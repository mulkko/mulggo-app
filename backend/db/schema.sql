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
-- 공고 수집·가공 파이프라인 테이블 (2026-09 기준 실제 운영 DB 반영).
-- 위쪽의 announcements_raw / announcements_parsed 는 초기 설계안이고, 실제
-- 파이프라인은 아래의 "소스별 raw 테이블 + 통합 announcements" 구조를 쓴다.
--   crawler/bizinfo_api.py, crawler/kst_api.py         -> raw 적재
--   preprocessing/sync_bizinfo_announcements.py 등      -> raw 읽어 가공 후 announcements 에 UPSERT
-- (schema.sql 정리 시 위 두 테이블 폐기 여부는 팀 확인 필요)
-- ══════════════════════════════════════════════════════

-- 기업마당(bizinfo) API 원본. API 응답 키를 컬럼으로 펼치고 전체 JSON 은 source_raw 에 보존.
CREATE TABLE IF NOT EXISTS announcements_raw_bizinfo (
    raw_bizinfo_id                   BIGSERIAL PRIMARY KEY,
    pblanc_id                        VARCHAR(50) NOT NULL,   -- API pblancId (원본 공고 ID)
    pblanc_nm                        TEXT NOT NULL,
    trget_nm                         TEXT,
    jrsd_instt_nm                    TEXT,                   -- 소관기관
    exc_instt_nm                     TEXT,                   -- 수행기관
    bsns_sumry_cn                    TEXT,
    pldir_sport_realm_lclas_code_nm  TEXT,
    pldir_sport_realm_mlsfc_code_nm  TEXT,
    reqst_begin_end_de               TEXT,
    reqst_mth_papers_cn              TEXT,
    hashtags                         TEXT,
    pblanc_url                       TEXT,
    rcept_engn_hmpg_url              TEXT,
    file_nm                          TEXT,
    print_flpth_nm                   TEXT,
    print_file_nm                    TEXT,
    flpth_nm                         TEXT,
    inqire_co                        INTEGER,                -- 조회수
    creat_pnttm                      TIMESTAMPTZ,
    updt_pnttm                       TIMESTAMPTZ,
    source_raw                       JSONB,                  -- API 응답 원본 전체
    collected_at                     TIMESTAMPTZ NOT NULL,   -- 크롤러가 NOW() 로 채움
    refrnc_nm                        TEXT                    -- 문의처(담당부서+연락처). 2026-09-07 추가 (contact 매핑 소스)
);

-- 창업진흥원(K-Startup) 오픈API 원본. 마감 공고는 애초에 저장 안 함(진행 중인 것만).
CREATE TABLE IF NOT EXISTS announcements_raw_kstartup (
    raw_kstartup_id          BIGSERIAL PRIMARY KEY,
    pbanc_sn                 VARCHAR(50) NOT NULL,           -- 원본 공고 번호
    biz_pbanc_nm             TEXT NOT NULL,
    intg_pbanc_biz_nm        TEXT,
    intg_pbanc_yn            BOOLEAN,
    pbanc_ctnt               TEXT,
    pbanc_ntrp_nm            TEXT,                           -- 공고 게시기관
    sprv_inst                TEXT,                           -- 주관기관
    biz_prch_dprt_nm         TEXT,                           -- 담당부서
    supt_biz_clsfc           TEXT,
    supt_regin               TEXT,
    aply_trgt                TEXT,
    aply_trgt_ctnt           TEXT,
    aply_excl_trgt_ctnt      TEXT,
    biz_trgt_age             TEXT,
    biz_enyy                 TEXT,
    prfn_matr                TEXT,
    rcrt_prgs_yn             CHAR(1),                        -- 모집진행여부 Y/N
    pbanc_rcpt_bgng_dt       DATE,
    pbanc_rcpt_end_dt        DATE,
    biz_aply_url             TEXT,
    biz_gdnc_url             TEXT,
    detl_pg_url              TEXT,
    prch_cnpl_no             TEXT,
    aply_mthd_eml_rcpt_istc  TEXT,
    aply_mthd_fax_rcpt_istc  TEXT,
    aply_mthd_vst_rcpt_istc  TEXT,
    aply_mthd_onli_rcpt_istc TEXT,
    aply_mthd_pssr_rcpt_istc TEXT,
    aply_mthd_etc_istc       TEXT,
    source_raw               JSONB,
    collected_at             TIMESTAMPTZ NOT NULL
);

-- 두 소스를 합친 최종 공고 테이블. sync_*_announcements.py 가 지역/업종 매핑까지
-- 끝낸 결과를 UPSERT. raw_bizinfo_id / raw_kstartup_id 중 소스에 해당하는 쪽만 채워짐.
CREATE TABLE IF NOT EXISTS announcements (
    announcement_id        BIGSERIAL PRIMARY KEY,
    source                 VARCHAR(20) NOT NULL,            -- 'bizinfo' / 'kstartup'
    raw_bizinfo_id         BIGINT REFERENCES announcements_raw_bizinfo(raw_bizinfo_id),
    raw_kstartup_id        BIGINT REFERENCES announcements_raw_kstartup(raw_kstartup_id),
    title                  TEXT NOT NULL,
    content                TEXT,
    host_org_name          TEXT,                            -- 수행기관
    supervising_org        TEXT,                            -- 소관기관
    contact                TEXT,
    category               TEXT,
    target_summary         TEXT,
    target_age_groups      TEXT[],
    business_age_condition  TEXT,
    apply_start_date       DATE,
    apply_end_date         DATE,
    detail_page_url        TEXT,
    regions                TEXT[],
    region_status          VARCHAR(30) NOT NULL,            -- extract_region() status (예: inferred_no_restriction)
    region_needs_review    BOOLEAN NOT NULL,
    ksic_codes_matched     TEXT[],
    ksic_names_matched     TEXT[],
    ksic_codes_excluded    TEXT[],
    ksic_status            VARCHAR(30) NOT NULL,            -- decide_industry() 확정단계 (예: 특정불가, 업종무관(기본값))
    apply_method           TEXT,
    management_no          TEXT,
    collected_at           TIMESTAMPTZ NOT NULL,
    updated_at             TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_announcements_raw_bizinfo_id  ON announcements (raw_bizinfo_id);
CREATE INDEX IF NOT EXISTS idx_announcements_raw_kstartup_id ON announcements (raw_kstartup_id);
-- sync 의 UPSERT(ON CONFLICT) 대상. 원본 공고 1건당 announcements 1행 보장. 2026-09-07 추가
CREATE UNIQUE INDEX IF NOT EXISTS uq_announcements_raw_bizinfo_id  ON announcements (raw_bizinfo_id)  WHERE source = 'bizinfo';
CREATE UNIQUE INDEX IF NOT EXISTS uq_announcements_raw_kstartup_id ON announcements (raw_kstartup_id) WHERE source = 'kstartup';

-- 공고 첨부파일 — 공고 상세페이지의 원본 신청서 양식·공고문 파일(정부가 게시한
-- 원본이며 신청서 어시스턴트가 만든 결과물이 아님). 공고 1건 : 첨부 N개.
-- 현재 크롤러/파이프라인이 아직 안 채움(빈 테이블). 채우는 로직은 별도 작업.
CREATE TABLE IF NOT EXISTS announcement_attachments (
    attachment_id    BIGSERIAL PRIMARY KEY,
    announcement_id  BIGINT NOT NULL REFERENCES announcements(announcement_id),
    file_name        TEXT NOT NULL,
    file_type        VARCHAR(10),          -- 확장자 (pdf/hwp/hwpx/zip/xlsx 등)
    attachment_role  VARCHAR(20),          -- 공고문/신청서양식/붙임 등 역할 구분
    source_url       TEXT NOT NULL,        -- 원본 다운로드 URL
    storage_path     TEXT,                 -- 자체 저장소에 받아둔 경우의 경로
    collected_at     TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_announcement_attachments_announcement_id
    ON announcement_attachments (announcement_id);

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

-- KSIC(한국표준산업분류 11차) 코드 -> 이름/계층 조회용 사전.
-- 시드: data/ksic_clean_v2.csv (분류기 backend/ml/classifier/explicit_match.py가
-- 쓰는 바로 그 파일) <- backend/preprocessing/load_ksic_codes.py 로 UPSERT 적재 (1,202행).
--   code = 세세분류(5자리, PK), name = 세세분류명, large/medium/small/detail = 대/중/소/세.
-- 공고 매칭(announcements.ksic_codes_matched)이 뱉는 코드의 이름/계층을 풀거나,
-- profile_business_types.ksic_code(FK) 무결성 근거로 쓴다.
-- 참고: nts_industry_codes(국세청 업종코드) 테이블은 실제 DB엔 존재하나 현재 미사용
-- (유저/공고 둘 다 텍스트->분류기->KSIC 로 비교, 국세청 연계 안 씀). 이 파일에 정의 없음.
CREATE TABLE IF NOT EXISTS ksic_codes (
    code VARCHAR(10) PRIMARY KEY,
    name TEXT NOT NULL,
    large_code VARCHAR(2),
    large_name VARCHAR(50),
    medium_code VARCHAR(4),
    medium_name VARCHAR(50),
    small_code VARCHAR(6),
    small_name VARCHAR(50),
    detail_code VARCHAR(8),
    detail_name VARCHAR(50)
);

-- 사업자등록증의 "사업의 종류"(업태·종목) — 표 형태라 여러 행 가능 (profile_id 기준 1:N).
-- backend/assistant/category_ocr.py(EasyOCR+Qwen 보정)가 채우고, backend/auth/signup.py의
-- save_biz_cert_data()에서 biz_registration_docs 저장 직후 같이 저장한다.
-- nts_industry_code/ksic_code는 업종 자동매핑(DA2, backend/ml/classifier) 담당 — 우리 OCR
-- 파이프라인은 채우지 않고 NULL로 둔다.
-- 주의: nts_industry_codes 테이블 정의는 이 파일에 아직 없음 (실제 DB엔 존재, 현재 미사용).
CREATE TABLE IF NOT EXISTS profile_business_types (
    business_type_id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES business_profiles(profile_id),
    business_category TEXT,                -- 업태
    business_item TEXT,                    -- 종목
    nts_industry_code VARCHAR(10) REFERENCES nts_industry_codes(code),
    ksic_code VARCHAR(10) REFERENCES ksic_codes(code),
    is_primary BOOLEAN NOT NULL DEFAULT false
);
