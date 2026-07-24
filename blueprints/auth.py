from time import time

from flask import (Blueprint, render_template, redirect, url_for, flash,
                   session, request, current_app)
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp, EqualTo, Optional

from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User
from helpers import login_required, current_user

auth_bp = Blueprint("auth", __name__)

USERNAME_RE = r"^[A-Za-z0-9_]+$"

# [보안] 타이밍 사이드채널 방지용 더미 해시.
# 아이디가 없을 때도 scrypt 검증을 한 번 돌려, 존재/미존재 아이디의 응답 시간을 맞춘다.
_DUMMY_HASH = generate_password_hash("dummy-password-for-constant-time-check")


# ---------- 로그인 시도 제한 (브루트포스 완화) ----------
# (IP, 아이디)별 실패 시각을 메모리에 기록해 임계 초과 시 쿨다운 동안 거부한다.
# 키에 IP를 포함하므로, 공격자가 남의 계정을 잠그는 계정잠금 DoS는 발생하지 않는다.
_login_failures = {}


def _rl_key(username):
    return (request.remote_addr or "?", (username or "").strip().lower())


def _login_blocked(key):
    window = current_app.config.get("LOGIN_FAIL_WINDOW", 300)
    limit = current_app.config.get("LOGIN_MAX_FAILURES", 5)
    now = time()
    fails = [t for t in _login_failures.get(key, []) if now - t < window]
    if fails:
        _login_failures[key] = fails
    else:
        _login_failures.pop(key, None)
    return len(fails) >= limit


def _record_login_failure(key):
    _login_failures.setdefault(key, []).append(time())


def _reset_login_failures(key):
    _login_failures.pop(key, None)


# ---------- 폼 (WTForms로 입력 검증 + CSRF 토큰) ----------

class RegisterForm(FlaskForm):
    username = StringField("아이디", validators=[
        DataRequired(), Length(min=3, max=20),
        Regexp(USERNAME_RE, message="영문/숫자/밑줄(_)만 사용할 수 있습니다."),
    ])
    password = PasswordField("비밀번호", validators=[
        DataRequired(), Length(min=8, max=128, message="비밀번호는 8자 이상이어야 합니다."),
    ])
    confirm = PasswordField("비밀번호 확인", validators=[
        DataRequired(), EqualTo("password", message="비밀번호가 일치하지 않습니다."),
    ])
    submit = SubmitField("가입하기")


class LoginForm(FlaskForm):
    username = StringField("아이디", validators=[DataRequired(), Length(max=20)])
    password = PasswordField("비밀번호", validators=[DataRequired()])
    submit = SubmitField("로그인")


class MyPageForm(FlaskForm):
    bio = TextAreaField("소개글", validators=[Optional(), Length(max=500)])
    current_password = PasswordField("현재 비밀번호 (비밀번호 변경 시 필수)",
                                     validators=[Optional()])
    new_password = PasswordField("새 비밀번호 (변경 시에만 입력)", validators=[
        Optional(), Length(min=8, max=128, message="비밀번호는 8자 이상이어야 합니다."),
    ])
    confirm = PasswordField("새 비밀번호 확인", validators=[
        EqualTo("new_password", message="비밀번호가 일치하지 않습니다."),
    ])
    submit = SubmitField("저장")


# ---------- 라우트 ----------

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("index"))
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        # FR-1.5: 아이디 중복 검사 (DB UNIQUE 제약 + 사전 검사)
        if User.query.filter_by(username=username).first():
            flash("이미 사용 중인 아이디입니다.", "danger")
            return render_template("register.html", form=form)
        user = User(username=username)
        user.set_password(form.password.data)   # [보안] 해싱 저장
        db.session.add(user)
        db.session.commit()
        flash("회원가입이 완료되었습니다. 로그인해 주세요.", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("index"))
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        key = _rl_key(username)
        # [보안] 브루트포스 완화 — 실패 누적 시 쿨다운 동안 거부
        if _login_blocked(key):
            flash("로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.", "danger")
            return render_template("login.html", form=form)
        user = User.query.filter_by(username=username).first()
        # [보안] 사용자 존재 여부와 무관하게 동일 메시지 + 동일 소요시간 → 사용자 열거 방지.
        # 아이디가 없어도 더미 해시로 검증을 수행해, "존재하면 느리고 없으면 빠른"
        # 타이밍 사이드채널(scrypt 검증 유무 차이)을 없앤다.
        pw_ok = (user.check_password(form.password.data) if user is not None
                else check_password_hash(_DUMMY_HASH, form.password.data))
        if user is None or not pw_ok:
            _record_login_failure(key)
            flash("아이디 또는 비밀번호가 올바르지 않습니다.", "danger")
            return render_template("login.html", form=form)
        if user.is_dormant:
            flash("신고 누적으로 휴면 처리된 계정입니다.", "danger")
            return render_template("login.html", form=form)
        # [보안] 세션 고정 공격 방어: 로그인 시 기존 세션 폐기 후 재설정
        _reset_login_failures(key)
        session.clear()
        session["user_id"] = user.id
        session.permanent = True
        flash(f"{user.username}님 환영합니다.", "success")
        return redirect(url_for("index"))
    return render_template("login.html", form=form)


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("로그아웃되었습니다.", "info")
    return redirect(url_for("index"))


@auth_bp.route("/mypage", methods=["GET", "POST"])
@login_required
def mypage():
    user = current_user()
    form = MyPageForm(obj=user)
    if form.validate_on_submit():
        if form.new_password.data:
            # [보안] 비밀번호 변경은 민감 작업 → 현재 비밀번호로 재인증
            if not user.check_password(form.current_password.data or ""):
                flash("현재 비밀번호가 올바르지 않습니다.", "danger")
                return render_template("mypage.html", form=form, user=user)
            user.set_password(form.new_password.data)
            flash("비밀번호가 변경되었습니다.", "success")
        user.bio = form.bio.data or ""
        db.session.commit()
        flash("프로필이 저장되었습니다.", "success")
        return redirect(url_for("auth.mypage"))
    return render_template("mypage.html", form=form, user=user)


@auth_bp.route("/user/<int:user_id>")
def profile(user_id):
    user = User.query.get_or_404(user_id)
    return render_template("profile.html", user=user)
