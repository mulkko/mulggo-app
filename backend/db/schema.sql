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
