# Tiny Second-hand Shopping Platform — 개발 보고서

> 작은 중고거래 플랫폼 개발 전 과정 보고서
> 작성자: 김진겸[33반]

---

## 0. 문서 개요

| 항목 | 내용 |
|------|------|
| 프로젝트명 | Tiny Second-hand Shopping Platform |
| 목적 | 중고거래 웹 플랫폼 구현 + 보안 약점 최소화 및 문서화 |
| 기술 스택 | Python · Flask · Flask-SocketIO · SQLite · Jinja2 (서버 렌더링) |
| 저장소 | https://github.com/jini135wii/myShoppingPlatform |
| 실행 방법 | 루트 `README.md` 참고 |

이 보고서는 **요구사항 분석 → 시스템 설계 → 보안 설계 → 구현 → 테스트/체크리스트 → 유지보수** 순서로 개발 전 과정을 기록한다. 각 단계는 실제 구현이 진행됨에 따라 채워진다. `TODO` 표시는 구현 후 작성 예정 항목이다.

---

## 1. 요구사항 분석

### 1.1 기능 요구사항 (Functional Requirements)

| ID | 요구사항 | 출처 | 우선순위 |
|----|----------|------|----------|
| **FR-1** | **회원 관리** | | |
| FR-1.1 | 회원가입 페이지 및 계정 생성 | README | 필수 |
| FR-1.2 | 로그인 / 로그아웃 | README | 필수 |
| FR-1.3 | 사용자 공개 프로필 조회 | README | 필수 |
| FR-1.4 | 마이페이지: 소개글·비밀번호 수정 | README | 필수 |
| FR-1.5 | 아이디(username) 중복 불가 | README | 필수 |
| FR-1.6 | 사용자 정보 DB 저장 | README | 필수 |
| **FR-2** | **상품 관리** | | |
| FR-2.1 | 상품 등록 페이지 | README | 필수 |
| FR-2.2 | 내가 등록한 상품 조회·관리 | README | 필수 |
| FR-2.3 | 상품명·가격·사진 표시 | README | 필수 |
| FR-2.4 | 등록 상품은 누구나 열람 가능 | README | 필수 |
| FR-2.5 | 상품 정보 DB 저장 | README | 필수 |
| FR-2.6 | 목록은 **이름만** 표시 → 클릭 시 상세 페이지 | README | 필수 |
| FR-2.7 | 상품 검색(제목·설명) | 확장 | 선택 |
| **FR-3** | **실시간 소통(채팅)** | | |
| FR-3.1 | 전체 유저 공용 채팅 | README | 필수 |
| FR-3.2 | 1:1 (유저 간) 채팅 | README | 필수 |
| **FR-4** | **신고 / 차단** | | |
| FR-4.1 | 불량 상품·사용자 신고 | README | 필수 |
| FR-4.2 | 신고 시 사유 작성 | README | 필수 |
| FR-4.3 | N회 이상 신고된 상품 자동 차단 | README | 필수 |
| FR-4.4 | N회 이상 신고된 유저 휴면 전환 | README | 필수 |
| **FR-5** | **관리자 (확장)** | | |
| FR-5.1 | 관리자 대시보드 + 회원·상품·신고 조회 | 확장 | 선택 |
| FR-5.2 | 회원 휴면/활성화, 상품 차단/해제/삭제 | 확장 | 선택 |
| **FR-6** | **이의제기 (확장)** | | |
| FR-6.1 | 차단/휴면 대상의 소명 접수 (본인 인증) | 확장 | 선택 |
| FR-6.2 | 관리자 이의제기 심사 (승인=사면 / 반려) | 확장 | 선택 |
| **FR-7** | **가상 포인트 지갑 (확장)** | | |
| FR-7.1 | 회원별 포인트 잔액(지갑) | 확장 | 선택 |
| FR-7.2 | 잔액·거래내역 조회 | 확장 | 선택 |
| FR-7.3 | 가입 보너스 지급 | 확장 | 선택 |
| FR-7.4 | 유저 간 포인트 송금 | 확장 | 선택 |

> **정책 기본값**: 신고 임계치 = **5회** (상품 차단·유저 휴면 공통). 근거는 §2.5 참조. 가입 보너스 = **10,000P**(`SIGNUP_BONUS`, 가상 포인트).
>
> **설계 결정(FR-2.6)**: 과제 원문은 목록에 "이름만" 표시이나, 사용자 요청으로 목록을 **사진+상품명 액자(gallery) 구성**으로 변경. 단, **가격·설명·판매자 등 상세 정보는 목록에 노출하지 않고 클릭 시 상세 페이지에서만** 제공하여 "목록=가벼운 미리보기, 상세는 클릭"이라는 원문 취지는 유지한다. (구현 §2.3·§4.2, 검증 TC-11)

### 1.2 비기능 요구사항 (Non-Functional Requirements)

| ID | 항목 | 내용 |
|----|------|------|
| NFR-1 | **보안** | 과제 핵심. OWASP Top 10 기준 주요 취약점 방어 (§3 상세) |
| NFR-2 | 사용성 | 직관적 네비게이션, 명확한 오류 메시지 |
| NFR-3 | 성능/규모 | "작은" 플랫폼 — 단일 서버, SQLite로 충분 |
| NFR-4 | 유지보수성 | 모듈 분리(Blueprint), 설정 외부화, 재현 가능한 실행 절차 |

### 1.3 요구사항 추적 매트릭스 (Traceability)

각 요구사항이 어느 설계·구현·테스트로 이어지는지 추적한다. (구현 진행 시 채움)

| 요구사항 ID | 설계 (§) | 구현 (파일/모듈) | 테스트 (TC ID) | 상태 |
|-------------|----------|------------------|----------------|------|
| FR-1.1 회원가입 | §2.3, §2.4 | `blueprints/auth.py` `register()` | TC-01 | ✅ |
| FR-1.2 로그인/로그아웃 | §2.3 | `auth.py` `login()`/`logout()` | TC-05 | ✅ |
| FR-1.3 프로필 조회 | §2.3 | `auth.py` `profile()` | TC-07 | ✅ |
| FR-1.4 마이페이지 | §2.3 | `auth.py` `mypage()` | TC-06 | ✅ |
| FR-1.5 아이디 중복 방지 | §2.4 | `models.User`(UNIQUE) + `register()` | TC-03 | ✅ |
| FR-1.6 유저 DB 저장 | §2.4 | `models.User` | TC-01 | ✅ |
| FR-2.1 상품 등록 | §2.3 | `blueprints/product.py` `new()` | TC-10 | ✅ |
| FR-2.2 내 상품 관리 | §2.3 | `product.py` `mine()`/`edit()`/`delete()` | TC-15 | ✅ |
| FR-2.3 이름·가격·사진 | §2.3 | `product_detail.html` | TC-12 | ✅ |
| FR-2.4 누구나 열람 | §2.3 | `product.py` `detail()` | TC-12 | ✅ |
| FR-2.5 상품 DB 저장 | §2.4 | `models.Product` | TC-10 | ✅ |
| FR-2.6 목록(사진+이름 갤러리)→상세 | §2.3 | `app.index()` + `index.html`(액자 갤러리) | TC-11 | ✅ |
| FR-2.7 상품 검색 | §2.3 | `app.index()` (ORM `ilike`, 파라미터 바인딩) | TC-14 | ✅ |
| FR-3.1 전체 채팅 | §2.6 | `blueprints/chat.py` + Socket.IO | TC-20 | ✅ |
| FR-3.2 1:1 채팅 | §2.6 | `chat.py` `direct_chat()` + DM room | TC-21 | ✅ |
| FR-4.1 상품·유저 신고 | §2.5 | `blueprints/report.py` `report()` | TC-30 | ✅ |
| FR-4.2 신고 사유 작성 | §2.5 | `report.py`(사유 필수 검증) + 신고 폼 | TC-30 | ✅ |
| FR-4.3 상품 자동 차단 | §2.5 | `report.py` `_apply_threshold()` → `status=blocked` | TC-30 | ✅ |
| FR-4.4 유저 자동 휴면 | §2.5 | `report.py` `_apply_threshold()` → `status=dormant` + 로그인 차단 | TC-31 | ✅ |
| FR-5 관리자 패널(전 요소) | §2.7 | `blueprints/admin.py` — 회원·상품·채팅·신고·이의제기 CRUD | TC-40, TC-43 | ✅ |
| FR-6 이의제기 | §2.7 | `blueprints/appeal.py` + `admin.appeal_resolve` | TC-41 | ✅ |
| FR-7 가상 지갑(송금) | §2.8 | `blueprints/wallet.py` (원자적 조건부 UPDATE) | TC-50, TC-51 | ✅ |

---

## 2. 시스템 설계

### 2.1 아키텍처 개요

```
[브라우저] ──HTTP──▶ [Flask 앱]
    │                   ├─ Blueprint: auth   (회원)
    │                   ├─ Blueprint: product(상품)
    │                   ├─ Blueprint: chat   (채팅 페이지)
    │                   ├─ Blueprint: report (신고)
    │                   └─ SQLAlchemy ──▶ [SQLite DB]
    └──WebSocket──▶ [Flask-SocketIO] (전체/1:1 실시간 메시지)
                        │
                   업로드 이미지 ──▶ [uploads/ (난수 파일명)]
```

- **서버 렌더링**: Jinja2 템플릿으로 HTML 생성. 실시간이 필요한 채팅만 클라이언트 JS + Socket.IO 사용.
- **모듈 분리**: 기능별 Blueprint로 라우트 분리 → 유지보수성·가독성 확보.

### 2.2 폴더 구조 (계획)

```
Shopping_Platform/
├─ app.py               # 앱 팩토리, SocketIO 초기화
├─ config.py            # 설정 (SECRET_KEY 등 환경변수 로드)
├─ models.py            # SQLAlchemy 모델
├─ blueprints/
│   ├─ auth.py
│   ├─ product.py
│   ├─ chat.py
│   └─ report.py
├─ templates/           # Jinja2
├─ static/              # CSS/JS
├─ uploads/             # 업로드 이미지 (난수 파일명)
├─ docs/REPORT.md       # 본 문서
├─ requirements.txt
└─ README.md
```

### 2.3 화면 / 라우트 설계

| 라우트 | 메서드 | 설명 | 접근 권한 |
|--------|--------|------|-----------|
| `/register` | GET/POST | 회원가입 | 누구나 |
| `/login` `/logout` | GET/POST | 로그인·로그아웃 | 누구나 / 로그인 |
| `/mypage` | GET/POST | 소개글·비밀번호 수정 | 본인 |
| `/user/<id>` | GET | 공개 프로필 | 누구나 |
| `/` | GET | 상품 목록 (**사진+이름 액자 갤러리**, 가격은 상세에서) | 누구나 |
| `/product/<id>` | GET | 상품 상세 | 누구나 |
| `/product/new` | GET/POST | 상품 등록 | 로그인 |
| `/product/mine` | GET | 내 상품 관리 | 로그인 |
| `/product/<id>/edit` `/delete` | POST | 수정·삭제 | **소유자만** |
| `/chat` | GET | 전체 채팅방 | 로그인 |
| `/dm/<user_id>` | GET | 1:1 채팅 | 로그인 |
| `/report` | POST | 신고 (대상=상품/유저 + 사유) | 로그인 |

### 2.4 데이터 모델 (ERD)

```
users                        products                    messages
─────                        ────────                    ────────
id (PK)                      id (PK)                     id (PK)
username (UNIQUE)            seller_id (FK→users.id)     room
password_hash                title                       sender_id (FK)
bio                          price                       receiver_id (FK, nullable)
status(active|dormant)       image_path                  content
report_count                 description                 created_at
created_at                   status(active|blocked)
                             report_count                reports
                             created_at                  ────────
                                                         id (PK)
                                                         reporter_id (FK)
                                                         target_type(user|product)
                                                         target_id
                                                         reason
                                                         created_at
                                                         UNIQUE(reporter_id, target_type, target_id)
```

**설계 포인트**
- `reports`의 `UNIQUE(reporter, target)`로 **동일인 중복 신고 방지** → 카운트 조작 차단 (FR-4).
- `messages.receiver_id`가 NULL이면 전체 채팅, 값이 있으면 1:1. `room`으로 방 구분.
- 비밀번호는 원문 저장 절대 금지 → `password_hash`만 (§3).
- (확장) `appeals(user_id, message, status, resolver_id)` 이의제기, `wallets(user_id PK, balance≥0)` 지갑, `transactions(sender_id nullable, receiver_id, amount, kind)` 거래기록.

### 2.5 신고 / 차단 로직 (FR-4)

```
신고 접수 (reporter, target, reason)
  ├─ 검증: 로그인 상태? 자기 자신/자기 상품 신고 아님? 중복 신고 아님?
  ├─ reports 저장
  ├─ target.report_count += 1
  └─ if report_count >= 임계치(5):
        상품 → status = blocked (목록·상세에서 숨김/차단 표시)
        유저 → status = dormant (로그인 차단)
```

- **임계치 = 5회** (기본). 소규모 플랫폼 특성상 지나치게 크면 발동이 안 되고, 1~2회면 악용 소지 → 5회로 시작하고 필요 시 조정.
- 중복 신고 차단(UNIQUE) + 자기 신고 금지로 카운트 신뢰성 확보.

### 2.6 실시간 채팅 설계 (Flask-SocketIO)

| 이벤트 | 방향 | 설명 |
|--------|------|------|
| `connect` | C→S | 세션 검증 후 접속 |
| `join` | C→S | 전체방 또는 1:1 방(room) 입장 |
| `send_message` | C→S | 메시지 전송 (서버에서 검증·저장) |
| `receive_message` | S→C | 같은 room 참여자에게 브로드캐스트 |

- **1:1 방 이름**: 두 유저 id를 정렬해 조합 (예: `dm:3_7`) → 동일 쌍은 항상 같은 방.
- 서버 수신 시 **인증·소유권·내용 검증** 후 저장/전파 (클라이언트 신뢰 금지). XSS 방어는 §3.

### 2.7 관리자 · 이의제기 설계 (확장, FR-5/FR-6)

```
[관리자]  admin_required(is_admin) ─▶ /admin/*  회원·상품·신고·이의제기 관리
[휴면 유저]  (로그인 불가) ─▶ /appeal  아이디+비밀번호 본인 인증(세션 미발급) → 소명 접수
[차단상품 판매자] (로그인 중) ─▶ "내 상품"의 이의제기 링크 → /appeal (세션으로 인증, 재인증 없음)
                              └─▶ 관리자 심사: 승인=사면(활성화+카운트0+신고삭제) / 반려
```

- **권한 부여**: 최초 관리자는 `tools/make_admin.py`(부트스트랩, 관리자가 0명인 초기 상태 대응)로 명시 부여. 이후 추가 관리자는 **기존 관리자만** `/admin/users`에서 임명/해제 가능(`admin_required`로 보호, 자기 자신 해제는 차단). 회원가입 시 자동 관리자 지정 등 암묵 규칙은 없음(권한 상승 경로 최소화).
- **이의제기 인증 분리**: 휴면 유저는 로그인이 막히므로, 로그인과 **분리된 공개 경로**에서 자격증명만 검증하고 세션은 발급하지 않는다. 승인 전까지 잠금 유지.
- **사면(pardon)**: 승인 시 대상 유저/본인 상품을 `active`로 복구하고 `report_count=0` + 관련 `reports` 삭제(재신고 가능하도록 초기화).
- 자기 자신 상태 변경 금지(관리자 자기 잠금 방지), 중복 이의제기(pending) 차단.
- **전 요소 관리(FR-5 "모든 요소")**: 관리 대상 데이터 = User·Product·Message·Report·Appeal 5종 모두 조회/수정/삭제 가능. 회원 삭제는 `_delete_user`로 관련 데이터를 연쇄 정리(FK 무결성·업로드 파일 정리).
- **DM 프라이버시**: 관리자 채팅 관리(`admin.messages`)는 **전체 채팅만** 대상(`receiver_id IS NULL`). 1:1 DM은 관리자도 조회·삭제 불가 — 삭제 라우트도 DM 대상이면 URL 직접 접근 시 403(`message_delete`). 도청 방지(§2.6) 원칙을 관리자에게도 동일하게 적용.

### 2.8 가상 포인트 지갑 설계 (확장, FR-7)

> **범위 결정**: 실제 화폐 송금은 과제 범위 밖·법적/보안 리스크(PCI·사기)이므로 **가상 포인트**로 구현. 획득은 **가입 보너스**(10,000P)만, 이동은 **유저 간 송금**만.

```
[지갑] wallets(user_id PK, balance≥0)     [기록] transactions(sender, receiver, amount>0, kind)
가입/최초접근 ──▶ 보너스 지급(kind=bonus, sender=NULL)
송금: 보낸이(세션 유저) ──amount──▶ 받는이
```

**이체 절차(원자성·경쟁조건 방어의 핵심)**
```
1) 입력 검증: 정수 amount ≥ 1, 수신자 존재, 수신자 ≠ 본인
2) 조건부 차감:  UPDATE wallets SET balance = balance - amount
                 WHERE user_id = 나 AND balance >= amount     ← 영향행 0이면 잔액부족→롤백
3) 입금:        UPDATE wallets SET balance = balance + amount WHERE user_id = 수신자
4) 기록 + 단일 커밋(차감·입금·기록이 하나의 트랜잭션 → 원자성)
```
- **경쟁조건(이중지불)**: `WHERE balance >= amount` 조건부 UPDATE로 동시 요청에도 음수 잔액 불가. DB `CHECK(balance>=0)`로 이중 방어.
- **IDOR**: 출금 계정은 항상 세션 유저(`current_user`). 폼의 sender를 신뢰하지 않음.

---

## 3. 보안 설계 (핵심)

> 본 과제의 평가 핵심. 아래 위협 모델과 방어책을 설계 단계부터 반영하고, 개발 중 발견한 취약점은 §3.3에 로그로 남긴다.

### 3.1 위협 모델 (기능 ↔ 위협 ↔ 방어)

| 기능 | 위협 | 방어책 | 관련 요구사항 |
|------|------|--------|---------------|
| 비밀번호 저장 | 평문 유출 | 해싱 (werkzeug/bcrypt), 솔트 | FR-1 |
| 로그인 | 무차별 대입 | (IP+아이디)별 실패 5회/5분 초과 시 쿨다운(브루트포스 완화) | FR-1.2 |
| 오류 응답 | 스택트레이스 등 내부 정보 노출 | 403/404/500 커스텀 에러 페이지, 배포 시 `DEBUG=False` | 전체 |
| 세션 | 탈취·고정 | 쿠키 `HttpOnly`+`SameSite`+`Secure`, 로그인 시 세션 재발급 | FR-1 |
| 모든 폼 제출 | CSRF | Flask-WTF CSRF 토큰 | 전체 |
| 채팅·소개글·상품 설명 | **XSS (저장형)** | Jinja2 자동 이스케이프, `|safe` 사용 금지, 입력 검증 | FR-2, FR-3 |
| DB 조회 | **SQL 인젝션** | ORM/파라미터 바인딩 (문자열 조합 금지) | 전체 |
| 상품 수정·삭제, 마이페이지 | **IDOR / 권한 상승** | 소유권 검증 데코레이터, 서버 측 권한 확인 | FR-2.2 |
| 사진 업로드 | 웹셸·경로 조작·MIME 위장 | 확장자 화이트리스트+MIME 검증, 파일명 난수화, 크기 제한, 실행권한 제거 | FR-2.3 |
| 신고 | 카운트 조작·남용 | 중복 신고 차단(UNIQUE), 자기 신고 금지, 로그인 필수 | FR-4 |
| 관리자 기능 | **권한 상승** (일반유저의 관리 접근) | `admin_required`로 전 라우트 서버측 강제(403), 관리자 임명은 최초=스크립트(부트스트랩)·이후=기존 관리자만 UI로 | FR-5 |
| 이의제기 | 인증 우회·휴면 우회 로그인 | 자격증명 검증 후에도 **세션 미발급**(잠금 유지), 열거 방지 동일 메시지, 중복 접수 차단 | FR-6 |
| 포인트 송금 | **경쟁조건 이중지불** | 조건부 UPDATE(`WHERE balance>=amount`) + 단일 트랜잭션 + DB `CHECK(balance>=0)` | FR-7 |
| 포인트 송금 | 음수·타인 지갑 출금(IDOR) | 정수·양수 검증, 출금은 항상 세션 유저 지갑 | FR-7 |
| 설정/배포 | 하드코딩 시크릿 노출 | `SECRET_KEY`·설정 환경변수화, `.gitignore` | 전체 |
| 오류 처리 | 정보 노출 | 상세 스택트레이스 비노출, 커스텀 에러 페이지 | 전체 |

### 3.2 보안 체크리스트 (OWASP 기반)

> 상태: ✅ 적용 완료 · 🟡 부분 적용(후속 모듈에서 확장) · ⬜ 예정

- [x] ✅ 비밀번호 해싱 저장 (원문 미저장) — werkzeug `scrypt`
- [x] ✅ SQL 파라미터 바인딩 / ORM 일관 사용 — SQLAlchemy ORM (문자열 조합 없음)
- [x] ✅ 출력 이스케이프 (XSS) — Jinja2 자동 이스케이프, `|safe` 미사용
- [x] ✅ CSRF 토큰 전 폼 적용 — Flask-WTF `CSRFProtect`
- [x] ✅ 세션 쿠키 플래그 (HttpOnly/SameSite/Secure)
- [x] ✅ 로그인 시 세션 재발급 (고정 공격 방어) — `session.clear()` 후 재설정
- [x] ✅ 세션 만료 + 민감작업 재인증 — 세션 만료 1h(유휴 갱신) + 비밀번호 변경 시 현재 비밀번호 재확인
- [x] ✅ 인증·인가 서버 측 검증 — `login_required` + 상품 소유권(IDOR) 검증(`_get_owned_product_or_403`)
- [x] ✅ 파일 업로드 검증 — 확장자 화이트리스트 + **매직바이트 내용 검증** + 난수 파일명 + 크기 제한(5MB) + 안전 서빙(`send_from_directory`)
- [x] ✅ 로그인 시도 제한 — (IP+아이디)별 실패 5회/5분 초과 시 쿨다운(계정잠금 DoS 방지 위해 IP 포함)
- [x] ✅ SECRET_KEY 환경변수화, 비밀정보 커밋 금지 — `.env`/`.gitignore`
- [x] ✅ 디버그 모드 배포 비활성화 + 커스텀 에러 페이지 — `FLASK_DEBUG` env 제어, 403/404/500 커스텀 페이지로 스택트레이스 미노출
- [x] ✅ 입력값 검증 (길이·형식·범위) — WTForms validators (Length/Regexp/EqualTo)
- [x] ✅ WebSocket 인증 — `connect` 시 세션 없으면 연결 거부
- [x] ✅ 실시간 메시지 XSS 방어 — 히스토리는 Jinja 이스케이프, 실시간은 JS `textContent`
- [x] ✅ 1:1 채팅방 접근 통제 — 참여자만 `join`/전송 가능(제3자 도청 차단)
- [x] ✅ 채팅 스팸 방지(Rate Limiting) — 사용자별 3초당 5건 초과 시 차단(초과분 본인 안내)
- [ ] 🟡 전송 구간 암호화(WSS) — 운영 영역: HTTPS 리버스프록시 뒤에서 WSS로 종단(§6.3)
- [x] ✅ 외부 스크립트 미사용 — Socket.IO 클라이언트 자체 호스팅(CDN 의존 제거)
- [x] ✅ 신고 카운트 조작 방지 — 중복 신고 차단(UNIQUE) + 자기/자기상품 신고 금지 + 서버측 카운트 증가
- [x] ✅ 신고 대상 타입 검증 — 화이트리스트(`product`/`user`)만 허용, 그 외 400
- [x] ✅ 관리자 권한 분리 — `admin_required`로 전 `/admin` 라우트 서버측 강제(비관리자 403), 관리자 임명 자체도 관리자만 가능(자기 해제 차단)
- [x] ✅ 이의제기 인증 분리 — 자격증명 검증하되 세션 미발급(휴면 우회 로그인 차단), 승인 전 잠금 유지, 중복 접수 차단
- [x] ✅ 포인트 이체 원자성·경쟁조건 방어 — 조건부 UPDATE(`WHERE balance>=amount`) + 단일 트랜잭션 + DB `CHECK(balance>=0)`, 정수·양수·자기송금 검증

### 3.3 발견한 보안 약점 및 수정 내역 (개발 중 실시간 기록)

> 개발하며 발견/수정한 취약점을 아래 표에 누적한다. **이 표가 보고서의 핵심 결과물.**

| # | 발견 위치 | 취약점 유형 | 위험 | 순진한 구현 (지양) | 적용한 방어 | 상태 |
|---|-----------|-------------|------|---------------------|-------------|------|
| 1 | 회원가입/로그인 | 평문 비밀번호 저장 | 높음 | `user.password == input` | `set_password()`→werkzeug scrypt 해싱, `check_password()` 검증 | ✅ |
| 2 | 로그인 | 사용자 열거(enumeration) — 메시지 | 중간 | "없는 아이디"/"비번 틀림" 구분 메시지 | 존재 여부 무관 **동일 메시지** 반환 | ✅ |
| 2b | 로그인 | 사용자 열거(enumeration) — **응답시간** | 중간 | 메시지는 같지만 존재 아이디는 scrypt 검증 때문에 느림 | 없는 아이디도 더미 해시 검증(§3.3 #32) | ✅ |
| 3 | 로그인 | 세션 고정(fixation) | 중간 | 기존 세션에 user_id만 추가 | 로그인 시 `session.clear()` 후 재설정 | ✅ |
| 4 | 전 폼 | CSRF | 높음 | 토큰 없는 순수 POST 폼 | `CSRFProtect` + `form.hidden_tag()` (미첨부 시 400) | ✅ |
| 5 | 프로필/소개글 | 저장형 XSS | 높음 | `{{ bio|safe }}` 로 원문 출력 | Jinja2 자동 이스케이프 유지, `|safe` 금지 | ✅ |
| 6 | 세션 쿠키 | 쿠키 탈취/스크립트 접근 | 중간 | 기본 쿠키 | `HttpOnly`+`SameSite=Lax`(+배포 시 `Secure`) | ✅ |
| 7 | 설정 | 하드코딩 시크릿 | 높음 | 소스에 `SECRET_KEY="..."` | 환경변수 로드 + `.gitignore` | ✅ |
| 8 | 입력 | 검증 부재 | 중간 | 무제한/무형식 입력 | WTForms Length·Regexp·EqualTo 검증 | ✅ |
| 9 | 사진 업로드 | 웹셸/확장자 위장 | 높음 | 확장자만 보고 저장 | 확장자 화이트리스트 **+ 매직바이트 내용 검증**(불일치 시 거부) | ✅ |
| 10 | 사진 업로드 | 경로조작·덮어쓰기 | 중간 | 원본 파일명 그대로 저장 | `secrets.token_hex` 난수 파일명, 서빙은 `send_from_directory` | ✅ |
| 11 | 상품 수정/삭제 | IDOR (남의 상품 조작) | 높음 | `product_id`만으로 처리 | `_get_owned_product_or_403`로 소유권 검증 → 403 | ✅ |
| 12 | 업로드 | 대용량 DoS | 낮음 | 무제한 | `MAX_CONTENT_LENGTH` 5MB 제한 | ✅ |
| 13 | 채팅 연결 | 미인증 WebSocket 접속 | 중간 | 누구나 소켓 연결 | `connect`에서 세션 검증, 없으면 거부 | ✅ |
| 14 | 채팅 메시지 | 실시간 XSS | 높음 | `innerHTML`로 메시지 삽입 | JS `textContent` 삽입 + 히스토리 Jinja 이스케이프 | ✅ |
| 15 | 1:1 채팅 | 방 도청(제3자 열람) | 높음 | 방 이름만 알면 입장 | `join`/전송 시 참여자(id) 검증 | ✅ |
| 16 | 프론트 자원 | 외부 CDN 공급망 위험 | 낮음 | CDN에서 socket.io 로드 | 클라이언트 JS 자체 호스팅 | ✅ |
| 17 | 신고 | 카운트 부풀리기(반복 신고) | 중간 | 신고할 때마다 무조건 +1 | 동일인·동일대상 재신고는 UNIQUE 위반으로 거부(카운트 미증가) | ✅ |
| 18 | 신고 | 자기 신고로 남 차단·자작 | 중간 | 대상 검증 없이 접수 | 본인/본인 상품 신고 금지(서버 검증) | ✅ |
| 19 | 신고 | 대상 타입 위조(파라미터 변조) | 낮음 | 폼 값 그대로 신뢰 | `target_type` 화이트리스트, `target_id` 정수 강제, 미존재 404 | ✅ |
| 20 | 차단 | 차단 상품 잔존 노출 | 중간 | 차단 후에도 목록/상세 접근 | 목록은 `status=active`만, 상세는 `blocked`→404 | ✅ |
| 21 | 관리자 기능 | 권한 상승(일반유저 관리 접근) | 높음 | 라우트만 숨기고 UI로 가림 | `admin_required`로 서버측 강제(403), 관리자 임명도 기존 관리자만 가능(회원가입 등 암묵 경로 없음) | ✅ |
| 22 | 이의제기 | 휴면 우회 로그인 | 높음 | 소명 시 세션 부여해 로그인 | 자격증명 검증하되 **세션 미발급**, 승인 전 잠금 유지 | ✅ |
| 23 | 관리자 | 자기 자신 잠금(운영 리스크) | 낮음 | 본인 계정도 휴면 가능 | 본인 상태 변경 차단 | ✅ |
| 24 | 포인트 송금 | 경쟁조건 이중지불(음수 잔액) | 높음 | 조회→검사→차감(TOCTOU) | 조건부 UPDATE `WHERE balance>=amount`(영향행 0→롤백) + 단일 트랜잭션 | ✅ |
| 25 | 포인트 송금 | 음수·0·실수 이체 | 중간 | 폼 값 그대로 차감 | 정수·`NumberRange(min=1)` 검증 + DB `CHECK(balance>=0)` | ✅ |
| 26 | 포인트 송금 | 타인 지갑 출금(IDOR) | 높음 | 폼의 sender로 출금 | 출금은 항상 세션 유저 지갑, sender 미신뢰 | ✅ |
| 27 | 로그인 | 무차별 대입(브루트포스) | 중간 | 무제한 시도 허용 | (IP+아이디)별 실패 5회/5분 초과 시 쿨다운. IP 포함으로 계정잠금 DoS 방지 | ✅ |
| 28 | 오류 처리 | 스택트레이스·경로 등 정보 노출 | 중간 | 기본 디버그 오류 페이지 | 403/404/500 커스텀 페이지 + 배포 `DEBUG=False` | ✅ |
| 29 | 채팅 | 메시지 스팸/플러딩 | 낮음 | 무제한 전송 | 사용자별 3초당 5건 초과 차단(초과분은 본인에게만 안내) | ✅ |
| 30 | 마이페이지 | 민감작업(비번변경) 재인증 부재 | 중간 | 세션만 있으면 비번 변경 | 비밀번호 변경 시 **현재 비밀번호 재확인** 요구 | ✅ |
| 31 | 관리자 | 행위 추적 불가(감사 부재) | 중간 | 관리 행위 기록 없음 | 전 관리 행위를 `AdminLog`에 기록·조회(`/admin/logs`) — 부인 방지 | ✅ |
| 32 | 로그인 | **타이밍 사이드채널을 통한 사용자 열거** | 중간 | `user is None or not check_password(...)` — 아이디 없으면 `or` 단락평가로 scrypt 검증을 건너뛰어 응답이 훨씬 빨라짐(측정상 수십 배 차이) → 메시지는 같아도 응답시간으로 계정 존재 여부 추론 가능 | 아이디가 없어도 **더미 해시로 동일하게 검증**을 수행(`_DUMMY_HASH`)해 두 경로의 소요시간을 맞춤 | ✅ |

> **검증**: 위 항목은 스모크 테스트 **163/163 통과**(auth 15 · product 23 · chat 14 · report 20 · admin/appeal 53 · wallet 22 · security 16) 및 실제 서버 응답(무-CSRF POST→400, 비로그인 `/mypage`→302)으로 확인함. (§5.1, §5.2)

---

## 4. 구현

### 4.1 기술 스택 상세

| 구분 | 선택 | 비고 |
|------|------|------|
| 언어/런타임 | Python 3.x | |
| 웹 프레임워크 | Flask | Blueprint 모듈화 |
| 실시간 | Flask-SocketIO | 전체/1:1 채팅 |
| DB | SQLite + SQLAlchemy | 파일 기반, 파라미터 바인딩 |
| 템플릿 | Jinja2 | 자동 이스케이프 |
| 보안 | Flask-WTF(CSRF), werkzeug(해싱) | |

### 4.2 모듈별 구현 요약

- **auth** (`blueprints/auth.py`) — ✅ 완료
  - `register` 회원가입: 아이디 정규식·길이 검증, 중복 검사(FR-1.5), 비번 해싱 저장
  - `login`/`logout`: 열거 방지 동일 메시지, 휴면 계정 차단, 세션 고정 방어
  - `mypage`: 소개글·비밀번호 수정 (`@login_required`, 본인 세션 기반)
  - `profile`: 공개 프로필 조회 (`get_or_404`)
  - 폼: WTForms(`RegisterForm`/`LoginForm`/`MyPageForm`) — 검증 + CSRF 토큰
  - 공통: `helpers.py`의 `current_user()`, `login_required` 데코레이터
  - **로그인 시도 제한**: (IP+아이디)별 실패 누적(`LOGIN_MAX_FAILURES`/`LOGIN_FAIL_WINDOW`) → 쿨다운. 성공 시 초기화
  - UI: 로그인·회원가입 화면 리디자인(브랜드 그라디언트 헤더 + 중앙 정렬 카드, 기존 디자인 시스템과 일관)
- **에러 처리** (`app.py`) — ✅ 완료: 403/404 커스텀 페이지(base 확장), 500은 독립 페이지(DB 비의존)로 스택트레이스 미노출
- **product** (`blueprints/product.py`) — ✅ 완료
  - `index`(홈, `app.py`): 목록 — **사진+상품명 액자 갤러리**(가격 미노출), 클릭 시 상세(FR-2.6 설계결정) · **검색**(`?q=`, 제목·설명 `ilike` 파라미터 바인딩 → SQLi 안전)
  - `detail`: 상세(이름·가격·사진·판매자·설명), 차단 상품은 404
  - `new`: 등록(`@login_required`, 이미지 업로드)
  - `mine`/`edit`/`delete`: 내 상품 관리 — **소유권 검증**(IDOR 방어)
  - 업로드 보안: `save_product_image()` — 확장자 화이트리스트 + `_detect_image_ext()` 매직바이트 검증 + 난수 파일명
  - 이미지 서빙: `uploaded_file()` — `send_from_directory`(경로조작 차단)
- **chat** (`blueprints/chat.py`) — ✅ 완료
  - `global_chat`(`/chat`): 전체 채팅방 + 최근 50건 히스토리
  - `direct_chat`(`/dm/<user_id>`): 1:1 채팅 — `dm_room()`으로 정렬된 방 이름, 자기 자신 차단
  - `inbox`(`/messages`): 1:1 대화 목록(쪽지함) — 대화 시작·재개 간소화. 상품 상세 "💬 판매자에게 문의" 버튼도 제공
  - Socket.IO 이벤트: `connect`(인증), `join`(방 입장·참여자 검증), `send_message`(검증·**스팸 rate limit**·저장·브로드캐스트)
  - 클라이언트: `static/chat.js`(textContent로 XSS 방어), `static/socket.io.min.js`(자체 호스팅)
  - **주의**: `socketio.init_app()`은 매 호출마다 새 서버를 만들므로 `register_chat_events()`를 init_app 직후 매번 호출(중복 방지 가드 두면 안 됨)
- **report** (`blueprints/report.py`) — ✅ 완료
  - `report`(`/report` POST): 상품/유저 신고 접수 — 로그인 필수, 사유 필수·길이(≤500), 대상 타입 화이트리스트
  - **카운트 신뢰성**: 중복 신고 차단(`Report` UNIQUE + `flush()`로 `IntegrityError` 감지), 자기/자기상품 신고 금지
  - **자동 조치**(`_apply_threshold`): `report_count >= REPORT_THRESHOLD(5)` 도달 시 상품 `status=blocked` / 유저 `status=dormant`
  - 차단 연동: 차단 상품은 목록(`status=active` 필터)·상세(`detail()` 404)에서 숨김, 휴면 유저는 `login()`에서 로그인 차단
  - UI: `product_detail.html`·`profile.html`에 신고 폼(`<details>` 접이식, CSRF 토큰 포함)
- **admin** (`blueprints/admin.py`, 확장) — ✅ 완료 (**플랫폼 전 요소 관리**)
  - 전 라우트 `admin_required`(권한 분리, 비관리자 403). `/admin/` 대시보드
  - **회원**: 조회·휴면/활성화·관리자 부여/해제·**삭제(연쇄 정리)** — `_delete_user`로 상품(+이미지)·메시지·신고·이의제기까지 정리(고아 데이터/FK 무결성)
  - **상품**: 조회·차단/해제·삭제·**수정**(`product.edit`, 소유권 검증이 관리자 우회 허용)
  - **채팅**: **전체 채팅만** 조회·삭제(모더레이션). 1:1 DM은 프라이버시 보호를 위해 관리자도 열람·삭제 불가
  - **신고**: 조회(이름 표시)·개별 삭제
  - **이의제기**: 승인(`_pardon_user` 사면)·반려
  - 자기 보호: 본인 상태 변경·본인 관리자 해제·본인 삭제 차단(락아웃 방지), 잘못된 `action`은 400
  - **감사 로그**: 전 관리 행위를 `AdminLog`에 기록(`_log`), `/admin/logs`에서 조회(부인 방지·추적)
  - 관리자 부여: 최초는 `tools/make_admin.py <username>`(부트스트랩), 이후는 기존 관리자가 `/admin/users`에서 임명/해제(자기 해제 차단)
- **appeal** (`blueprints/appeal.py`, 확장) — ✅ 완료
  - `/appeal` 두 경로: **① 비로그인(휴면)** = 아이디+비밀번호 본인 인증(열거 방지 동일 메시지) 후 접수, **세션 미발급**(휴면 우회 로그인 차단) / **② 로그인(차단상품 판매자)** = 세션으로 이미 인증되어 재인증 없이 접수
  - 진입점: 차단상품은 "내 상품" 목록의 "이의제기" 링크, 휴면 계정은 로그아웃 네비의 "이의제기"
  - 제재 대상(휴면·차단상품 보유)만 접수, 중복(pending) 신청 차단. 관리자 심사는 `admin.appeal_resolve`(승인=`_pardon_user` 사면)
- **wallet** (`blueprints/wallet.py`, 확장) — ✅ 완료
  - `/wallet`: 잔액·거래내역 조회 + 송금 폼. `get_wallet()`로 최초 접근 시 가입 보너스 지급
  - `/wallet/transfer`: 유저 간 송금 — `TransferForm`(정수·`NumberRange(min=1)` 검증)
  - **원자적 이체**: 조건부 UPDATE(`WHERE balance>=amount`, 영향행 0→롤백) + 입금 + 기록을 단일 트랜잭션으로 커밋
  - 자기 송금·미존재 수신자 차단, 출금은 항상 세션 유저(IDOR 방어). 모델 `Wallet`(CHECK balance≥0)·`Transaction`

**공통 구성**: `app.py`(앱 팩토리 + CSRFProtect + SocketIO), `config.py`(설정·보안 플래그), `models.py`(User/Product/Message/Report/Appeal/Wallet/Transaction/AdminLog), `helpers.py`(`current_user`·`login_required`·`admin_required`).

---

## 5. 테스트 및 체크리스트

### 5.1 기능 테스트 케이스

| TC ID | 대상 | 시나리오 | 기대 결과 | 결과 |
|-------|------|----------|-----------|------|
| TC-01 | FR-1.1 | 신규 회원가입 | 계정 생성·로그인 안내 | ✅ |
| TC-03 | FR-1.5 | 중복 아이디로 가입 시도 | 거부 메시지 | ✅ |
| TC-04 | FR-1.1 | 짧은(<8자) 비밀번호 가입 | 검증 오류 | ✅ |
| TC-05 | FR-1.2 | 올바른/잘못된 로그인 | 성공 / 실패 처리 | ✅ |
| TC-06 | FR-1.4 | 소개글·비밀번호 변경 후 재로그인 | 반영·재로그인 성공 | ✅ |
| TC-07 | FR-1.3 | 프로필 조회 | 소개글·가입일 표시 | ✅ |
| TC-08 | FR-1.4 | 비로그인 `/mypage` 접근 | 로그인으로 리다이렉트 | ✅ |
| TC-10 | FR-2.1 | 유효 이미지로 상품 등록 | 등록 성공·DB 저장 | ✅ |
| TC-11 | FR-2.6 | 목록 확인 | 사진+이름 노출(가격 미표시), 클릭 시 상세 | ✅ |
| TC-14 | FR-2.7 | 상품 검색(일치/무결과/SQLi 문자열) | 일치 노출·무결과 안내·오류 없음 | ✅ |
| TC-12 | FR-2.3/2.4 | 상세 조회 | 이름·가격·이미지 노출 | ✅ |
| TC-13 | FR-2.1 | 비로그인 등록 시도 | 로그인으로 리다이렉트 | ✅ |
| TC-15 | FR-2.2 | 소유자 수정·삭제 | 반영·삭제 성공 | ✅ |
| TC-20 | FR-3.1 | 두 계정 전체 채팅 | 실시간 상호 수신 | ✅ |
| TC-21 | FR-3.2 | 1:1 채팅 송수신 | 상대만 수신, DB 저장 | ✅ |
| TC-22 | FR-3.2 | 제3자가 남의 DM 방 입장 | 도청 차단(수신 없음) | ✅ |
| TC-30 | FR-4.1~4.3 | 상품 5회(서로 다른 유저) 신고 | 자동 차단·목록/상세 숨김 | ✅ |
| TC-31 | FR-4.4 | 유저 5회 신고 후 로그인 시도 | 자동 휴면·로그인 차단 | ✅ |
| TC-32 | FR-4.2 | 사유 없이 신고 | 거부(카운트 미증가) | ✅ |
| TC-40 | FR-5 | 관리자 화면 접근 + 회원/상품 관리 | 대시보드·관리 동작, 비관리자 403 | ✅ |
| TC-41 | FR-6 | 휴면 유저 소명 → 관리자 승인 | 접수(세션X)·승인 시 재로그인 가능 | ✅ |
| TC-42 | FR-6.1 | 잘못된 자격증명으로 소명 | 거부(이의제기 미생성) | ✅ |
| TC-43 | FR-5 | 채팅 메시지 조회·삭제, 신고 삭제, 상품 수정 | 관리자만 가능(비관리자 403) | ✅ |
| TC-44 | FR-5 | 회원 삭제 | 관련 상품·메시지 연쇄 삭제, 본인 삭제 차단 | ✅ |
| TC-50 | FR-7.4 | 유저 간 송금 | 보낸이 차감·받는이 증가·기록 생성 | ✅ |
| TC-51 | FR-7.4 | 잔액 부족/누적 초과 송금 | 조건부 UPDATE로 차단(잔액 불변) | ✅ |
| TC-52 | FR-7 | 0·음수·비정수·자기송금 | 각각 거부(잔액 불변) | ✅ |
| TC-60 | NFR-1 | 로그인 5회 실패 후 재시도 | 쿨다운(정상 비번도 차단) | ✅ |
| TC-61 | NFR-1 | 없는 페이지 접근 | 커스텀 404(내부정보 미노출) | ✅ |
| TC-62 | NFR-1 | 채팅 빠른 연속 전송 | 5건까지만 전파(스팸 제한) | ✅ |
| TC-63 | FR-1.4 | 틀린 현재 비번으로 비밀번호 변경 | 거부(비번 유지), 소개글만 변경은 허용 | ✅ |
| TC-64 | FR-5 | 관리 행위 후 감사로그 조회 | 차단·승인·삭제 등 기록·조회, 비관리자 403 | ✅ |

> 자동화: 회원 `test_auth.py`(15), 상품 `test_product.py`(23), 채팅 `test_chat.py`(14), 신고 `test_report.py`(20), 관리자·이의제기 `test_admin.py`(53), 지갑 `test_wallet.py`(22), 보안 `test_security.py`(16) — **총 163/163 통과**.

### 5.2 보안 테스트 케이스

| TC ID | 취약점 | 공격 시나리오 | 기대(방어) 결과 | 결과 |
|-------|--------|---------------|-----------------|------|
| SEC-01 | XSS | 소개글에 `<script>` 저장 후 프로필 조회 | 이스케이프되어 미실행 | ✅ |
| SEC-02 | 사용자 열거 | 없는 아이디 vs 틀린 비번 | 동일 메시지(응답시간도 더미 해시로 동일화) | ✅ |
| SEC-05 | CSRF | 토큰 없는 POST | 400 거부 | ✅ |
| SEC-06 | 세션 고정 | 로그인 전후 세션 | 로그인 시 세션 재발급 | ✅ |
| SEC-03 | IDOR | 남의 상품 `/edit`·`/delete` 직접 호출 | 403 차단 | ✅ |
| SEC-04 | 업로드 | `.php` 또는 확장자 위장(`evil.png`=PHP) 업로드 | 거부 (매직바이트 불일치) | ✅ |
| SEC-07 | SQLi | 로그인 폼 아이디/**비밀번호 필드**/주석페이로드에 `' OR '1'='1` 등 | 인증 실패(ORM 바인딩. 비번은 애초에 SQL에 안 들어가고 해시 비교만 함) | ✅ |
| SEC-08 | WS 인증 | 비로그인 소켓 연결 | 연결 거부 | ✅ |
| SEC-09 | 도청 | 제3자가 남의 DM 방 join | 입장·수신 차단 | ✅ |
| SEC-10 | 채팅 XSS | `<script>` 메시지 | 이스케이프(미실행) | ✅ |
| SEC-11 | 신고 카운트 조작 | 동일인이 같은 대상 반복 신고 | 중복 거부(카운트 미증가) | ✅ |
| SEC-12 | 자작 신고 | 자기 자신/자기 상품 신고 | 서버 거부 | ✅ |
| SEC-13 | 파라미터 변조 | `target_type=evil` 등 위조 신고 | 400 거부 | ✅ |
| SEC-14 | 권한 상승 | 일반유저가 `/admin/*` 직접 호출 | 403 차단 | ✅ |
| SEC-15 | 휴면 우회 | 소명으로 세션 획득해 로그인 시도 | 세션 미발급(잠금 유지) | ✅ |
| SEC-16 | 경쟁조건 | 잔액 초과/누적 초과 송금 | 조건부 UPDATE로 음수 잔액 차단 | ✅ |
| SEC-17 | 송금 변조 | 음수·0·비정수·자기송금 | 검증 거부(잔액 불변) | ✅ |
| SEC-18 | SQLi | 검색어에 `' OR '1'='1` | ORM `ilike` 바인딩 → 오류 없이 무결과 | ✅ |
| SEC-19 | 브루트포스 | 로그인 5회+ 실패 반복 | 쿨다운 발동(정상 비번도 일시 차단) | ✅ |
| SEC-20 | 정보 노출 | 없는 경로/오류 유발 | 커스텀 에러 페이지(스택트레이스 미노출) | ✅ |
| SEC-21 | 스팸 | 채팅 메시지 빠르게 다수 전송 | 5건 초과 전파 차단 | ✅ |
| SEC-22 | CSRF | 토큰 없는 POST 요청 | 400 거부(CSRF 강제 확인) | ✅ |
| SEC-23 | 세션 탈취 | 세션 쿠키 플래그 검사 | HttpOnly·SameSite=Lax 설정 | ✅ |
| SEC-24 | 세션 고정 | 로그인 전 심은 세션 값 | 로그인 시 폐기(재발급) | ✅ |
| SEC-25 | 경로조작 | `/uploads/..%2f..%2fmodels.py` | 404(소스 유출 없음) | ✅ |
| SEC-26 | 입력 검증 | 상품 가격 음수·비숫자 | 거부(상품 미생성) | ✅ |
| SEC-27 | 저장형 XSS | 상품 설명·신고 사유에 `<script>` | 이스케이프(미실행) | ✅ |

> 자동화: 위 보안 케이스 다수를 **`tests/test_security.py`(14)** 로 집중 검증(CSRF 강제·쿠키 플래그·세션 고정·SQLi·경로조작·입력검증·저장형 XSS). 채팅/신고/지갑/관리자 관련은 각 기능 테스트에도 포함.

---

## 6. 유지보수

### 6.1 환경 설정 및 실행 방법
- 상세는 루트 `README.md` 참조 (설치·환경변수·실행 명령).

### 6.2 알려진 한계 및 향후 개선
- TODO (예: 이미지 CDN, 알림, 검색 등)

### 6.3 배포/운영 시 주의사항
- `SECRET_KEY` 등 비밀정보 환경변수 관리, `DEBUG=False`.
- **HTTPS/WSS 종단**: 운영 시 Nginx 등 리버스프록시에서 TLS를 종단하고, WebSocket은 `wss://`로 업그레이드한다. 이때 세션 쿠키 `SESSION_COOKIE_SECURE=1`(env `COOKIE_SECURE=1`)로 설정해 평문 전송을 차단한다. Socket.IO 클라이언트는 같은 오리진(`io()`)이라 HTTPS 페이지에서 자동으로 WSS로 연결된다.
- 로그인 시도 제한은 인메모리 구현이므로, 다중 워커/재시작 환경에서는 Redis 등 공유 저장소 기반으로 확장 권장.
- 프로덕션 WSGI/ASGI 서버(gunicorn + eventlet/gevent 등) 사용 권장(개발용 서버 미사용).

---

## 부록 A. AI 도구 활용 기록

과제 요구사항에 따라 AI 도구 활용 내역을 기록한다.

| 단계 | 활용 도구 | 활용 내용 |
|------|-----------|-----------|
| 설계 | Claude | 요구사항 정리, 아키텍처·보안 설계 초안 |
| ... | | |
