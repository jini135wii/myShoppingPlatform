"""최초 관리자를 부트스트랩하는 스크립트.

사용법:
    ./venv/bin/python tools/make_admin.py <username>

관리자가 한 명도 없으면 관리자 화면(/admin) 자체에 아무도 못 들어가므로,
최초 1명은 이 스크립트로 부여한다. 이후 추가 관리자는 기존 관리자가
/admin/users 화면에서 UI로 임명/해제할 수 있다(회원가입 시 자동 부여 등
암묵 규칙은 없음 — 권한 상승 경로 최소화).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, User


def main():
    if len(sys.argv) < 2:
        print("usage: python tools/make_admin.py <username>")
        sys.exit(1)
    username = sys.argv[1]
    with app.app_context():
        u = User.query.filter_by(username=username).first()
        if u is None:
            print(f"[!] 그런 사용자가 없습니다: {username}")
            sys.exit(1)
        u.is_admin = True
        db.session.commit()
        print(f"[ok] {username} → is_admin=True")


if __name__ == "__main__":
    main()
