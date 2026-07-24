"""마일스톤 4 (신고/차단) 스모크 테스트.

실행: 프로젝트 루트에서
    python tests/test_report.py

검증: 신고 접수·사유 필수, 중복 신고 차단, 자기신고 금지,
      임계치(5) 도달 시 상품 자동 차단(FR-4.3)·유저 자동 휴면(FR-4.4).
"""
import os
import sys
import base64
import shutil
import tempfile
from io import BytesIO
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from models import db, User, Product

tmpdir = tempfile.mkdtemp()

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+P+/HgAFhAJ/wlseKgAAAABJRU5ErkJggg=="
)


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

def create_product(client, title):
    client.post("/product/new", data={
        "title": title, "price": "1000", "description": "설명",
        "image": (BytesIO(PNG_BYTES), "photo.png"),
    }, content_type="multipart/form-data", follow_redirects=True)
    with app.app_context():
        return Product.query.filter_by(title=title).first().id

def do_report(client, target_type, target_id, reason="불량 게시물"):
    return client.post("/report", data={
        "target_type": target_type, "target_id": target_id, "reason": reason,
    }, follow_redirects=True)

def user_id(username):
    with app.app_context():
        return User.query.filter_by(username=username).first().id

def prod_count_status(pid):
    with app.app_context():
        p = db.session.get(Product, pid)
        return p.report_count, p.status

def user_count_status(uid):
    with app.app_context():
        u = db.session.get(User, uid)
        return u.report_count, u.status


# ---- 준비 ----
alice = app.test_client(); register_and_login(alice, "alice")   # 판매자
bob = app.test_client();   register_and_login(bob, "bob")       # 자기신고 테스트용
victim = app.test_client(); register_and_login(victim, "victim")# 휴면 대상

reporters = []
for i in range(5):
    c = app.test_client(); register_and_login(c, f"reporter{i}")
    reporters.append(c)

p_block = create_product(alice, "차단대상상품")   # 5회 신고로 차단할 상품
p_misc = create_product(bob, "잡화상품")          # 자기신고/중복/사유 테스트용

# 1) 비로그인 신고는 로그인으로 리다이렉트
anon = app.test_client()
r = do_report(anon, "product", p_block)
check("비로그인 신고 차단", "로그인이 필요합니다" in r.get_data(as_text=True))

# 2) 사유 없는 신고 거부 (카운트 미증가)
r = reporters[0].post("/report", data={"target_type": "product",
    "target_id": p_misc, "reason": "   "}, follow_redirects=True)
check("사유 없는 신고 거부", "신고 사유를 입력" in r.get_data(as_text=True))
check("사유 없으면 카운트 미증가", prod_count_status(p_misc)[0] == 0)

# 3) 자기 상품 신고 금지
r = do_report(bob, "product", p_misc)
check("자기 상품 신고 금지", "본인 상품은 신고할 수 없습니다" in r.get_data(as_text=True))
check("자기 상품 신고 카운트 미증가", prod_count_status(p_misc)[0] == 0)

# 4) 자기 자신(유저) 신고 금지
r = do_report(bob, "user", user_id("bob"))
check("본인 유저 신고 금지", "본인은 신고할 수 없습니다" in r.get_data(as_text=True))

# 5) 정상 신고 접수 + 중복 신고 차단
r = do_report(reporters[0], "product", p_misc)
check("정상 신고 접수", "신고가 접수되었습니다" in r.get_data(as_text=True))
check("신고 후 카운트 1", prod_count_status(p_misc)[0] == 1)
r = do_report(reporters[0], "product", p_misc)          # 같은 사람 재신고
check("중복 신고 차단", "이미 신고한 대상입니다" in r.get_data(as_text=True))
check("중복 신고는 카운트 미증가", prod_count_status(p_misc)[0] == 1)

# 6) 임계치(5) 도달 → 상품 자동 차단 (FR-4.3)
for i in range(4):
    do_report(reporters[i], "product", p_block)
check("4회 신고 시 아직 active", prod_count_status(p_block) == (4, "active"))
r = do_report(reporters[4], "product", p_block)         # 5회째
check("5회 신고 시 차단 안내", "차단되었습니다" in r.get_data(as_text=True))
check("상품 status=blocked", prod_count_status(p_block)[1] == "blocked")
# 차단 상품은 상세 404 + 목록에서 숨김
check("차단 상품 상세 404", anon.get(f"/product/{p_block}").status_code == 404)
check("차단 상품 목록 숨김", "차단대상상품" not in anon.get("/").get_data(as_text=True))

# 7) 임계치(5) 도달 → 유저 자동 휴면 (FR-4.4)
vid = user_id("victim")
for i in range(4):
    do_report(reporters[i], "user", vid)
check("4회 신고 시 유저 active", user_count_status(vid) == (4, "active"))
r = do_report(reporters[4], "user", vid)
check("5회 신고 시 휴면 안내", "휴면 처리되었습니다" in r.get_data(as_text=True))
check("유저 status=dormant", user_count_status(vid)[1] == "dormant")
# 휴면 계정은 로그인 차단
fresh = app.test_client()
r = fresh.post("/login", data={"username": "victim", "password": "password123"},
               follow_redirects=True)
check("휴면 계정 로그인 차단", "휴면" in r.get_data(as_text=True))

# 8) 잘못된 target_type 은 400
r = reporters[0].post("/report", data={"target_type": "evil",
    "target_id": 1, "reason": "x"})
check("잘못된 대상 타입 400", r.status_code == 400)

shutil.rmtree(tmpdir, ignore_errors=True)

print("\n=== RESULT ===")
failed = [n for n, ok in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
