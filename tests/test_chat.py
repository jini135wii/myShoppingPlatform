"""마일스톤 3 (실시간 채팅) 스모크 테스트.

실행: 프로젝트 루트에서
    python tests/test_chat.py

검증: WebSocket 인증, 전체 브로드캐스트, 1:1 방, 제3자 도청 차단,
      히스토리 XSS 이스케이프, 입력 검증, DB 저장.
"""
import os
import sys
import shutil
import tempfile
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, socketio
from models import db, User, Message

tmpdir = tempfile.mkdtemp()


class TestConfig:
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(tmpdir, "test.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=6)
    UPLOAD_FOLDER = os.path.join(tmpdir, "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
    REPORT_THRESHOLD = 5


app = create_app(TestConfig)

results = []
def check(name, cond):
    results.append((name, cond))
    print(("  ok " if cond else "FAIL ") + name)

def make_user(username, password="password123"):
    c = app.test_client()
    c.post("/register", data={"username": username, "password": password,
                              "confirm": password}, follow_redirects=True)
    c.post("/login", data={"username": username, "password": password},
           follow_redirects=True)
    return c

def got_message(received, content):
    return any(e["name"] == "receive_message" and e["args"][0]["content"] == content
               for e in received)

def got_any_message(received):
    return any(e["name"] == "receive_message" for e in received)


alice_http = make_user("alice")
bob_http = make_user("bob")
carol_http = make_user("carol")

with app.app_context():
    aid = User.query.filter_by(username="alice").first().id
    bid = User.query.filter_by(username="bob").first().id

dm = f"dm:{min(aid, bid)}_{max(aid, bid)}"

# 1) 비로그인 WebSocket 연결 거부
anon_http = app.test_client()
anon_sio = socketio.test_client(app, flask_test_client=anon_http)
check("비로그인 WebSocket 연결 거부", not anon_sio.is_connected())

# 2) 로그인 WebSocket 연결 성공
alice_sio = socketio.test_client(app, flask_test_client=alice_http)
bob_sio = socketio.test_client(app, flask_test_client=bob_http)
check("로그인 WebSocket 연결", alice_sio.is_connected() and bob_sio.is_connected())

# 3) 전체 채팅 브로드캐스트
alice_sio.emit("join", {"room": "global"})
bob_sio.emit("join", {"room": "global"})
alice_sio.get_received(); bob_sio.get_received()
alice_sio.emit("send_message", {"room": "global", "content": "안녕하세요 전체"})
check("전체 채팅 수신", got_message(bob_sio.get_received(), "안녕하세요 전체"))

# 4) 1:1 채팅 + 제3자 도청 차단
alice_sio.emit("join", {"room": dm})
bob_sio.emit("join", {"room": dm})
carol_sio = socketio.test_client(app, flask_test_client=carol_http)
carol_sio.emit("join", {"room": dm})           # 참여자 아님 → 서버가 입장 거부
alice_sio.get_received(); bob_sio.get_received(); carol_sio.get_received()
alice_sio.emit("send_message", {"room": dm, "content": "비밀 메시지"})
check("1:1 상대 수신", got_message(bob_sio.get_received(), "비밀 메시지"))
check("제3자 도청 차단", not got_any_message(carol_sio.get_received()))

# 5) DB 저장 및 receiver_id
with app.app_context():
    m = Message.query.filter_by(content="비밀 메시지").first()
    check("1:1 메시지 DB 저장", m is not None)
    check("1:1 receiver_id/room 설정", m.room == dm and m.receiver_id in (aid, bid))

# 6) XSS: 히스토리 페이지에서 스크립트 이스케이프
xss = "<script>alert(1)</script>"
alice_sio.emit("send_message", {"room": "global", "content": xss})
body = alice_http.get("/chat").get_data(as_text=True)
check("채팅 히스토리 XSS 이스케이프",
      "<script>alert(1)" not in body and "&lt;script&gt;" in body)

# 7) 빈/과길이 메시지 무시
bob_sio.get_received()
alice_sio.emit("send_message", {"room": "global", "content": "   "})
alice_sio.emit("send_message", {"room": "global", "content": "x" * 1001})
check("빈/과길이 메시지 무시", not got_any_message(bob_sio.get_received()))

# 8) 자기 자신과 DM 차단
check("자기 자신 DM 차단(400)", alice_http.get(f"/dm/{aid}").status_code == 400)

# 9) 비로그인 /chat 접근 차단
check("비로그인 /chat 차단",
      "로그인이 필요합니다" in anon_http.get("/chat", follow_redirects=True).get_data(as_text=True))

# 10) 쪽지함: 1:1 대화 상대 목록 (alice↔bob 대화 존재)
inbox = alice_http.get("/messages").get_data(as_text=True)
check("쪽지함에 대화 상대 노출", "bob" in inbox)
check("쪽지함 비로그인 차단",
      "로그인이 필요합니다" in anon_http.get("/messages", follow_redirects=True).get_data(as_text=True))

# 11) 채팅 Rate Limiting (스팸 방지): 윈도 내 5건 초과 차단
spammer_http = make_user("spammer")
spammer_sio = socketio.test_client(app, flask_test_client=spammer_http)
spammer_sio.emit("join", {"room": "global"})
bob_sio.get_received()                              # 수신 버퍼 비우기
for i in range(7):                                  # 빠르게 7건 전송
    spammer_sio.emit("send_message", {"room": "global", "content": f"spam{i}"})
spam_recv = sum(1 for e in bob_sio.get_received()
                if e["name"] == "receive_message" and e["args"][0]["content"].startswith("spam"))
check("채팅 rate limit: 5건까지만 전파", spam_recv == 5)

shutil.rmtree(tmpdir, ignore_errors=True)

print("\n=== RESULT ===")
failed = [n for n, ok in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
