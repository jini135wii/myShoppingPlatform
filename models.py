from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False, index=True)  # FR-1.5 중복 불가
    password_hash = db.Column(db.String(255), nullable=False)                     # [보안] 원문 미저장
    bio = db.Column(db.String(500), default="")
    status = db.Column(db.String(20), default="active", nullable=False)          # active | dormant
    report_count = db.Column(db.Integer, default=0, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw):
        # [보안] werkzeug 해싱 + 솔트 (pbkdf2)
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def is_dormant(self):
        return self.status == "dormant"


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    image_path = db.Column(db.String(255))
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="active", nullable=False)          # active | blocked
    report_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    seller = db.relationship("User", backref="products")


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    room = db.Column(db.String(60), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # NULL=전체 채팅
    content = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # FK가 2개(sender/receiver)라 명시적으로 지정
    sender = db.relationship("User", foreign_keys=[sender_id])


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_type = db.Column(db.String(20), nullable=False)                       # user | product
    target_id = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # [보안] 동일인이 같은 대상을 중복 신고해 카운트를 부풀리는 것 방지
    __table_args__ = (
        db.UniqueConstraint("reporter_id", "target_type", "target_id",
                            name="uq_one_report_per_target"),
    )


class Appeal(db.Model):
    """차단/휴면 조치에 대한 이의제기(소명). 관리자가 심사한다."""
    __tablename__ = "appeals"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    message = db.Column(db.String(1000), nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)         # pending | approved | rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    resolver_id = db.Column(db.Integer, db.ForeignKey("users.id"))               # 처리한 관리자

    user = db.relationship("User", foreign_keys=[user_id])


class Wallet(db.Model):
    """가상 포인트 지갑 (유저당 1개). 실제 화폐 아님 — 교육용 가상 포인트."""
    __tablename__ = "wallets"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    balance = db.Column(db.Integer, default=0, nullable=False)

    # [보안] 잔액 음수 방지 — DB 레벨 방어(응용 로직의 조건부 UPDATE와 이중 안전장치)
    __table_args__ = (db.CheckConstraint("balance >= 0", name="ck_wallet_nonneg"),)

    user = db.relationship("User")


class Transaction(db.Model):
    """포인트 이동 기록. sender_id=NULL 이면 시스템 지급(가입 보너스)."""
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount = db.Column(db.Integer, nullable=False)                                # 항상 > 0
    kind = db.Column(db.String(20), nullable=False, default="transfer")           # transfer | bonus
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])


class AdminLog(db.Model):
    """관리자 행위 감사 로그 — 누가·언제·무엇을 했는지 기록(부인 방지·추적)."""
    __tablename__ = "admin_logs"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(50), nullable=False)                # 예: 상품 차단, 회원 휴면
    target_type = db.Column(db.String(20))                           # user | product | message | report | appeal
    target_id = db.Column(db.Integer)                                # 대상 식별자(FK 아님: 삭제돼도 기록 보존)
    detail = db.Column(db.String(255))                               # 대상 이름 등 부가정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    admin = db.relationship("User", foreign_keys=[admin_id])
