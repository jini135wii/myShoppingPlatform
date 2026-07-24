"""마일스톤 5 (관리자 패널 + 이의제기) 스모크 테스트.

실행: 프로젝트 루트에서
    python tests/test_admin.py

검증: 관리자 권한 분리(비관리자 403), 회원/상품 관리, 이의제기(본인인증·세션 미발급),
      관리자 승인 시 사면(휴면 해제→재로그인 가능).
"""
import os
import sys
import base64
import shutil
import tempfile
from io import BytesIO
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from models import db, User, Product, Appeal, Report, Message, AdminLog

tmpdir = tempfile.mkdtemp()

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+P+/HgAFhAJ/wlseKgAAAABJRU5ErkJggg=="
)


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
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    REPORT_THRESHOLD = 5


app = create_app(TestConfig)

results = []
def check(name, cond):
    results.append((name, cond))
    print(("  ok " if cond else "FAIL ") + name)

def register_and_login(client, username, password="password123"):
    client.post("/register", data={"username": username, "password": password,
                                   "confirm": password}, follow_redirects=True)
    client.post("/login", data={"username": username, "password": password},
                follow_redirects=True)

def create_product(client, title):
    client.post("/product/new", data={
        "title": title, "price": "1000", "description": "설명",
        "image": (BytesIO(PNG_BYTES), "photo.png"),
    }, content_type="multipart/form-data", follow_redirects=True)
    with app.app_context():
        return Product.query.filter_by(title=title).first().id

def do_report(client, target_type, target_id, reason="불량"):
    return client.post("/report", data={"target_type": target_type,
        "target_id": target_id, "reason": reason}, follow_redirects=True)

def uid(username):
    with app.app_context():
        return User.query.filter_by(username=username).first().id

def ustatus(username):
    with app.app_context():
        return User.query.filter_by(username=username).first().status

def pstatus(pid):
    with app.app_context():
        return db.session.get(Product, pid).status


# ---- 준비 ----
admin = app.test_client(); register_and_login(admin, "admin")
with app.app_context():                       # admin 승격
    a = User.query.filter_by(username="admin").first(); a.is_admin = True; db.session.commit()
normal = app.test_client(); register_and_login(normal, "normal")
victim = app.test_client(); register_and_login(victim, "victim")

reporters = []
for i in range(5):
    c = app.test_client(); register_and_login(c, f"rep{i}"); reporters.append(c)

pid = create_product(normal, "노멀상품")

# 1) [보안] 권한 분리 — 비관리자 403
check("비관리자 /admin 403", normal.get("/admin/").status_code == 403)
check("비관리자 회원관리 403", normal.get("/admin/users").status_code == 403)
r = normal.post(f"/admin/products/{pid}/delete")
check("비관리자 상품삭제 403", r.status_code == 403)

# 2) 비로그인 → 로그인 리다이렉트
anon = app.test_client()
r = anon.get("/admin", follow_redirects=True)
check("비로그인 /admin 로그인유도", "로그인이 필요합니다" in r.get_data(as_text=True))

# 3) 관리자 화면 접근
check("관리자 대시보드 200", "관리자 대시보드" in admin.get("/admin/").get_data(as_text=True))
check("관리자 회원목록에 유저 노출", "normal" in admin.get("/admin/users").get_data(as_text=True))
check("관리자 상품목록에 상품 노출", "노멀상품" in admin.get("/admin/products").get_data(as_text=True))

# 4) 회원 상태 관리 (휴면/활성화)
admin.post(f"/admin/users/{uid('normal')}/status", data={"action": "dormant"}, follow_redirects=True)
check("관리자 휴면 처리", ustatus("normal") == "dormant")
admin.post(f"/admin/users/{uid('normal')}/status", data={"action": "activate"}, follow_redirects=True)
check("관리자 활성화 처리", ustatus("normal") == "active")

# 5) [보안] 관리자 자기 자신 잠금 방지
r = admin.post(f"/admin/users/{uid('admin')}/status", data={"action": "dormant"}, follow_redirects=True)
check("관리자 본인 잠금 차단", "본인 계정" in r.get_data(as_text=True) and ustatus("admin") == "active")

# 6) 상품 차단/해제
admin.post(f"/admin/products/{pid}/status", data={"action": "block"}, follow_redirects=True)
check("관리자 상품 차단", pstatus(pid) == "blocked")
check("차단 상품 목록 숨김", "노멀상품" not in anon.get("/").get_data(as_text=True))
admin.post(f"/admin/products/{pid}/status", data={"action": "unblock"}, follow_redirects=True)
check("관리자 차단 해제", pstatus(pid) == "active")

# ---- 이의제기(소명) ----
# victim을 5회 신고 → 휴면
vid = uid("victim")
for c in reporters:
    do_report(c, "user", vid)
check("신고 누적으로 휴면", ustatus("victim") == "dormant")

# 신고 내역이 원시 id가 아니라 이름으로 표시되는지
rbody = admin.get("/admin/reports").get_data(as_text=True)
check("신고내역에 신고자 이름 노출", "rep0" in rbody)
check("신고내역에 대상 이름 노출", "victim" in rbody)
check("신고내역 원시 'user #' 미노출", "user #" not in rbody)

# 7) 공개 이의제기 폼
ap = app.test_client()
check("이의제기 폼 200", "이의제기" in ap.get("/appeal").get_data(as_text=True))

# 8) [보안] 잘못된 자격증명 거부 (열거 방지)
r = ap.post("/appeal", data={"username": "victim", "password": "wrong",
    "message": "억울"}, follow_redirects=True)
check("잘못된 비번 이의제기 거부", "올바르지 않습니다" in r.get_data(as_text=True))
with app.app_context():
    check("거부 시 이의제기 미생성", Appeal.query.count() == 0)

# 9) 정상 이의제기 접수 (세션은 발급되지 않음)
r = ap.post("/appeal", data={"username": "victim", "password": "password123",
    "message": "저는 정상 거래만 했습니다"}, follow_redirects=True)
check("이의제기 접수", "접수되었습니다" in r.get_data(as_text=True))
with app.app_context():
    check("이의제기 1건 생성", Appeal.query.filter_by(user_id=vid, status="pending").count() == 1)
check("휴면 유지(승인 전)", ustatus("victim") == "dormant")
r = ap.get("/mypage", follow_redirects=True)          # 세션 미발급 확인
check("이의제기는 로그인 아님", "로그인이 필요합니다" in r.get_data(as_text=True))

# 10) 중복(대기) 신청 차단
r = ap.post("/appeal", data={"username": "victim", "password": "password123",
    "message": "다시요"}, follow_redirects=True)
check("중복 이의제기 차단", "검토 중" in r.get_data(as_text=True))

# 11) 관리자 승인 → 사면(휴면 해제) → 재로그인 가능
with app.app_context():
    apid = Appeal.query.filter_by(user_id=vid).first().id
admin.post(f"/admin/appeals/{apid}/resolve", data={"action": "approve"}, follow_redirects=True)
check("승인 후 계정 활성화", ustatus("victim") == "active")
with app.app_context():
    check("승인 후 신고카운트 0", User.query.filter_by(username="victim").first().report_count == 0)
fresh = app.test_client()
r = fresh.post("/login", data={"username": "victim", "password": "password123"},
               follow_redirects=True)
check("사면 후 재로그인 성공", "환영합니다" in r.get_data(as_text=True))

# 12) 로그인 상태 상품 이의제기 (재인증 없이) → 승인 시 차단 해제
admin.post(f"/admin/products/{pid}/status", data={"action": "block"}, follow_redirects=True)
gbody = normal.get("/appeal").get_data(as_text=True)
check("로그인 시 자격증명란 숨김", 'name="password"' not in gbody)
r = normal.post("/appeal", data={"message": "정상 상품입니다"}, follow_redirects=True)
check("로그인 상품 이의제기 접수", "접수되었습니다" in r.get_data(as_text=True))
with app.app_context():
    apid2 = Appeal.query.filter_by(user_id=uid("normal"), status="pending").first().id
admin.post(f"/admin/appeals/{apid2}/resolve", data={"action": "approve"}, follow_redirects=True)
check("승인 후 상품 차단 해제", pstatus(pid) == "active")

# 13) 잘못된 action은 400
r = admin.post(f"/admin/users/{uid('normal')}/status", data={"action": "evil"})
check("잘못된 관리 action 400", r.status_code == 400)

# 14) 채팅 메시지 관리 (조회·삭제) — 전체 채팅만 대상
with app.app_context():
    m = Message(room="global", sender_id=uid("normal"), content="관리대상메시지")
    db.session.add(m); db.session.commit(); mid = m.id
check("채팅 관리에 메시지 노출", "관리대상메시지" in admin.get("/admin/messages").get_data(as_text=True))
check("비관리자 채팅관리 403", normal.get("/admin/messages").status_code == 403)
admin.post(f"/admin/messages/{mid}/delete", follow_redirects=True)
with app.app_context():
    check("메시지 삭제됨", db.session.get(Message, mid) is None)

# 14b) [보안/프라이버시] 1:1 DM은 관리자도 열람·삭제 불가
n_id, v_id = uid("normal"), uid("victim")
dm_room = f"dm:{min(n_id, v_id)}_{max(n_id, v_id)}"
with app.app_context():
    dm = Message(room=dm_room, sender_id=n_id, receiver_id=v_id, content="비공개DM내용")
    db.session.add(dm); db.session.commit(); dm_id = dm.id
mgmt_body = admin.get("/admin/messages").get_data(as_text=True)
check("관리자 채팅관리에 DM 미노출", "비공개DM내용" not in mgmt_body)
r = admin.post(f"/admin/messages/{dm_id}/delete", follow_redirects=True)
check("관리자 DM 삭제 시도 403", r.status_code == 403)
with app.app_context():
    check("DM 레코드 유지(삭제 안 됨)", db.session.get(Message, dm_id) is not None)

# 15) 신고 개별 삭제
with app.app_context():
    rep = Report(reporter_id=uid("rep0"), target_type="user", target_id=uid("normal"), reason="테스트신고")
    db.session.add(rep); db.session.commit(); rid = rep.id
admin.post(f"/admin/reports/{rid}/delete", follow_redirects=True)
with app.app_context():
    check("신고 삭제됨", db.session.get(Report, rid) is None)

# 16) 관리자 권한 부여/해제
admin.post(f"/admin/users/{uid('normal')}/role", data={"action": "promote"}, follow_redirects=True)
with app.app_context():
    check("관리자 권한 부여", User.query.filter_by(username="normal").first().is_admin)
admin.post(f"/admin/users/{uid('normal')}/role", data={"action": "demote"}, follow_redirects=True)
with app.app_context():
    check("관리자 권한 해제", not User.query.filter_by(username="normal").first().is_admin)

# 17) [보안] 본인 관리자 권한 해제 차단
r = admin.post(f"/admin/users/{uid('admin')}/role", data={"action": "demote"}, follow_redirects=True)
check("본인 관리자 해제 차단", "본인의 관리자 권한" in r.get_data(as_text=True))

# 18) 관리자 타인 상품 수정 (소유권 우회 허용)
admin.post(f"/product/{pid}/edit", data={"title": "관리자수정", "price": "500", "description": "x"},
           content_type="multipart/form-data", follow_redirects=True)
with app.app_context():
    check("관리자 타인 상품 수정", db.session.get(Product, pid).title == "관리자수정")

# 19) 회원 삭제 연쇄(상품·메시지 정리) + 본인 삭제 차단
victim2 = app.test_client(); register_and_login(victim2, "victim2")
pid2 = create_product(victim2, "빅텀2상품")
with app.app_context():
    db.session.add(Message(room="global", sender_id=uid("victim2"), content="빅텀2글")); db.session.commit()
v2id = uid("victim2")
r = admin.post(f"/admin/users/{uid('admin')}/delete", follow_redirects=True)
check("본인 삭제 차단", "본인 계정은 삭제" in r.get_data(as_text=True))
admin.post(f"/admin/users/{v2id}/delete", follow_redirects=True)
with app.app_context():
    check("회원 삭제됨", User.query.filter_by(username="victim2").first() is None)
    check("회원 상품 연쇄삭제", db.session.get(Product, pid2) is None)
    check("회원 메시지 연쇄삭제", Message.query.filter_by(sender_id=v2id).count() == 0)

# 20) 감사 로그 — 관리 행위 기록·조회
lbody = admin.get("/admin/logs").get_data(as_text=True)
check("감사로그: 상품 차단 기록", "상품 차단" in lbody)
check("감사로그: 이의제기 승인 기록", "이의제기 승인" in lbody)
check("감사로그: 회원 삭제 기록", "회원 삭제" in lbody)
check("비관리자 감사로그 403", normal.get("/admin/logs").status_code == 403)
with app.app_context():
    check("감사로그 DB 적재", AdminLog.query.count() > 0)
    check("감사로그에 관리자 id 기록",
          AdminLog.query.filter_by(admin_id=uid("admin")).count() > 0)

shutil.rmtree(tmpdir, ignore_errors=True)

print("\n=== RESULT ===")
failed = [n for n, ok in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
