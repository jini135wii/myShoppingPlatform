"""보안 체크리스트 집중 테스트 (SEC).

회원/상품/신고/관리자 전반의 핵심 보안 요소를 HTTP 레벨에서 검증한다.
기존 기능 테스트에서 덜 다룬 항목(CSRF 강제·세션 쿠키 플래그·세션 고정·
SQLi·경로조작·저장형 XSS·입력 검증)을 집중 커버.

실행: python tests/test_security.py
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


class BaseConfig:
    SECRET_KEY = "test-secret"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=6)
    UPLOAD_FOLDER = os.path.join(tmpdir, "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    REPORT_THRESHOLD = 5
    SIGNUP_BONUS = 10000


class TestConfig(BaseConfig):                       # 대부분 테스트(CSRF 비활성)
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(tmpdir, "test.db")
    WTF_CSRF_ENABLED = False


class CsrfConfig(BaseConfig):                        # CSRF 강제 검증 전용
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(tmpdir, "csrf.db")
    WTF_CSRF_ENABLED = True


app = create_app(TestConfig)
csrf_app = create_app(CsrfConfig)

results = []
def check(name, cond):
    results.append((name, cond))
    print(("  ok " if cond else "FAIL ") + name)

def reg_login(c, u, p="password123"):
    c.post("/register", data={"username": u, "password": p, "confirm": p}, follow_redirects=True)
    c.post("/login", data={"username": u, "password": p}, follow_redirects=True)

def create_product(c, title, description="설명", price="1000"):
    c.post("/product/new", data={"title": title, "price": price, "description": description,
        "image": (BytesIO(PNG_BYTES), "p.png")},
        content_type="multipart/form-data", follow_redirects=True)


# ---- 준비 ----
alice = app.test_client(); reg_login(alice, "alice")
admin = app.test_client(); reg_login(admin, "admin")
with app.app_context():
    a = User.query.filter_by(username="admin").first(); a.is_admin = True; db.session.commit()
    admin_id = User.query.filter_by(username="admin").first().id


# ===== 회원가입 및 프로필 =====

# 1) CSRF — 토큰 없는 POST 거부
r = csrf_app.test_client().post("/login", data={"username": "x", "password": "y"})
check("[회원] CSRF 토큰 없는 POST 거부", r.status_code == 400)

# 2~3) 세션 쿠키 플래그(HttpOnly / SameSite)
sc = app.test_client()
sc.post("/register", data={"username": "cookie", "password": "password123",
                           "confirm": "password123"}, follow_redirects=True)
r = sc.post("/login", data={"username": "cookie", "password": "password123"}, follow_redirects=False)
setcookie = " ".join(r.headers.getlist("Set-Cookie"))
check("[회원] 세션 쿠키 HttpOnly", "HttpOnly" in setcookie)
check("[회원] 세션 쿠키 SameSite=Lax", "SameSite=Lax" in setcookie)

# 4) 세션 고정 방어 — 로그인 시 기존 세션 폐기
sf = app.test_client()
sf.post("/register", data={"username": "sfuser", "password": "password123",
                           "confirm": "password123"}, follow_redirects=True)
with sf.session_transaction() as s:
    s["planted"] = "attacker"
sf.post("/login", data={"username": "sfuser", "password": "password123"}, follow_redirects=True)
with sf.session_transaction() as s:
    check("[회원] 세션 고정 방어(기존 세션 폐기)", "planted" not in s and s.get("user_id"))

# 5) 사용자명 서버측 검증 — 특수문자/스크립트 거부
r = app.test_client().post("/register", data={"username": "<script>x", "password": "password123",
                                              "confirm": "password123"})
check("[회원] 사용자명 특수문자 거부", "밑줄" in r.get_data(as_text=True))

# 6) SQL 인젝션 — 아이디 필드 로그인 우회 시도 실패
r = app.test_client().post("/login", data={"username": "' OR '1'='1", "password": "x"},
                           follow_redirects=True)
check("[회원] SQLi 로그인 우회 실패(아이디 필드)", "환영합니다" not in r.get_data(as_text=True))

# 6b) SQL 인젝션 — 비밀번호 필드(실존 아이디 + 인젝션 비번) 우회 시도 실패
# [보안] 비밀번호는 SQL 쿼리에 전혀 들어가지 않음(ORM으로 username만 조회 후,
#        가져온 해시를 check_password_hash로 파이썬에서 검증) → 쿼리 자체가 없어 원천 차단
r = app.test_client().post("/login",
        data={"username": "alice", "password": "x' OR '1'='1"}, follow_redirects=True)
check("[회원] SQLi 로그인 우회 실패(비번 필드)", "환영합니다" not in r.get_data(as_text=True))

# 6c) SQL 인젝션 — 전형적 인증우회 페이로드(주석 처리 시도) 아이디+비번 동시
r = app.test_client().post("/login",
        data={"username": "alice' -- ", "password": "anything"}, follow_redirects=True)
check("[회원] SQLi 로그인 우회 실패(주석 페이로드)", "환영합니다" not in r.get_data(as_text=True))


# ===== 상품 등록 및 관리 =====

# 7) SQL 인젝션 — 검색어 무해 처리
r = app.test_client().get("/?q=' OR '1'='1")
check("[상품] SQLi 검색 무해 처리(200)", r.status_code == 200)

# 8) 가격 서버측 검증 — 음수 거부
create_product(alice, "음수가격상품", price="-500")
with app.app_context():
    check("[상품] 음수 가격 거부(미생성)",
          Product.query.filter_by(title="음수가격상품").first() is None)

# 9) 가격 서버측 검증 — 비숫자 거부
create_product(alice, "문자가격상품", price="abc")
with app.app_context():
    check("[상품] 비숫자 가격 거부(미생성)",
          Product.query.filter_by(title="문자가격상품").first() is None)

# 10) 상품 설명 저장형 XSS 이스케이프
create_product(alice, "XSS설명상품", description="<script>alert(7)</script>")
with app.app_context():
    pid = Product.query.filter_by(title="XSS설명상품").first().id
body = alice.get(f"/product/{pid}").get_data(as_text=True)
check("[상품] 설명 저장형 XSS 이스케이프",
      "<script>alert(7)" not in body and "&lt;script&gt;" in body)

# 11) 업로드 경로조작(../) 차단 — 소스 파일 유출 방지
r = app.test_client().get("/uploads/..%2f..%2fmodels.py")
check("[상품] 업로드 경로조작 차단",
      r.status_code == 404 and "class User" not in r.get_data(as_text=True))


# ===== 안전 거래 및 신고 =====

# 12) 신고 사유 길이 검증 — 500자 초과 거부
r = alice.post("/report", data={"target_type": "user", "target_id": admin_id,
                                "reason": "x" * 501}, follow_redirects=True)
check("[신고] 사유 500자 초과 거부", "너무 깁니다" in r.get_data(as_text=True))

# 13) 신고 사유 저장형 XSS — 관리자 화면에서 이스케이프
alice.post("/report", data={"target_type": "user", "target_id": admin_id,
                            "reason": "<script>alert(3)</script>"}, follow_redirects=True)
body = admin.get("/admin/reports").get_data(as_text=True)
check("[신고] 사유 XSS 관리자화면 이스케이프",
      "<script>alert(3)" not in body and "&lt;script&gt;" in body)

# 14) 관리자 권한 분리 — 비관리자 접근 403
check("[관리자] 비관리자 접근 403", alice.get("/admin/users").status_code == 403)

shutil.rmtree(tmpdir, ignore_errors=True)

print("\n=== RESULT ===")
failed = [n for n, ok in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
