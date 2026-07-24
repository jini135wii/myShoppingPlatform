# Tiny Second-hand Shopping Platform

작은 중고거래 웹 플랫폼. 회원·상품·실시간 채팅·신고/차단·관리자·가상 포인트 지갑 기능을 제공하며, **보안 약점 최소화**를 핵심 목표로 개발합니다.

- 기술 스택: **Python · Flask · Flask-SocketIO · SQLite · Jinja2**

## 문서 (`docs/`)

| 파일 | 내용 |
|------|------|
| [`REPORT.md`](docs/REPORT.md) | 개발 보고서 — 요구사항 분석 → 시스템 설계 → 보안 설계 → 구현 → 테스트 → 유지보수 전 과정 |
| [`보안_체크리스트.md`](docs/보안_체크리스트.md) | 과제 제공 보안 체크리스트(21항목) ↔ 실제 구현·테스트 대조표 |
| [`보안_통제_점검표.md`](docs/보안_통제_점검표.md) | 자체 점검한 보안 통제 목록(카테고리별 위협·방어·검증 매핑) |
| [`과제_요구사항.md`](docs/과제_요구사항.md) | 원본 과제 요구사항(변경 없이 보존) |

## 구현 현황

| 영역 | 기능 | 상태 |
|------|------|------|
| 회원 | 회원가입 · 로그인/로그아웃 · 마이페이지(소개글·비번, **변경 시 재인증**) · 공개 프로필 · 아이디 중복 방지 | ✅ |
| 상품 | 등록 · 내 상품 관리(수정/삭제) · 목록(액자 갤러리)/상세 · 사진 업로드 · **검색**(제목·설명) | ✅ |
| 채팅 | 전체 채팅 · 1:1 채팅(Socket.IO 실시간) · **쪽지함**(대화 목록) · 스팸 방지(rate limit) | ✅ |
| 신고/차단 | 상품·유저 신고/사유 · 중복신고 방지 · 임계치 도달 시 자동 차단·휴면 | ✅ |
| 관리자 | 회원·상품·전체채팅·신고·이의제기 관리(**1:1 DM은 프라이버시 보호로 열람 제외**) · 권한 분리(403) · **감사 로그** | ✅ |
| 이의제기 | 차단/휴면 대상의 소명 접수(본인 인증) → 관리자 승인 시 사면 | ✅ |
| 가상 포인트 지갑 | 가입 보너스 지급 · 유저 간 송금(원자적 처리, 실제 화폐 아님) | ✅ |

## 환경 설정 및 실행 방법

### 1. Requirements
- **Python 3.10 이상** (미설치 시 설치: https://www.python.org/downloads/)
- Debian/Ubuntu 계열은 `venv` 모듈이 별도 패키지로 빠져 있을 수 있습니다. 아래 설치 시 오류가 나면 먼저 설치하세요:
  ```bash
  sudo apt install python3-venv
  ```
- `openssl` — WSS(HTTPS) 실행 검증 시에만 필요(선택)

### 2. 설치
```bash
git clone https://github.com/jini135wii/myShoppingPlatform.git
cd myShoppingPlatform

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 환경 변수 설정

**`.env`가 왜 필요한가**: `SECRET_KEY` 같은 비밀값과 환경별 설정은 코드에 하드코딩하지 않고 `.env`로 분리해 git에 올리지 않습니다. `.env.example`은 어떤 변수가 필요한지 보여주는 템플릿이고, `.env`는 그걸 복사해 실제 값을 채운 파일입니다.

`.env.example`을 `.env`로 복사하고 `SECRET_KEY`를 무작위 값으로 채웁니다(한 번에 실행):
```bash
cp .env.example .env && sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')/" .env
```
> macOS(BSD sed)에서는 `sed -i ''` 형태가 필요합니다: `sed -i '' "s/.../"`.

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `SECRET_KEY` | 세션 서명 키 (필수, 미설정 시 실행마다 무작위 생성) | - |
| `COOKIE_SECURE` | HTTPS 배포 시 `1` (쿠키 Secure 플래그) | `0` |
| `FLASK_DEBUG` | 개발 모드 | `1` |
| `REPORT_THRESHOLD` | 신고 임계치(상품 차단/유저 휴면) | `5` |
| `SIGNUP_BONUS` | 가입 시 지급하는 가상 포인트 보너스 | `10000` |
| `LOGIN_MAX_FAILURES` | 로그인 실패 허용 횟수(초과 시 쿨다운) | `5` |
| `LOGIN_FAIL_WINDOW` | 로그인 실패 집계 윈도(초) | `300` |
| `HOST` | 바인딩 호스트 (예: 외부 접속 허용 시 `0.0.0.0`) | `127.0.0.1` |
| `PORT` | 바인딩 포트 | `5000` |
| `USE_TLS` | `1`이면 자체서명 인증서(`cert.pem`/`key.pem`)로 HTTPS/WSS 실행(로컬 검증용) | `0` |

### 4. 실행

두 가지 접속 방식이 있습니다. 평소 개발·과제 확인용은 **HTTP**로 충분하고, **HTTPS/WSS**는 통신 암호화(TLS)를 로컬에서 직접 검증해보고 싶을 때만 사용합니다.

| | 접속 URL | 용도 |
|---|---|---|
| **HTTP (기본)** | `http://127.0.0.1:5000` | 평소 실행·개발. WebSocket도 `ws://`(평문)로 연결됨 |
| **HTTPS/WSS (선택)** | `https://127.0.0.1:5000` | 자체서명 인증서로 TLS 암호화 실행. WebSocket이 `wss://`로 업그레이드됨(암호화 검증용) |

**HTTP로 실행 (기본):**
```bash
python app.py
```
→ 브라우저에서 http://127.0.0.1:5000 접속

**HTTPS/WSS로 실행 (선택, 로컬 암호화 검증용):**
```bash
openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365 -subj "/CN=localhost"
USE_TLS=1 python app.py
```
→ https://127.0.0.1:5000 접속(자체서명 인증서 경고는 "고급 → 계속 진행"). 채팅 접속 시 WebSocket이 `wss://`로 업그레이드되는 것을 개발자도구(Network 탭)에서 확인할 수 있습니다. 운영 배포 시에는 이렇게 자체서명 인증서를 쓰는 대신, 리버스프록시(Nginx 등)에서 TLS를 종단하는 방식을 권장합니다.

> DB(`app.db`)는 최초 실행 시 자동 생성됩니다.
> 실제 배포 시에는 `gunicorn` 등 프로덕션 WSGI 서버 사용을 권장합니다.

### 5. 관리자 계정 만들기
관리자가 한 명도 없는 초기 상태에서는 관리자 화면 자체에 아무도 들어갈 수 없으므로, **최초 관리자**는 스크립트로 부여합니다.
```bash
./venv/bin/python tools/make_admin.py <username>
```
이후 추가 관리자 임명은 **관리자 화면(회원 관리 → 관리자지정/해제)에서 UI로 가능**합니다(`/admin/users`). 스크립트는 최초 부트스트랩 용도입니다.
DB 내용을 직접 조회하려면:
```bash
./venv/bin/python tools/dbview.py            # 전체 테이블
./venv/bin/python tools/dbview.py users      # 특정 테이블
```

### 6. 데이터베이스 초기화
⚠️ 아래 방법은 모두 **데이터를 되돌릴 수 없이 삭제**합니다. 실행 전 필요한 데이터가 없는지 확인하세요.

**방법 A — 파일째로 삭제 후 재생성 (가장 간단, 완전 초기화)**
```bash
rm app.db
python app.py     # 실행 시 create_all()이 빈 스키마를 자동 재생성
```
계정도 전부 사라지므로, 재가입 후 `tools/make_admin.py`로 관리자를 다시 만들어야 합니다.

**방법 B — 스키마는 유지하고 데이터(행)만 비우기**
```bash
./venv/bin/python -c "
from app import app, db
with app.app_context():
    for t in reversed(db.metadata.sorted_tables):
        db.session.execute(t.delete())
    db.session.commit()
    print('전체 테이블 데이터 삭제 완료')
"
```
업로드된 이미지 파일은 자동으로 지워지지 않으므로, 필요하면 `uploads/` 폴더도 함께 비우세요:
```bash
rm -f uploads/*.png uploads/*.jpg uploads/*.jpeg uploads/*.gif uploads/*.webp
```

> `tests/`의 자동화 테스트는 매번 별도의 임시 DB를 생성·삭제하므로 위 초기화와 무관하게 항상 독립적으로 동작합니다.

## 보안 설계 요약
비밀번호 해싱(scrypt+salt), CSRF 토큰, 세션 쿠키 보안 플래그, 세션 고정 방어, **로그인 타이밍 사이드채널 방지**(더미 해시로 응답시간 균일화), 로그인 시도 제한(브루트포스 완화), XSS 자동 이스케이프, SQL 인젝션 방어(ORM), 사용자 열거 방지, **파일 업로드 검증**(매직바이트+난수 파일명), **IDOR 방어**(소유권 검증), **WebSocket 인증·1:1 방 접근 통제·채팅 스팸 방지**, **관리자 권한 분리(403)·감사 로그**, **이의제기 인증 분리**(휴면 우회 로그인 차단), **가상 지갑 경쟁조건/이중지불 방어**(조건부 UPDATE), 커스텀 에러 페이지(403/404/500) 등을 적용합니다.

상세 위협 모델·발견한 취약점과 수정 내역, 체크리스트 대조는 위 [문서](#문서-docs) 표를 참고하세요.

## 테스트
```bash
./venv/bin/python tests/test_auth.py       # 인증 15건
./venv/bin/python tests/test_product.py    # 상품 23건
./venv/bin/python tests/test_chat.py       # 채팅 14건
./venv/bin/python tests/test_report.py     # 신고/차단 20건
./venv/bin/python tests/test_admin.py      # 관리자/이의제기 53건
./venv/bin/python tests/test_wallet.py     # 가상 지갑 22건
./venv/bin/python tests/test_security.py   # 보안 집중 16건
```
전체 **163/163 통과**. 상세 및 발견/수정 내역은 [`docs/REPORT.md`](docs/REPORT.md) §5를 참고하세요.
