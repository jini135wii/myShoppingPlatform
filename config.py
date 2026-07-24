import os
from datetime import timedelta

# .env 파일이 있으면 로드 (없거나 python-dotenv 미설치여도 무시)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # [보안] SECRET_KEY는 환경변수에서 로드 (하드코딩 금지).
    # 미설정 시 실행마다 무작위 값 생성 → 세션이 재시작 시 초기화되지만 안전.
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(32).hex()

    # SQLite DB
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or \
        "sqlite:///" + os.path.join(basedir, "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # [보안] 세션/쿠키 플래그
    SESSION_COOKIE_HTTPONLY = True                                    # JS의 쿠키 접근 차단 (XSS 완화)
    SESSION_COOKIE_SAMESITE = "Lax"                                  # 교차 사이트 요청 완화 (CSRF 방어 보조)
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"  # HTTPS 배포 시 1로 설정
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)     # 세션 수명 1시간(유휴 만료)

    # 상품 사진 업로드 (상품 모듈에서 사용)
    UPLOAD_FOLDER = os.path.join(basedir, "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024                             # [보안] 업로드 크기 5MB 제한
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    # 신고 임계치 (상품 차단 / 유저 휴면 공통)
    REPORT_THRESHOLD = int(os.environ.get("REPORT_THRESHOLD", "5"))

    # 가상 포인트 지갑 — 가입(최초 지갑 생성) 시 지급하는 보너스 (실제 화폐 아님)
    SIGNUP_BONUS = int(os.environ.get("SIGNUP_BONUS", "10000"))

    # 로그인 시도 제한 (브루트포스 완화): 윈도(초) 내 실패 임계치
    LOGIN_MAX_FAILURES = int(os.environ.get("LOGIN_MAX_FAILURES", "5"))
    LOGIN_FAIL_WINDOW = int(os.environ.get("LOGIN_FAIL_WINDOW", "300"))
