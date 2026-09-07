-- 물꼬(mulkko) DB 스키마 (PostgreSQL / Supabase)

CREATE TABLE IF NOT EXISTS announcements_raw (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,                  -- 수집 출처 (예: 'bizinfo', 'kstartup')
    external_id TEXT NOT NULL,             -- 원본 API의 공고 ID (예: pblancId)
    raw_data JSONB NOT NULL,               -- API 응답 원본 그대로 저장
    collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, external_id)
);

CREATE TABLE IF NOT EXISTS announcements_parsed (
    id BIGSERIAL PRIMARY KEY,
    raw_id BIGINT REFERENCES announcements_raw(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    agency TEXT,                           -- 소관/수행 기관
    category TEXT,                         -- 지원분야 (자금, 인력, 수출 등)
    region TEXT,                           -- 지원 지역
    target_business_type TEXT,             -- 대상 업종
    target_company_stage TEXT,             -- 대상 기업 단계 (예비창업, 3년 이내 등)
    min_employee_count INT,
    max_employee_count INT,
    min_annual_revenue NUMERIC,
    max_annual_revenue NUMERIC,
    eligibility_criteria JSONB,            -- 구조화된 자격요건
    support_amount TEXT,
    application_start_date DATE,
    application_end_date DATE,
    source_url TEXT,
    parsed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,          -- 인증 시스템의 사용자 식별자
    company_name TEXT,
    business_type TEXT,
    region TEXT,
    founded_date DATE,
    employee_count INT,
    annual_revenue NUMERIC,
    business_stage TEXT,                   -- 예비창업, 창업 3년 이내 등
    interests JSONB,                       -- 관심 분야/키워드
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS matching_results (
    id BIGSERIAL PRIMARY KEY,
    user_profile_id BIGINT NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    announcement_id BIGINT NOT NULL REFERENCES announcements_parsed(id) ON DELETE CASCADE,
    match_score NUMERIC,                   -- 매칭 점수
    match_reason TEXT,                     -- 매칭 근거 요약
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_profile_id, announcement_id)
);

-- 관리자 대시보드의 "최근 배치 실행 로그"용. 특정 유저/공고를 가리키는 게 아니라
-- 배치 1회 실행에 대한 집계 기록이라 FK 없음.
CREATE TABLE IF NOT EXISTS crawl_batch_logs (
    crawl_id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,                  -- 'bizinfo', 'kstartup' 등
    fetched_count INT NOT NULL,
    inserted_count INT NOT NULL,
    status TEXT NOT NULL,                  -- 'success' / 'error'
    ran_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ══════════════════════════════════════════════════════
-- 아래부터는 실제 운영 DB(Supabase)에 있는 회원/사업자 관련 테이블을 그대로 반영한 것.
-- users 테이블은 실제로는 Supabase Auth가 관리하는 컬럼(instance_id, encrypted_password,
-- confirmation_token, recovery_token 등 약 30개)이 더 있으나, 앱 코드가 직접 읽고 쓰는
-- 컬럼만 여기 기록한다.
-- ══════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS users (
    user_id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    role VARCHAR(255),
    is_admin BOOLEAN NOT NULL DEFAULT false,
    agree_terms BOOLEAN NOT NULL DEFAULT false,
    agree_privacy BOOLEAN NOT NULL DEFAULT false,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 개인/법인 코드표. 'prospective'(예비창업자)는 아직 확정 전 상태라 여기 없고 business_profiles.profile_type에만 있음.
CREATE TABLE IF NOT EXISTS entity_types (
    code VARCHAR(10) PRIMARY KEY,          -- 'individual'(개인), 'corporate'(법인)
    name VARCHAR(20) NOT NULL
);

-- 가입 시 user_id만 채워서 생성됨 (profile_type='예비창업자').
-- 사업자등록증 OCR 성공 시 UPDATE로 profile_type='기존사업자', entity_type_code, business_name 등이 채워짐.
CREATE TABLE IF NOT EXISTS business_profiles (
    profile_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE REFERENCES users(user_id),
    profile_type VARCHAR(20) NOT NULL,     -- '예비창업자' / '기존사업자'
    entity_type_code VARCHAR(10) REFERENCES entity_types(code), -- OCR 성공 전까지 NULL
    business_name TEXT,
    industry_text TEXT,
    region TEXT,
    business_age_months INT,
    annual_revenue BIGINT,
    employee_count INT,
    founder_age_group TEXT,
    profile_attributes JSONB,
    matching_profile_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 사업자등록증 업로드 + OCR 결과 저장. 프로필당 여러 장 첨부 가능하므로 profile_id 기준 1:N.
CREATE TABLE IF NOT EXISTS biz_registration_docs (
    document_id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES business_profiles(profile_id),
    entity_type_code VARCHAR(10) NOT NULL REFERENCES entity_types(code),
    file_name TEXT NOT NULL,
    file_type VARCHAR(10),
    storage_path TEXT NOT NULL,
    biz_no VARCHAR(12) NOT NULL,
    corp_no VARCHAR(14),
    company_name VARCHAR(100) NOT NULL,
    ceo_name VARCHAR(100) NOT NULL,
    open_date DATE NOT NULL,
    birth_date DATE,
    business_address TEXT NOT NULL,
    head_address TEXT,
    business_category JSONB,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 사업자등록증의 "사업의 종류"(업태·종목) — 표 형태라 여러 행 가능 (profile_id 기준 1:N).
-- backend/assistant/category_ocr.py(EasyOCR+Qwen 보정)가 채우고, backend/auth/signup.py의
-- save_biz_cert_data()에서 biz_registration_docs 저장 직후 같이 저장한다.
-- nts_industry_code/ksic_code는 업종 자동매핑(DA2, backend/ml/classifier) 담당 — 우리 OCR
-- 파이프라인은 채우지 않고 NULL로 둔다.
-- 주의: nts_industry_codes, ksic_codes 테이블 정의는 이 파일에 아직 없음 (실제 DB엔 존재).
CREATE TABLE IF NOT EXISTS profile_business_types (
    business_type_id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES business_profiles(profile_id),
    business_category TEXT,                -- 업태
    business_item TEXT,                    -- 종목
    nts_industry_code VARCHAR(10) REFERENCES nts_industry_codes(code),
    ksic_code VARCHAR(10) REFERENCES ksic_codes(code),
    is_primary BOOLEAN NOT NULL DEFAULT false
);
