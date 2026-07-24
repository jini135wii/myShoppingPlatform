"""가상 포인트 지갑 (FR-7). 유저 간 포인트 송금 — 실제 화폐 아님(교육용).

보안 초점:
- 이체 원자성 + 경쟁조건(race) 방어: 잔액 이내일 때만 성공하는 **조건부 UPDATE**.
- IDOR 방어: 출금 계정은 항상 세션 유저(폼의 sender 신뢰 안 함).
- 입력 검증: 정수·양수만(WTForms), 자기 송금·미존재 수신자 차단.
"""
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, current_app)
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired, InputRequired, NumberRange

from models import db, User, Wallet, Transaction
from helpers import login_required, current_user

wallet_bp = Blueprint("wallet", __name__)


def get_wallet(user):
    """지갑 조회, 없으면 생성하며 가입 보너스 지급(기존 계정도 최초 접근 시 1회)."""
    w = Wallet.query.filter_by(user_id=user.id).first()
    if w is None:
        bonus = current_app.config.get("SIGNUP_BONUS", 0)
        w = Wallet(user_id=user.id, balance=bonus)
        db.session.add(w)
        if bonus > 0:
            db.session.add(Transaction(sender_id=None, receiver_id=user.id,
                                       amount=bonus, kind="bonus"))
        db.session.commit()
    return w


class TransferForm(FlaskForm):
    recipient = StringField("받는 사람(아이디)", validators=[DataRequired()])
    amount = IntegerField("보낼 포인트", validators=[
        InputRequired(), NumberRange(min=1, message="1 이상의 정수를 입력하세요."),
    ])
    submit = SubmitField("송금")


@wallet_bp.route("/wallet")
@login_required
def wallet():
    me = current_user()
    w = get_wallet(me)
    txs = (Transaction.query
           .filter((Transaction.sender_id == me.id) | (Transaction.receiver_id == me.id))
           .order_by(Transaction.created_at.desc())
           .limit(50).all())
    names = {u.id: u.username for u in User.query.all()}
    form = TransferForm()
    to = request.args.get("to", "")
    if to:
        form.recipient.data = to                      # 프로필의 "송금하기"에서 넘어온 값 프리필
    return render_template("wallet.html", balance=w.balance, txs=txs,
                           names=names, form=form, me_id=me.id)


@wallet_bp.route("/wallet/transfer", methods=["POST"])
@login_required
def transfer():
    me = current_user()
    form = TransferForm()
    if not form.validate_on_submit():                 # 정수·양수·CSRF 검증
        for field in form:
            for err in field.errors:
                flash(err, "danger")
        return redirect(url_for("wallet.wallet"))

    amount = form.amount.data
    receiver = User.query.filter_by(username=form.recipient.data.strip()).first()
    if receiver is None:
        flash("받는 사람을 찾을 수 없습니다.", "danger")
        return redirect(url_for("wallet.wallet"))
    if receiver.id == me.id:
        flash("자기 자신에게는 송금할 수 없습니다.", "danger")
        return redirect(url_for("wallet.wallet"))

    get_wallet(me)                                     # 양쪽 지갑 보장
    get_wallet(receiver)

    # [보안] 원자적 출금 — 잔액이 충분할 때만 차감 성공(동시 요청에도 음수 불가).
    # 영향받은 행이 0이면 잔액 부족 → 크레딧하지 않고 롤백.
    debited = (Wallet.query
               .filter(Wallet.user_id == me.id, Wallet.balance >= amount)
               .update({Wallet.balance: Wallet.balance - amount},
                       synchronize_session=False))
    if not debited:
        db.session.rollback()
        flash("잔액이 부족합니다.", "danger")
        return redirect(url_for("wallet.wallet"))

    Wallet.query.filter_by(user_id=receiver.id).update(
        {Wallet.balance: Wallet.balance + amount}, synchronize_session=False)
    db.session.add(Transaction(sender_id=me.id, receiver_id=receiver.id,
                               amount=amount, kind="transfer"))
    db.session.commit()                                # 차감·입금·기록이 하나의 트랜잭션
    flash(f"{receiver.username}님에게 {amount:,}포인트를 송금했습니다.", "success")
    return redirect(url_for("wallet.wallet"))
