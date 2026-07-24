from time import time

from flask import Blueprint, render_template, session, abort
from flask_socketio import emit, join_room

from models import db, User, Message
from helpers import login_required, current_user

chat_bp = Blueprint("chat", __name__)

GLOBAL_ROOM = "global"
MAX_LEN = 1000
HISTORY_LIMIT = 50

# 채팅 스팸 방지: 사용자별 최근 전송 시각 (윈도 내 최대 건수 제한)
MSG_RATE_MAX = 5
MSG_RATE_WINDOW = 3
_msg_times = {}


def _chat_rate_ok(uid):
    now = time()
    recent = [t for t in _msg_times.get(uid, []) if now - t < MSG_RATE_WINDOW]
    if len(recent) >= MSG_RATE_MAX:
        _msg_times[uid] = recent
        return False
    recent.append(now)
    _msg_times[uid] = recent
    return True


def dm_room(a, b):
    """두 유저 id를 정렬해 1:1 방 이름 생성 (항상 동일한 쌍→동일 방)."""
    lo, hi = sorted((int(a), int(b)))
    return f"dm:{lo}_{hi}"


def _parse_dm_members(room):
    """'dm:3_7' → (3, 7). 형식이 아니면 None."""
    if not isinstance(room, str) or not room.startswith("dm:"):
        return None
    try:
        a, b = room[3:].split("_")
        return int(a), int(b)
    except (ValueError, IndexError):
        return None


# ---------- HTTP 페이지 ----------

@chat_bp.route("/chat")
@login_required
def global_chat():
    messages = (Message.query.filter_by(room=GLOBAL_ROOM)
                .order_by(Message.created_at.desc())
                .limit(HISTORY_LIMIT).all())[::-1]
    return render_template("chat.html", room=GLOBAL_ROOM,
                           title="전체 채팅", messages=messages)


@chat_bp.route("/dm/<int:user_id>")
@login_required
def direct_chat(user_id):
    me = current_user()
    if user_id == me.id:
        abort(400)                       # 자기 자신과 DM 불가
    other = User.query.get_or_404(user_id)
    room = dm_room(me.id, other.id)
    messages = (Message.query.filter_by(room=room)
                .order_by(Message.created_at.desc())
                .limit(HISTORY_LIMIT).all())[::-1]
    return render_template("chat.html", room=room,
                           title=f"{other.username}님과의 1:1 채팅", messages=messages)


@chat_bp.route("/messages")
@login_required
def inbox():
    """1:1 대화 목록(쪽지함) — 대화를 쉽게 찾아 이어가도록."""
    me = current_user()
    msgs = (Message.query
            .filter(Message.receiver_id.isnot(None),
                    db.or_(Message.sender_id == me.id, Message.receiver_id == me.id))
            .order_by(Message.created_at.desc())
            .all())
    names = {u.id: u.username for u in User.query.all()}
    convos, seen = [], set()
    for m in msgs:                                  # 상대별 최신 메시지 1건만
        partner = m.receiver_id if m.sender_id == me.id else m.sender_id
        if partner in seen:
            continue
        seen.add(partner)
        convos.append({"id": partner, "username": names.get(partner, "?"),
                       "last": m.content, "at": m.created_at})
    return render_template("inbox.html", convos=convos)


# ---------- Socket.IO 이벤트 ----------
# 주의: socketio.init_app()은 매번 새 서버를 생성하므로, init_app 직후 매번 호출해
# 핸들러를 (그 서버에) 등록해야 한다. (중복 방지 가드를 두면 안 됨)
def register_chat_events(socketio):

    @socketio.on("connect")
    def on_connect():
        # [보안] WebSocket 인증: 로그인 세션 없는 접속 거부
        if not session.get("user_id"):
            return False

    @socketio.on("join")
    def on_join(data):
        uid = session.get("user_id")
        if not uid:
            return
        room = (data or {}).get("room")
        if room == GLOBAL_ROOM:
            join_room(GLOBAL_ROOM)
            return
        members = _parse_dm_members(room)
        # [보안] 1:1 방 접근 통제: 본인이 참여자인 방만 입장 가능 (제3자 도청 차단)
        if members and uid in members:
            join_room(room)

    @socketio.on("send_message")
    def on_send(data):
        uid = session.get("user_id")
        if not uid:
            return
        data = data or {}
        content = (data.get("content") or "").strip()
        if not content or len(content) > MAX_LEN:   # [보안] 입력 검증(빈 값/길이)
            return
        # [보안] 스팸 방지 — 사용자별 속도 제한(초과분은 본인에게만 안내)
        if not _chat_rate_ok(uid):
            emit("receive_message", {
                "sender": "시스템", "sender_id": 0,
                "content": "메시지를 너무 빠르게 보내고 있어요. 잠시 후 다시 시도해 주세요.",
                "created_at": "",
            })
            return
        room = data.get("room")

        receiver_id = None
        if room == GLOBAL_ROOM:
            pass
        else:
            members = _parse_dm_members(room)
            if not members or uid not in members:   # [보안] 참여자만 전송 가능
                return
            a, b = members
            receiver_id = b if uid == a else a

        user = db.session.get(User, uid)
        if user is None:
            return
        msg = Message(room=room, sender_id=uid, receiver_id=receiver_id, content=content)
        db.session.add(msg)
        db.session.commit()

        # content는 클라이언트에서 textContent로 삽입 → XSS 방어 (chat.js 참고)
        emit("receive_message", {
            "sender": user.username,
            "sender_id": uid,
            "content": content,
            "created_at": msg.created_at.strftime("%H:%M"),
        }, room=room)
