import os
import secrets

from flask import (Blueprint, render_template, redirect, url_for, flash,
                   abort, current_app, send_from_directory)
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, IntegerField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional

from models import db, Product
from helpers import login_required, current_user

product_bp = Blueprint("product", __name__)

# 폼 단계 확장자 필터 (UX용). 실제 방어는 아래 매직바이트 검증.
ALLOWED_EXTENSIONS = ("png", "jpg", "jpeg", "gif", "webp")


class ProductForm(FlaskForm):
    title = StringField("상품명", validators=[DataRequired(), Length(min=1, max=100)])
    price = IntegerField("가격(원)", validators=[
        InputRequired(), NumberRange(min=0, max=1_000_000_000, message="0 이상 금액을 입력하세요."),
    ])
    description = TextAreaField("설명", validators=[Optional(), Length(max=2000)])
    image = FileField("사진", validators=[
        FileAllowed(ALLOWED_EXTENSIONS, "이미지 파일(png/jpg/gif/webp)만 업로드할 수 있습니다."),
    ])
    submit = SubmitField("저장")


# ---------- 이미지 업로드 검증/저장 ----------

def _detect_image_ext(head: bytes):
    """파일의 실제 내용(매직 바이트)으로 이미지 형식 판별. 확장자 위장 방지."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "gif"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "webp"
    return None


def save_product_image(file_storage):
    """업로드 이미지를 검증 후 저장. (filename, error) 반환."""
    if not file_storage or not file_storage.filename:
        return None, "이미지를 선택해 주세요."

    # 1) 확장자 화이트리스트
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
        return None, "허용되지 않는 파일 형식입니다."

    # 2) 실제 내용(매직 바이트) 검증 — .php 등 위장 업로드(웹셸) 차단
    head = file_storage.stream.read(16)
    file_storage.stream.seek(0)
    detected = _detect_image_ext(head)
    if detected is None:
        return None, "이미지 파일이 아닙니다."

    # 3) 확장자와 실제 형식 일치 확인
    norm_ext = "jpg" if ext in ("jpg", "jpeg") else ext
    if detected != norm_ext:
        return None, "파일 확장자와 실제 형식이 일치하지 않습니다."

    # 4) 난수 파일명으로 저장 — 원본 파일명 신뢰 안 함(경로조작·덮어쓰기 방지)
    fname = secrets.token_hex(16) + "." + detected
    file_storage.save(os.path.join(current_app.config["UPLOAD_FOLDER"], fname))
    return fname, None


def _remove_image(fname):
    if not fname:
        return
    try:
        os.remove(os.path.join(current_app.config["UPLOAD_FOLDER"], fname))
    except OSError:
        pass


def _get_owned_product_or_403(product_id):
    """소유권 검증 — 남의 상품 조작(IDOR) 차단. 단, 관리자는 전 상품 관리 가능."""
    p = Product.query.get_or_404(product_id)
    u = current_user()
    if p.seller_id != u.id and not u.is_admin:
        abort(403)
    return p


# ---------- 라우트 ----------

@product_bp.route("/product/<int:product_id>")
def detail(product_id):
    p = Product.query.get_or_404(product_id)
    if p.status == "blocked":
        abort(404)   # 차단된 상품은 노출하지 않음 (신고 모듈 연동)
    return render_template("product_detail.html", p=p)


@product_bp.route("/product/new", methods=["GET", "POST"])
@login_required
def new():
    form = ProductForm()
    if form.validate_on_submit():
        fname, err = save_product_image(form.image.data)
        if err:
            flash(err, "danger")
            return render_template("product_form.html", form=form, mode="new")
        p = Product(
            seller_id=current_user().id,
            title=form.title.data.strip(),
            price=form.price.data,
            description=form.description.data or "",
            image_path=fname,
        )
        db.session.add(p)
        db.session.commit()
        flash("상품이 등록되었습니다.", "success")
        return redirect(url_for("product.detail", product_id=p.id))
    return render_template("product_form.html", form=form, mode="new")


@product_bp.route("/product/mine")
@login_required
def mine():
    products = (Product.query
                .filter_by(seller_id=current_user().id)
                .order_by(Product.created_at.desc())
                .all())
    return render_template("product_mine.html", products=products)


@product_bp.route("/product/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit(product_id):
    p = _get_owned_product_or_403(product_id)      # IDOR 방어
    form = ProductForm(obj=p)
    if form.validate_on_submit():
        p.title = form.title.data.strip()
        p.price = form.price.data
        p.description = form.description.data or ""
        # 이미지는 새로 올라온 경우에만 교체
        if form.image.data and form.image.data.filename:
            fname, err = save_product_image(form.image.data)
            if err:
                flash(err, "danger")
                return render_template("product_form.html", form=form, mode="edit", product=p)
            old = p.image_path
            p.image_path = fname
            _remove_image(old)
        db.session.commit()
        flash("상품이 수정되었습니다.", "success")
        return redirect(url_for("product.detail", product_id=p.id))
    return render_template("product_form.html", form=form, mode="edit", product=p)


@product_bp.route("/product/<int:product_id>/delete", methods=["POST"])
@login_required
def delete(product_id):
    p = _get_owned_product_or_403(product_id)      # IDOR 방어
    _remove_image(p.image_path)
    db.session.delete(p)
    db.session.commit()
    flash("상품이 삭제되었습니다.", "info")
    return redirect(url_for("product.mine"))


@product_bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    # send_from_directory는 '../' 경로 조작을 안전하게 차단
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
