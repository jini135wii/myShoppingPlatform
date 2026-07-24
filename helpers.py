from functools import wraps

from flask import session, redirect, url_for, flash, abort

from models import db, User


def current_user():
    """현재 로그인한 사용자 객체 (없으면 None)."""
    uid = session.get("user_id")
    if uid is None:
        return None
    return db.session.get(User, uid)


def login_required(view):
    """로그인이 필요한 라우트 보호 데코레이터."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_id") is None:
            flash("로그인이 필요합니다.", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    """[보안] 관리자 전용 라우트 보호 — 권한 분리(서버측 강제)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        u = current_user()
        if u is None:
            flash("로그인이 필요합니다.", "warning")
            return redirect(url_for("auth.login"))
        if not u.is_admin:
            abort(403)                      # 일반 유저의 관리자 기능 접근 차단
        return view(*args, **kwargs)
    return wrapped
