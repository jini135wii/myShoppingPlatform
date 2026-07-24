"""마일스톤 2 (상품) 스모크 테스트.

실행: 프로젝트 루트에서
    python tests/test_product.py

검증: 등록/목록(사진+이름 액자 갤러리)/상세, 업로드 검증(위장·비허용 차단), IDOR(소유권) 방어, 이미지 서빙.
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
from models import db, User, Product

tmpdir = tempfile.mkdtemp()

# 1x1 투명 PNG (유효한 이미지)
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

def create_product(client, title, image_bytes=PNG_BYTES, filename="photo.png", price="1000"):
    return client.post("/product/new", data={
        "title": title, "price": price, "description": "설명",
        "image": (BytesIO(image_bytes), filename),
    }, content_type="multipart/form-data", follow_redirects=True)


# ---- 준비: alice, bob ----
alice = app.test_client()
register_and_login(alice, "alice")
bob = app.test_client()
register_and_login(bob, "bob")

# 1) 비로그인은 상품 등록 불가
anon = app.test_client()
r = anon.get("/product/new", follow_redirects=True)
check("비로그인 상품등록 차단", "로그인이 필요합니다" in r.get_data(as_text=True))

# 2) 유효 이미지로 상품 등록
r = create_product(alice, "빈티지 자전거")
check("상품 등록 성공", "상품이 등록되었습니다" in r.get_data(as_text=True))
with app.app_context():
    prod = Product.query.filter_by(title="빈티지 자전거").first()
    pid = prod.id
    saved_img = prod.image_path
check("이미지 난수 파일명 저장", saved_img and saved_img.endswith(".png") and "photo" not in saved_img)

# 3) 목록(액자 갤러리): 상품명 + 썸네일 노출, 가격은 상세에서만
r = anon.get("/")
body = r.get_data(as_text=True)
check("목록에 상품명 노출", "빈티지 자전거" in body)
check("목록에 썸네일(사진) 노출", f"/uploads/{saved_img}" in body)
check("목록에 가격 미노출", "1,000원" not in body)

# 3.5) 상품 검색 (제목·설명, ORM ilike → SQLi 안전)
r = anon.get("/?q=자전거")
check("검색: 일치 상품 노출", "빈티지 자전거" in r.get_data(as_text=True))
r = anon.get("/?q=없는상품키워드zzz")
body2 = r.get_data(as_text=True)
check("검색: 무결과 안내", "검색 결과가 없습니다" in body2)
check("검색: 무결과 시 상품 미노출", "빈티지 자전거" not in body2)
# SQLi 시도가 오류 없이 무결과 처리되는지
r = anon.get("/?q=' OR '1'='1")
check("검색: SQLi 문자열 안전 처리", r.status_code == 200 and "빈티지 자전거" not in r.get_data(as_text=True))

# 4) 상세는 가격·이미지 노출
r = anon.get(f"/product/{pid}")
body = r.get_data(as_text=True)
check("상세에 가격 노출", "1,000원" in body)
check("상세에 이미지 경로 노출", f"/uploads/{saved_img}" in body)

# 상세: 로그인 비소유자에게 '판매자에게 문의' 버튼 노출
r = bob.get(f"/product/{pid}")
check("상세: 판매자 문의 버튼(비소유자)", "판매자에게 문의" in r.get_data(as_text=True))

# 5) 업로드된 이미지 서빙
r = anon.get(f"/uploads/{saved_img}")
check("이미지 파일 서빙 200", r.status_code == 200 and r.data[:8] == PNG_BYTES[:8])

# 6) 확장자 위장 차단: .png 인데 실제로는 PHP 코드
r = create_product(alice, "위장상품", image_bytes=b"<?php system($_GET['c']); ?>",
                   filename="evil.png")
check("확장자 위장(매직바이트 불일치) 차단",
      "이미지 파일이 아닙니다" in r.get_data(as_text=True))

# 7) 비허용 확장자 차단: .php
r = create_product(alice, "웹셸", image_bytes=b"<?php ?>", filename="shell.php")
check("비허용 확장자 차단", "이미지 파일" in r.get_data(as_text=True))

# 위장/웹셸 상품이 실제로 DB에 안 들어갔는지
with app.app_context():
    check("위장 업로드 상품 미등록", Product.query.filter_by(title="위장상품").first() is None)

# 8) IDOR: bob은 alice의 상품을 삭제/수정할 수 없음
r = bob.post(f"/product/{pid}/delete")
check("IDOR 삭제 차단(403)", r.status_code == 403)
r = bob.get(f"/product/{pid}/edit")
check("IDOR 수정 차단(403)", r.status_code == 403)
with app.app_context():
    check("IDOR 시도 후 상품 유지", db.session.get(Product, pid) is not None)

# 9) 소유자는 수정 가능
r = alice.post(f"/product/{pid}/edit", data={
    "title": "빈티지 자전거(가격인하)", "price": "800", "description": "설명",
}, content_type="multipart/form-data", follow_redirects=True)
check("소유자 수정 성공", "상품이 수정되었습니다" in r.get_data(as_text=True))

# 10) 소유자는 삭제 가능
r = alice.post(f"/product/{pid}/delete", follow_redirects=True)
check("소유자 삭제 성공", "상품이 삭제되었습니다" in r.get_data(as_text=True))
with app.app_context():
    check("삭제 후 DB 제거", db.session.get(Product, pid) is None)

shutil.rmtree(tmpdir, ignore_errors=True)

print("\n=== RESULT ===")
failed = [n for n, ok in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
