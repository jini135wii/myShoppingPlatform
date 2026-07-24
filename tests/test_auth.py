"""마일스톤 1 (인증) 스모크 테스트.

실행: 프로젝트 루트에서
    python tests/test_auth.py

격리된 임시 DB를 사용하며 CSRF는 테스트 편의상 비활성화한다.
검증 항목: 회원가입/중복거부/입력검증/비번해싱/열거방지/로그인/XSS 이스케이프/비번변경/접근제어.
"""
import os
import sys
import shutil
import tempfile
from datetime import timedelta

# 프로젝트 루트를 import 경로에 추가 (어디서 실행해도 동작)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from models import db, User

tmpdir = tempfile.mkdtemp()


class TestConfig:
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(tmpdir, "test.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False            # 테스트 편의상 비활성 (실서비스는 활성)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=6)
    UPLOAD_FOLDER = tmpdir
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
    REPORT_THRESHOLD = 5


app = create_app(TestConfig)   # create_app 내부에서 db.create_all() 수행

results = []
def check(name, cond):
    results.append((name, cond))
    print(("  ok " if cond else "FAIL ") + name)


c = app.test_client()

# 1) 회원가입
r = c.post("/register", data={"username": "alice", "password": "password123",
                              "confirm": "password123"}, follow_redirects=True)
check("회원가입 성공", "회원가입이 완료" in r.get_data(as_text=True))

# 2) 아이디 중복 거부 (FR-1.5)
r = c.post("/register", data={"username": "alice", "password": "password123",
                              "confirm": "password123"})
check("중복 아이디 거부", "이미 사용 중인 아이디" in r.get_data(as_text=True))

# 3) 짧은 비밀번호 거부 (입력 검증)
r = c.post("/register", data={"username": "bob", "password": "short",
                              "confirm": "short"})
check("짧은 비밀번호 거부", "8자 이상" in r.get_data(as_text=True))

# 4) 비밀번호 원문 미저장 (해싱)
with app.app_context():
    u = User.query.filter_by(username="alice").first()
    check("비밀번호 해싱 저장",
          "password123" not in u.password_hash and "$" in u.password_hash)

# 5) 틀린 비번 / 없는 유저 → 동일 메시지 (사용자 열거 방지)
r_wrong_pw = c.post("/login", data={"username": "alice", "password": "wrongpass"})
r_no_user = c.post("/login", data={"username": "ghost", "password": "whatever"})
msg = "아이디 또는 비밀번호가 올바르지 않습니다"
check("틀린 비번/없는 유저 동일 메시지 (열거 방지)",
      msg in r_wrong_pw.get_data(as_text=True) and msg in r_no_user.get_data(as_text=True))

# 6) 정상 로그인
r = c.post("/login", data={"username": "alice", "password": "password123"},
           follow_redirects=True)
check("정상 로그인", "환영합니다" in r.get_data(as_text=True))

# 7) 마이페이지 소개글에 XSS 페이로드 저장 → 프로필에서 이스케이프 확인
xss = "<script>alert('x')</script>"
c.post("/mypage", data={"bio": xss, "new_password": "", "confirm": ""},
       follow_redirects=True)
with app.app_context():
    uid = User.query.filter_by(username="alice").first().id
body = c.get(f"/user/{uid}").get_data(as_text=True)
check("XSS 이스케이프 (프로필 출력)",
      "<script>alert" not in body and "&lt;script&gt;" in body)

# 8) 비밀번호 변경(현재 비번 재인증 필요) 후 재로그인
c.post("/mypage", data={"bio": xss, "current_password": "password123",
                        "new_password": "newpassword456",
                        "confirm": "newpassword456"}, follow_redirects=True)
c.get("/logout")
r = c.post("/login", data={"username": "alice", "password": "newpassword456"},
           follow_redirects=True)
check("비밀번호 변경 후 재로그인", "환영합니다" in r.get_data(as_text=True))

# 8b) 민감작업 재인증 — 틀린 현재 비번으로 변경 시도 거부
r = c.post("/mypage", data={"bio": xss, "current_password": "wrongpw",
                            "new_password": "hackedpass1", "confirm": "hackedpass1"},
           follow_redirects=True)
check("비번변경 재인증(틀린 현재비번 거부)",
      "현재 비밀번호가 올바르지 않습니다" in r.get_data(as_text=True))
c.get("/logout")
r = c.post("/login", data={"username": "alice", "password": "newpassword456"},
           follow_redirects=True)
check("재인증 실패 시 기존 비번 유지", "환영합니다" in r.get_data(as_text=True))

# 8c) 소개글만 변경은 현재 비번 없이 가능
r = c.post("/mypage", data={"bio": "소개 업데이트", "current_password": "",
                            "new_password": "", "confirm": ""}, follow_redirects=True)
check("소개글만 변경은 재인증 불필요", "프로필이 저장되었습니다" in r.get_data(as_text=True))

# 9) 비로그인 상태 마이페이지 접근 차단
c.get("/logout")
r = c.get("/mypage", follow_redirects=True)
check("비로그인 마이페이지 차단", "로그인이 필요합니다" in r.get_data(as_text=True))

# 10) 로그인 시도 제한 (브루트포스): 임계치(5) 초과 시 쿨다운
rc = app.test_client()
rc.post("/register", data={"username": "ratevictim", "password": "password123",
                           "confirm": "password123"}, follow_redirects=True)
for _ in range(5):                                   # 5회 실패 누적
    rc.post("/login", data={"username": "ratevictim", "password": "wrong"})
r = rc.post("/login", data={"username": "ratevictim", "password": "wrong"})
check("로그인 시도 제한 발동", "시도가 너무 많습니다" in r.get_data(as_text=True))
# 올바른 비번이어도 쿨다운 중엔 거부
r = rc.post("/login", data={"username": "ratevictim", "password": "password123"},
            follow_redirects=True)
check("쿨다운 중 정상 비번도 차단", "시도가 너무 많습니다" in r.get_data(as_text=True))

# 11) 커스텀 404 페이지 (내부 정보 노출 방지)
r = c.get("/this-page-does-not-exist")
check("커스텀 404 페이지",
      r.status_code == 404 and "페이지를 찾을 수 없습니다" in r.get_data(as_text=True))

shutil.rmtree(tmpdir, ignore_errors=True)

print("\n=== RESULT ===")
failed = [n for n, ok in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
