"""마일스톤 6 (가상 포인트 지갑) 스모크 테스트.

실행: 프로젝트 루트에서
    python tests/test_wallet.py

검증: 가입 보너스, 유저간 송금(원자적 차감/입금), 잔액 부족·음수·0·자기송금·미존재 수신자 차단,
      비로그인 차단, IDOR(출금은 항상 세션 유저).
"""
import os
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from models import db, User, Wallet, Transaction

tmpdir = tempfile.mkdtemp()


class TestConfig:
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(tmpdir, "test.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=6)
    UPLOAD_FOLDER = os.path.join(tmpdir, "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    REPORT_THRESHOLD = 5
    SIGNUP_BONUS = 10000


app = create_app(TestConfig)

results = []
def check(name, cond):
    results.append((name, cond))
    print(("  ok " if cond else "FAIL ") + name)

def register_and_login(client, username, password="password123"):
    client.post("/register", data={"username": username, "password": password,
                                   "confirm": password}, follow_redirects=True)
    client.post("/login", data={"username": username, "password": password},
                follow_redirects=True)

def transfer(client, to, amount):
    return client.post("/wallet/transfer", data={"recipient": to, "amount": str(amount)},
                       follow_redirects=True)

def balance(username):
    with app.app_context():
        u = User.query.filter_by(username=username).first()
        w = Wallet.query.filter_by(user_id=u.id).first()
        return w.balance if w else None


# ---- 준비 ----
alice = app.test_client(); register_and_login(alice, "alice")
bob = app.test_client(); register_and_login(bob, "bob")

# 1) 가입 보너스 (최초 지갑 조회 시 지급)
body = alice.get("/wallet").get_data(as_text=True)
check("지갑에 보너스 잔액 표시", "10,000" in body)
check("거래내역에 가입 보너스", "가입 보너스" in body)
check("alice 잔액 = 보너스", balance("alice") == 10000)

# 2) 정상 송금 (원자적 차감/입금)
r = transfer(alice, "bob", 3000)
check("송금 성공 안내", "송금했습니다" in r.get_data(as_text=True))
check("보낸이 차감", balance("alice") == 7000)
check("받는이 증가(보너스+수신)", balance("bob") == 13000)
with app.app_context():
    check("거래기록 생성", Transaction.query.filter_by(kind="transfer").count() == 1)

# 3) 잔액 부족 — 조건부 UPDATE로 차단, 잔액 불변
r = transfer(alice, "bob", 999999)
check("잔액 부족 차단", "잔액이 부족" in r.get_data(as_text=True))
check("실패 시 보낸이 불변", balance("alice") == 7000)
check("실패 시 받는이 불변", balance("bob") == 13000)

# 4) 0/음수 송금 — 정수 양수 검증
r = transfer(alice, "bob", 0)
check("0 송금 거부", "1 이상" in r.get_data(as_text=True))
r = transfer(alice, "bob", -100)
check("음수 송금 거부", "1 이상" in r.get_data(as_text=True))
check("검증 실패 시 잔액 불변", balance("alice") == 7000)

# 5) 비정수 금액 — 코어싱 실패로 거부(잔액 불변)
r = alice.post("/wallet/transfer", data={"recipient": "bob", "amount": "abc"},
               follow_redirects=True)
check("비정수 금액 거부(잔액 불변)", balance("alice") == 7000)

# 6) 자기 자신 송금 금지
r = transfer(alice, "alice", 100)
check("자기 송금 거부", "자기 자신" in r.get_data(as_text=True))
check("자기 송금 잔액 불변", balance("alice") == 7000)

# 7) 없는 수신자
r = transfer(alice, "ghost", 100)
check("없는 수신자 거부", "찾을 수 없" in r.get_data(as_text=True))

# 8) 연속 송금으로 초과 인출 시도 (누적 잔액 가드)
transfer(alice, "bob", 5000)                          # 7000 → 2000
check("정상 차감", balance("alice") == 2000)
r = transfer(alice, "bob", 5000)                      # 2000 < 5000 → 거부
check("누적 초과 인출 차단", "잔액이 부족" in r.get_data(as_text=True))
check("초과 인출 차단 후 불변", balance("alice") == 2000)

# 9) 비로그인 차단
anon = app.test_client()
r = anon.get("/wallet", follow_redirects=True)
check("비로그인 지갑 접근 차단", "로그인이 필요합니다" in r.get_data(as_text=True))
r = anon.post("/wallet/transfer", data={"recipient": "bob", "amount": "100"},
              follow_redirects=True)
check("비로그인 송금 차단", "로그인이 필요합니다" in r.get_data(as_text=True))

print("\n=== RESULT ===")
failed = [n for n, ok in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
