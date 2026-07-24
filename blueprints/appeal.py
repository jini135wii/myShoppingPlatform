"""이의제기(소명) — 차단/휴면 조치에 대한 공개 소명 창구.

[설계] 휴면 유저는 로그인 자체가 막히므로, 로그인과 분리된 경로가 필요하다.
아이디+비밀번호로 **본인 인증만** 수행하고(세션은 발급하지 않음) 사유를 접수한다.
승인 전까지 계정/상품은 계속 잠긴 상태이며, 관리자가 심사한다.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash

from models import db, User, Product, Appeal
from helpers import current_user

appeal_bp = Blueprint("appeal", __name__)

MAX_MSG_LEN = 1000


@appeal_bp.route("/appeal", methods=["GET", "POST"])
def appeal():
    me = current_user()                      # 로그인 상태(차단상품 판매자)면 재인증 불필요
    if request.method == "GET":
        return render_template("appeal.html", logged_in=me is not None)

    def _render():
        return render_template("appeal.html", logged_in=me is not None)

    # 본인 확인
    if me is not None:
        user = me                            # 세션으로 이미 인증됨
    else:
        # 비로그인(휴면 등): 아이디+비밀번호로 인증 (열거 방지 동일 메시지)
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash("아이디 또는 비밀번호가 올바르지 않습니다.", "danger")
            return _render()

    # 입력 검증
    message = (request.form.get("message") or "").strip()
    if not message:
        flash("이의제기 사유를 입력해 주세요.", "danger")
        return _render()
    if len(message) > MAX_MSG_LEN:
        flash("사유가 너무 깁니다(최대 1000자).", "danger")
        return _render()

    # 제재된 항목이 있어야 이의제기 의미가 있음
    has_blocked = (Product.query
                   .filter_by(seller_id=user.id, status="blocked").first() is not None)
    if not (user.is_dormant or has_blocked):
        flash("현재 제재된 계정·상품이 없어 이의제기 대상이 아닙니다.", "info")
        return _render()

    # 중복(검토 대기) 신청 차단
    if Appeal.query.filter_by(user_id=user.id, status="pending").first():
        flash("이미 접수된 이의제기가 검토 중입니다.", "warning")
        return _render()

    # [보안] 비로그인 경로에서는 세션을 발급하지 않는다 — 접수만 하고 잠금 유지(휴면 우회 로그인 차단)
    db.session.add(Appeal(user_id=user.id, message=message))
    db.session.commit()
    flash("이의제기가 접수되었습니다. 관리자 검토 후 반영됩니다.", "success")
    return redirect(url_for("product.mine") if me is not None else url_for("auth.login"))
