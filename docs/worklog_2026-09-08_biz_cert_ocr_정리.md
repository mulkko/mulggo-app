# 작업 기록 — 사업자등록증 OCR 기능 (2026-09-08)

> 보고서 작성용 참고 자료. 팀 공유 문서가 아니라 개인 작업 로그이므로, 필요한 내용만 골라서 보고서에 옮겨 쓰면 됨.
> 커밋/푸시는 아직 안 한 상태 — 원하면 git에 올리고, 원하지 않으면 로컬에만 두고 참고만 해도 됨.

## 1. 배경

Qwen2.5-VL-3B-Instruct(로컬 GPU 비전 모델)로 사업자등록증을 OCR해서, 회원가입 시 사용자가 업로드한 사진에서 상호/대표자명/사업자번호/개업일/주소/업태/종목을 자동 추출 → 검토/수정 → DB 저장까지 이어지는 기능을 만드는 작업. RTX 4060(8GB VRAM) 한 대에서 모델을 돌리고, 다른 팀원 PC는 네트워크로 그 GPU PC에 붙어서 테스트하는 구조.

## 2. OCR 파이프라인 안정화 (`backend/assistant/biz_cert_ocr.py`)

### 겪은 문제와 원인
- **CUDA device-side assert (이미지 리사이징 시)**: 처음엔 PIL로 직접 이미지를 리사이즈했는데, Qwen 모델이 내부적으로 요구하는 28px 패치 / 2×2 병합 그리드에 안 맞아서 발생. → `qwen_vl_utils`가 제공하는 `max_pixels` 방식으로 리사이즈를 맡기는 것으로 해결 (직접 리사이즈 금지).
- **CUDA assert / 출력이 "!!!"처럼 깨지는 현상 (특히 어두운 사진)**: 8GB VRAM으로는 3B 모델이 다 안 올라가서 일부 레이어가 CPU로 오프로드됨(`device_map="auto"`) → 그 상태에서 fp16 + 샘플링(확률적 생성)을 쓰니 수치가 불안정해짐. → `bfloat16` + `do_sample=False`(그리디 디코딩)로 해결.
- **작은 글씨(대표자명 등) 인식 실패**: `MAX_OCR_PIXELS`를 1280²에서 1600²로 올려서 해결. 다만 이건 "속도 vs 정확도" 트레이드오프라 무조건 좋은 건 아님 — 인식률은 올라가지만 처리 시간도 늘어남.

### 결과
같은 사진 기준으로 안정적으로 성공하고, 속도도 초기 대비 개선된 상태. GPU가 약한 PC 특성상 "이미지를 더 작게 보내면 빠를까" / "화질 좋은 사진이면 더 빠를까"는 확인만 하고 실행은 보류한 상태 (의견 교환만 진행, 코드 변경 없음).

## 3. 크로스 PC 테스트 (하이브리드 아키텍처)

- 각자 PC에서 프론트(Vite)는 로컬로 띄우되, **OCR 요청만** GPU가 있는 고정 PC(`192.168.0.160:8000`)로 보내는 구조.
- `backend/main.py`에 CORS 허용 정규식 추가: `allow_origin_regex=r"http://192\.168\.0\.\d{1,3}:5173"`.
- `frontend/vite.config.ts`에 `server: { host: true }` 추가해서 LAN 노출.
- 프론트 쪽 주소는 `frontend/src/components/BizCertUpload/BizCertUpload.tsx`의 `OCR_SERVER_HOST` 상수(하드코딩된 GPU PC IP)로 고정하되, `localStorage.setItem("ocr_api_base_url", "http://새주소:8000")`로 덮어쓸 수 있게 해둠 (GPU PC IP가 바뀔 경우 대비).
- PDF 업로드가 안 되던 문제는 poppler(`pdf2image` 의존)가 설치는 되어 있었지만 PATH에 안 잡혀 있어서였음 — 재확인 후 정상 동작 확인.

## 4. 프로덕션 컴포넌트: `BizCertUpload`

### 설계 원칙 (사용자와 논의 후 확정)
- "OCR 결과를 그냥 한 번에 저장"이 아니라, **팝업으로 결과를 보여주고 사용자가 확인/수정 후 확인 버튼을 눌러야 저장**되는 방식으로 결정.
- 이미 값이 채워진 필드는 텍스트로만 보여주고 "수정" 버튼을 눌러야 입력창으로 바뀌는 구조, 처음부터 비어있는 필드(OCR이 못 읽은 값)는 처음부터 입력창으로 열어서 "확인 필요" 배지 표시.
- 사업자등록증 첨부 자체가 선택 사항이라 "나중에 하기(skip)" 경로도 항상 제공.

### 파일 검증
- 확장자: jpg / png / pdf만 허용.
- 용량: 최대 10MB (추후 조정 가능하다는 전제로 우선 확정).

### 최종 파일
- `frontend/src/components/BizCertUpload/BizCertUpload.tsx` (신규 컴포넌트)
- `frontend/src/components/BizCertUpload/bizCertUpload.module.css` (스타일 가이드 토큰 적용)
- `frontend/src/pages/auth/Signup.tsx`에 통합 — 확인 시 `biz_cert_file` + `biz_cert_data`(JSON)를 회원가입 FormData에 같이 담아 전송.
- 백엔드 `POST /api/auth/biz-cert-ocr` 엔드포인트(`backend/api/auth.py`) 신설 — 업로드된 파일을 임시 저장 후 OCR만 수행해서 결과 반환 (아직 DB 저장은 안 함, 회원가입 제출 시점에 한 번에 저장).
- `/signup` 엔드포인트는 `biz_cert_data`가 같이 오면 재OCR 없이 그 값 그대로 저장 (`save_biz_cert_data`).

## 5. 업태/업종 OCR 연동

- 원래 업태/업종은 별도 파이프라인(`backend/assistant/category_ocr.py`, EasyOCR + 기하학적 휴리스틱 + Qwen 보정)이었고, 처음엔 이 값을 회원가입 팝업에서 확인 없이 바로 저장하도록 짜여 있었음 → 사용자가 "다른 필드들처럼 검토 후 저장이어야 하지 않냐"고 지적 → `REVIEW_FIELDS`에 `business_category`(업태)/`business_item`(종목) 추가해서 다른 필드와 동일하게 검토 대상으로 통일.
- `POST /biz-cert-ocr` 엔드포인트가 기본 OCR(`extract_biz_cert`)과 업태/업종 OCR(`category_ocr.extract_categories`)을 같이 호출해서 하나의 응답으로 합쳐서 반환.
- 저장은 `profile_business_types` 테이블에 `business_category`/`business_item`이 있을 때만 insert.

### 업태/업종이 계속 빈 값으로 나오던 문제
- 원인은 파이프라인 버그가 아니라, **테스트에 쓰던 이미지가 합성(synthetic) PNG였기 때문** — EasyOCR의 영역 탐지가 실제 사진에는 잘 작동하지만 인위적으로 만든 테스트 이미지에는 실패함. 실제 사진 3장으로는 3/3 성공, 합성 PNG 2장으로는 2/2 실패(엔드포인트 직접 호출 양쪽 다 동일하게 실패)로 원인 확정.

## 6. DB 스키마 관련 확인 사항 (구현 아님, 조사만 진행)

- `users.applicant_type` 컬럼은 팀원이 이미 제거했고, 대신 `business_profiles.profile_type`('예비창업자'/'기존사업자') + `business_profiles.entity_type_code`(개인/법인 FK)로 대체되어 있음.
- `biz_registration_docs`는 `biz_no`, `company_name`, `ceo_name`, `open_date`, `business_address`에 NOT NULL 제약이 있어서, 프론트 `REQUIRED_FIELDS`도 이 5개로 맞춤.
- **`profile_business_types` 테이블**(스키마 문서엔 없었지만 실제 DB엔 존재): 업태/업종 저장용 컬럼 외에, 향후 "정부지원사업 매칭" 기능에 쓸 것으로 보이는 `nts_industry_code`(국세청 업종코드), `ksic_code`(표준산업분류코드) 컬럼도 있음.
- **위 두 코드 컬럼이 항상 비어있는 이유(확인만, 미구현)**:
  - 매칭에 필요한 `ksic_codes` / `nts_industry_codes` / `nts_ksic_mapping` 테이블이 전부 0건 (데이터 자체가 아직 안 들어감).
  - 매핑에 필요한 `data/ksic_clean_v2.csv` 파일도 저장소에 없음 (DA2가 준비해야 하는 참고 데이터로 추정).
  - 즉 지금 이 값을 채우는 코드를 연결해도 FK 위반/파일 없음 에러만 나는 상태 — **선행 조건은 (1) 업종 매칭 기능 자체의 설계 확정, (2) KSIC/국세청 코드 테이블에 데이터 적재**이고, 둘 다 코드 문제가 아니라 팀의 다른 파트(DA2 등) 작업이 먼저 필요함.
  - `backend/ml/classifier/{explicit_match.py, llm_match.py, decide_industry.py}`에 이미 매칭 로직 자체는 존재(공고 데이터 태깅에 사용 중)하지만, 사용자/프로필 쪽에는 아직 연결 안 됨.
- 스키마 문서(`backend/db/schema.sql`)에 `profile_business_types` 테이블 정의를 추가해서 실제 DB와 문서를 동기화함. `backend/db/describe_table.py`(신규)로 `python -m backend.db.describe_table <테이블명>` 하면 실제 DB 구조를 바로 조회해서 `CREATE TABLE` 초안을 뽑아줌 — 앞으로 스키마 동기화 확인할 때 재사용 가능.

## 7. 버그 수정 (React)

두 가지 서로 다른 원인으로, 팝업에서 한글을 입력하면 한 글자 치고 입력창이 닫혀버리는 현상이 있었음.

1. **이미 값이 있던 필드**: `onBlur`로 자동으로 "수정 모드 종료" 처리를 했는데, 한글 조합 입력 중 브라우저가 순간적으로 blur를 발생시켜서 오작동. → `onBlur` 자동 종료 로직 제거.
2. **처음부터 비어있던 필드(업태/업종 등)**: "입력창으로 보여줄지 여부"를 매 렌더링마다 "지금 값이 비어있는가"로 다시 계산하고 있어서, 한 글자라도 입력되는 순간 "이제 안 비었네" 판단하고 스스로 입력창을 닫아버림. → `openFields`(한 번 열리면 계속 열려있는 Set 상태)로 재설계, 값이 아니라 "열렸는가"만으로 판단하도록 변경.

이 문제는 모바일 터치 입력과는 무관하고, 순수하게 한글 조합 입력(IME) 특성 때문이라는 것도 별도로 확인함.

## 8. 스타일 가이드 반영

`frontend/src/styles/webTokens.css` / `signup.module.css`의 토큰(`--font-size-body`, `--input-height-min`, `--color-navy-sphere` 등)을 `bizCertUpload.module.css`에도 동일하게 적용해서, 입력창 높이/폰트 크기 등이 회원가입 폼의 다른 입력창들과 시각적으로 일치하도록 맞춤.

## 9. Git / 워크플로우

- 세션 중 여러 차례 브랜치 전환 시 커밋 안 한 파일이 날아가는 사고, 팀원 3명 이상의 동시 푸시로 인한 머지 충돌(`backend/auth/signup.py`, `backend/db/schema.sql`, `backend/main.py`, `.gitignore`, `requirements.txt`, `backend/api/test_ocr.py`, `backend/assistant/biz_cert_ocr.py`, `frontend/src/pages/auth/Signup.tsx` 등)을 겪고 매번 양쪽 의도를 파악해서 수동 병합, `py_compile`/`tsc -b --noEmit`으로 검증 후 푸시.
- 이 사고들을 계기로 **앞으로는 각자 작업을 `main`에 바로 올리지 않고 PR을 거쳐서 병합하는 방식으로 팀 워크플로우를 바꾸기로 결정.**
- 이번 작업은 `DA3_` 브랜치에서 진행. 마지막 커밋: `3fd0107` ("BizCertUpload: 빈 필드 입력 시 자동으로 닫히던 버그 수정 + 인풋 스타일 가이드 반영"). `DA3_` → `main` PR은 준비만 해두고(제목/설명 초안 전달) 실제로 열었는지는 미확인 상태.

## 10. 보류 / 다음 단계 (내 판단으로 진행 안 한 것들)

- **마이페이지/서비스 진입 지점에서의 OCR 재사용**: 현재 로그인 세션/인증 체계 자체가 없어서 회원가입 외 지점에는 적용 불가 — TA(백엔드 인프라) 영역 선행 필요.
- **업종 자동분류(KSIC/국세청 코드) 연결**: 위 6번 항목 참고 — 매칭 기능 설계 확정 + DA2의 참조 데이터 적재가 선행되어야 함.
- **개인/법인 구분 UI(등록번호 필드 관련) 리디자인**: 사용자가 명시적으로 보류 결정.
- **모바일 카메라 촬영 속성(`capture` attribute) 추가**: 나중에 추가해도 안전하다고 확인만 해둔 상태, 미적용.
