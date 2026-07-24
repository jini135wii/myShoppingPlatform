"""신고 / 차단 모듈 (FR-4).

- 상품/사용자를 사유와 함께 신고
- 동일인이 같은 대상을 중복 신고하지 못하도록 차단 (카운트 조작 방지)
- 자기 자신/자기 상품 신고 금지
- 누적 신고가 임계치(REPORT_THRESHOLD, 기본 5) 도달 시:
    상품 → status=blocked (목록/상세에서 숨김), 유저 → status=dormant (로그인 차단)
"""
from flask import (Blueprint, request, redirect, url_for, flash, abort,
                   current_app)
from sqlalchemy.exc import IntegrityError

from models import db, User, Product, Report
from helpers import login_required, current_user

report_bp = Blueprint("report", __name__)

MAX_REASON_LEN = 500
VALID_TARGETS = ("product", "user")


def _back(target_type, target_id):
    """신고 처리 후 원래 보던 페이지로 되돌려 보낸다."""
    if target_type == "product":
        return redirect(url_for("product.detail", product_id=target_id))
    return redirect(url_for("auth.profile", user_id=target_id))


def _apply_threshold(target_type, target):
    """임계치 도달 시 상품 차단 / 유저 휴면 전환. 상태를 바꿨으면 True."""
    if target.report_count < current_app.config["REPORT_THRESHOLD"]:
        return False
    target.status = "blocked" if target_type == "product" else "dormant"
    return True


@report_bp.route("/report", methods=["POST"])
@login_required
def report():
    # CSRF는 CSRFProtect가 전역 검증(form의 csrf_token) — 통과한 요청만 여기 도달
    me = current_user()
    target_type = request.form.get("target_type", "")
    reason = (request.form.get("reason") or "").strip()

    # 1) 입력 검증 (타입 화이트리스트 · 사유 필수·길이)
    if target_type not in VALID_TARGETS:
        abort(400)
    try:
        target_id = int(request.form.get("target_id", ""))
    except (TypeError, ValueError):
        abort(400)
    if not reason:
        flash("신고 사유를 입력해 주세요.", "danger")
        return _back(target_type, target_id)
    if len(reason) > MAX_REASON_LEN:
        flash("신고 사유가 너무 깁니다(최대 500자).", "danger")
        return _back(target_type, target_id)

    # 2) 대상 조회 (없으면 404)
    if target_type == "product":
        target = db.session.get(Product, target_id)
    else:
        target = db.session.get(User, target_id)
    if target is None:
        abort(404)

    # 3) [보안] 자기 자신/자기 상품 신고 금지 (카운트 자작 방지)
    if target_type == "user" and target.id == me.id:
        flash("본인은 신고할 수 없습니다.", "danger")
        return _back(target_type, target_id)
    if target_type == "product" and target.seller_id == me.id:
        flash("본인 상품은 신고할 수 없습니다.", "danger")
        return _back(target_type, target_id)

    # 4) [보안] 중복 신고 차단 — UNIQUE(reporter, target_type, target_id) 위반 감지
    db.session.add(Report(reporter_id=me.id, target_type=target_type,
                          target_id=target_id, reason=reason))
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        flash("이미 신고한 대상입니다.", "warning")
        return _back(target_type, target_id)

    # 5) 카운트 증가 + 임계치 도달 시 차단/휴면
    target.report_count += 1
    acted = _apply_threshold(target_type, target)
    db.session.commit()

    if acted and target_type == "product":
        # 차단된 상품 상세는 404가 되므로 목록으로 돌려보낸다
        flash("신고가 접수되었고, 누적 신고로 해당 상품이 차단되었습니다.", "success")
        return redirect(url_for("index"))
    if acted:
        flash("신고가 접수되었고, 누적 신고로 해당 사용자가 휴면 처리되었습니다.", "success")
    else:
        flash("신고가 접수되었습니다.", "success")
    return _back(target_type, target_id)
