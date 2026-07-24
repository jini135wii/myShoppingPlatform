import os

from flask import Flask, render_template, request
from flask_wtf import CSRFProtect
from flask_socketio import SocketIO

from config import Config
from models import db, Product
from helpers import current_user

# 확장 객체 (앱 팩토리에서 init)
csrf = CSRFProtect()
socketio = SocketIO(async_mode="threading")   # 추가 의존성 없이 스레딩 모드


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # 확장 초기화
    db.init_app(app)
    csrf.init_app(app)          # [보안] 전 POST 폼에 CSRF 토큰 강제
    socketio.init_app(app)

    # 블루프린트 등록
    from blueprints.auth import auth_bp
    from blueprints.product import product_bp
    from blueprints.chat import chat_bp, register_chat_events
    from blueprints.report import report_bp
    from blueprints.admin import admin_bp
    from blueprints.appeal import appeal_bp
    from blueprints.wallet import wallet_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(appeal_bp)
    app.register_blueprint(wallet_bp)
    register_chat_events(socketio)       # Socket.IO 이벤트 핸들러 등록

    # 템플릿 어디서나 current_user 사용 가능하게
    @app.context_processor
    def inject_user():
        return {"current_user": current_user()}

    @app.route("/")
    def index():
        # FR-2.6(설계결정): 목록은 사진+상품명 액자 갤러리, 가격 등 상세는 클릭 시
        q = request.args.get("q", "").strip()
        query = Product.query.filter_by(status="active")
        if q:
            # [보안] ORM ilike → 파라미터 바인딩(문자열 조합 없음, SQLi 안전)
            like = f"%{q}%"
            query = query.filter(db.or_(Product.title.ilike(like),
                                        Product.description.ilike(like)))
        products = query.order_by(Product.created_at.desc()).all()
        return render_template("index.html", products=products, q=q)

    # [보안] 커스텀 에러 페이지 — 스택트레이스 등 내부 정보 노출 방지
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()               # 손상된 DB 세션 정리
        return render_template("errors/500.html"), 500

    with app.app_context():
        db.create_all()

    return app


app = create_app()


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    # 로컬 개발/교육용 실행. 실제 배포 시에는 gunicorn 등 프로덕션 서버 사용 권장.
    run_kwargs = dict(host=os.environ.get("HOST", "127.0.0.1"),
                      port=int(os.environ.get("PORT", "5000")),
                      debug=debug, allow_unsafe_werkzeug=True)
    # USE_TLS=1 이면 자체서명 인증서로 https 제공 → WebSocket이 wss로 승격(로컬 검증용).
    if os.environ.get("USE_TLS") == "1":
        run_kwargs["ssl_context"] = (os.environ.get("TLS_CERT", "cert.pem"),
                                     os.environ.get("TLS_KEY", "key.pem"))
    socketio.run(app, **run_kwargs)
