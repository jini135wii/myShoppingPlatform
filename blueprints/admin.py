"""관리자 패널 (확장 기능). 플랫폼 전 요소 관리 + 이의제기 심사.

[보안] 모든 라우트는 admin_required로 보호 — 권한 분리(서버측 강제).
일반 유저가 URL을 직접 쳐도 403.
"""
from datetime import datetime

from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, abort)

from models import db, User, Product, Report, Appeal, Message, AdminLog
from helpers import admin_required, current_user
from blueprints.product import _remove_image

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _log(action, target_type=None, target_id=None, detail=""):
    """관리 행위를 감사 로그에 적재(해당 라우트의 commit과 함께 저장)."""
    db.session.add(AdminLog(admin_id=current_user().id, action=action,
                            target_type=target_type, target_id=target_id,
                            detail=(detail or "")[:255]))


def _pardon_user(user):
    """사면: 유저 휴면 해제 + 본인 차단상품 복구 + 관련 신고 기록 삭제(카운트 초기화)."""
    user.status = "active"
    user.report_count = 0
    Report.query.filter_by(target_type="user", target_id=user.id).delete()
    for p in Product.query.filter_by(seller_id=user.id, status="blocked").all():
        p.status = "active"
        p.report_count = 0
        Report.query.filter_by(target_type="product", target_id=p.id).delete()


def _delete_user(u):
    """회원 삭제 시 관련 데이터 연쇄 정리(고아 데이터·FK 무결성 방지)."""
    for p in Product.query.filter_by(seller_id=u.id).all():
        Report.query.filter_by(target_type="product", target_id=p.id).delete()
        _remove_image(p.image_path)                 # 업로드 파일도 정리
        db.session.delete(p)
    Message.query.filter(
        (Message.sender_id == u.id) | (Message.receiver_id == u.id)
    ).delete(synchronize_session=False)
    Report.query.filter_by(reporter_id=u.id).delete()
    Report.query.filter_by(target_type="user", target_id=u.id).delete()
    Appeal.query.filter_by(user_id=u.id).delete()
    AdminLog.query.filter_by(admin_id=u.id).delete()      # 이 유저가 관리자로 남긴 로그
    db.session.delete(u)


@admin_bp.route("/")
@admin_required
def dashboard():
    stats = {
        "users": User.query.count(),
        "dormant": User.query.filter_by(status="dormant").count(),
        "products": Product.query.count(),
        "blocked": Product.query.filter_by(status="blocked").count(),
        "reports": Report.query.count(),
        "messages": Message.query.count(),
        "pending_appeals": Appeal.query.filter_by(status="pending").count(),
        "logs": AdminLog.query.count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


@admin_bp.route("/users")
@admin_required
def users():
    rows = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=rows)


@admin_bp.route("/users/<int:user_id>/status", methods=["POST"])
@admin_required
def user_status(user_id):
    u = User.query.get_or_404(user_id)
    if u.id == current_user().id:
        flash("본인 계정 상태는 변경할 수 없습니다.", "danger")   # 자기 잠금 방지
        return redirect(url_for("admin.users"))
    action = request.form.get("action")
    if action == "dormant":
        u.status = "dormant"
        _log("회원 휴면", "user", u.id, u.username)
        flash(f"{u.username} 계정을 휴면 처리했습니다.", "info")
    elif action == "activate":
        u.status = "active"
        u.report_count = 0
        Report.query.filter_by(target_type="user", target_id=u.id).delete()
        _log("회원 활성화", "user", u.id, u.username)
        flash(f"{u.username} 계정을 활성화했습니다.", "success")
    else:
        abort(400)
    db.session.commit()
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@admin_required
def user_role(user_id):
    u = User.query.get_or_404(user_id)
    action = request.form.get("action")
    if action == "promote":
        u.is_admin = True
        _log("관리자 지정", "user", u.id, u.username)
        flash(f"{u.username}에게 관리자 권한을 부여했습니다.", "success")
    elif action == "demote":
        if u.id == current_user().id:
            flash("본인의 관리자 권한은 해제할 수 없습니다.", "danger")   # 자기 권한 박탈 방지
            return redirect(url_for("admin.users"))
        u.is_admin = False
        _log("관리자 해제", "user", u.id, u.username)
        flash(f"{u.username}의 관리자 권한을 해제했습니다.", "info")
    else:
        abort(400)
    db.session.commit()
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def user_delete(user_id):
    u = User.query.get_or_404(user_id)
    if u.id == current_user().id:
        flash("본인 계정은 삭제할 수 없습니다.", "danger")               # 자기 삭제(락아웃) 방지
        return redirect(url_for("admin.users"))
    name = u.username
    _delete_user(u)
    _log("회원 삭제", "user", user_id, name)
    db.session.commit()
    flash(f"{name} 계정과 관련 데이터를 삭제했습니다.", "info")
    return redirect(url_for("admin.users"))


@admin_bp.route("/products")
@admin_required
def products():
    rows = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("admin/products.html", products=rows)


@admin_bp.route("/products/<int:product_id>/status", methods=["POST"])
@admin_required
def product_status(product_id):
    p = Product.query.get_or_404(product_id)
    action = request.form.get("action")
    if action == "block":
        p.status = "blocked"
        _log("상품 차단", "product", p.id, p.title)
        flash("상품을 차단했습니다.", "info")
    elif action == "unblock":
        p.status = "active"
        p.report_count = 0
        Report.query.filter_by(target_type="product", target_id=p.id).delete()
        _log("상품 차단해제", "product", p.id, p.title)
        flash("상품 차단을 해제했습니다.", "success")
    else:
        abort(400)
    db.session.commit()
    return redirect(url_for("admin.products"))


@admin_bp.route("/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def product_delete(product_id):
    p = Product.query.get_or_404(product_id)
    _log("상품 삭제", "product", p.id, p.title)
    db.session.delete(p)
    db.session.commit()
    flash("상품을 삭제했습니다.", "info")
    return redirect(url_for("admin.products"))


@admin_bp.route("/reports")
@admin_required
def reports():
    rows = Report.query.order_by(Report.created_at.desc()).all()
    # id → 이름 해석 (소규모 플랫폼: 전량 캐시)
    user_names = {u.id: u.username for u in User.query.all()}
    product_titles = {p.id: p.title for p in Product.query.all()}
    items = []
    for r in rows:
        if r.target_type == "user":
            label = user_names.get(r.target_id, f"삭제된 사용자 #{r.target_id}")
        else:
            label = product_titles.get(r.target_id, f"삭제된 상품 #{r.target_id}")
        items.append({
            "id": r.id,
            "reporter_id": r.reporter_id,
            "reporter": user_names.get(r.reporter_id, f"#{r.reporter_id}"),
            "target_type": r.target_type,
            "target_id": r.target_id,
            "target_label": label,
            "target_exists": (r.target_id in (user_names if r.target_type == "user" else product_titles)),
            "reason": r.reason,
            "created_at": r.created_at,
        })
    return render_template("admin/reports.html", reports=items)


@admin_bp.route("/reports/<int:report_id>/delete", methods=["POST"])
@admin_required
def report_delete(report_id):
    r = Report.query.get_or_404(report_id)
    _log("신고 삭제", "report", r.id, f"{r.target_type} #{r.target_id}")
    db.session.delete(r)
    db.session.commit()
    flash("신고를 삭제했습니다.", "info")
    return redirect(url_for("admin.reports"))


@admin_bp.route("/messages")
@admin_required
def messages():
    # [보안/프라이버시] 전체 채팅만 관리자 열람 대상. 1:1 DM은 당사자 외 열람 불가(도청 방지 원칙 유지).
    rows = (Message.query.filter_by(receiver_id=None)
            .order_by(Message.created_at.desc()).limit(100).all())
    names = {u.id: u.username for u in User.query.all()}
    return render_template("admin/messages.html", messages=rows, names=names)


@admin_bp.route("/messages/<int:message_id>/delete", methods=["POST"])
@admin_required
def message_delete(message_id):
    m = Message.query.get_or_404(message_id)
    if m.receiver_id is not None:
        # [보안/프라이버시] 1:1 DM은 관리자도 조회·조작 불가 — URL 직접 접근도 차단
        abort(403)
    _log("메시지 삭제", "message", m.id, m.content[:50])
    db.session.delete(m)
    db.session.commit()
    flash("메시지를 삭제했습니다.", "info")
    return redirect(url_for("admin.messages"))


@admin_bp.route("/appeals")
@admin_required
def appeals():
    rows = Appeal.query.order_by(Appeal.created_at.desc()).all()
    return render_template("admin/appeals.html", appeals=rows)


@admin_bp.route("/appeals/<int:appeal_id>/resolve", methods=["POST"])
@admin_required
def appeal_resolve(appeal_id):
    ap = Appeal.query.get_or_404(appeal_id)
    if ap.status != "pending":
        flash("이미 처리된 이의제기입니다.", "warning")
        return redirect(url_for("admin.appeals"))
    action = request.form.get("action")
    if action == "approve":
        _pardon_user(ap.user)
        ap.status = "approved"
        _log("이의제기 승인", "appeal", ap.id, ap.user.username)
        flash(f"{ap.user.username}의 이의제기를 승인(사면)했습니다.", "success")
    elif action == "reject":
        ap.status = "rejected"
        _log("이의제기 반려", "appeal", ap.id, ap.user.username)
        flash("이의제기를 반려했습니다.", "info")
    else:
        abort(400)
    ap.resolved_at = datetime.utcnow()
    ap.resolver_id = current_user().id
    db.session.commit()
    return redirect(url_for("admin.appeals"))


@admin_bp.route("/logs")
@admin_required
def logs():
    rows = AdminLog.query.order_by(AdminLog.created_at.desc()).limit(200).all()
    names = {u.id: u.username for u in User.query.all()}
    return render_template("admin/logs.html", logs=rows, names=names)
