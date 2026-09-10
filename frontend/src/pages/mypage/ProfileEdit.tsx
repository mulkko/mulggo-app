import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/profileEdit.module.css";
import { getUserId } from "../../auth/session";
import BizCertUpload from "../../components/BizCertUpload/BizCertUpload";

/**
 * 프로필 수정 화면 (17-1).
 *
 * 마이페이지(`/mypage`)의 프로필 요약 카드를 누르면 `/mypage/edit`로 들어온다.
 * 공고 상세(16)와 동일하게 하단 네비게이션 없이 상단 뒤로가기 헤더만 있는 구조.
 *
 * 폼 상태: 편집 가능한 필드는 전부 하나의 객체 state(`form`)로 관리하고,
 * input/select 는 name 속성 기반 공통 핸들러(handleChange)로 갱신한다.
 * 이메일은 계정 식별값이라 이 화면에서 수정 불가 — form state에 넣지 않고
 * 상수(READONLY_EMAIL)를 readOnly input으로 흐리게 표시한다.
 *
 * [2026-09-09] backend/api/mypage.py의 GET/PUT /api/mypage/profile 연동함
 * (business_profiles 테이블 - 실제 로그인 사용자 6명 데이터 있음).
 * [2026-09-10] user_id를 로그인 세션(auth/session.ts::getUserId)에서 가져오도록 교체,
 * 세션 없으면(자동로그인 미설정 등) FALLBACK_USER_ID로 동작.
 *
 * "기업유형"(companyType) 필드는 연동 안 함 - DB엔 이 화면 드롭다운(예비창업자/
 * 중소/소상공인/창업벤처)에 대응하는 컬럼이 없고, business_profiles.profile_type
 * (예비창업자/기존사업자 2종류만) / entity_type_code(개인/법인)만 있어서 그대로
 * 매핑하면 값이 깨짐 - 어느 컬럼/옵션 목록으로 갈지 팀 확인 필요.
 *
 * 실제 동작: 뒤로가기(→ /mypage), 저장하기(→ API PUT 후 /mypage).
 * TODO로만 남긴 것: 프로필 사진 변경, 사업자등록증 재업로드/OCR, 이름(users.name) 저장.
 * (사업자등록증 행은 기존 BizCertUpload 컴포넌트를 재사용하지 않고 이 화면에선 정적 표시만 한다.)
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// 로그인 세션(getUserId)이 없을 때만 쓰는 폴백 - business_profiles에 실데이터가 있는 계정.
const FALLBACK_USER_ID = 27;

/** 계정 이메일 — 읽기전용(이 화면에서 수정 불가). API 응답의 email로 갱신됨. */
const DEFAULT_READONLY_EMAIL = "startup@email.com";

interface ProfileApiData {
  name: string;
  email: string;
  profile_type: string | null;
  entity_type_code: string | null;
  entity_type_name: string | null;
  business_name: string | null;
  industry_text: string | null;
  region: string | null;
  business_age_months: number | null;
  annual_revenue: number | null;
  employee_count: number | null;
  founder_age_group: string | null;
  has_biz_cert: boolean;
}

interface ProfileForm {
  name: string;
  bizName: string;
  industryDesc: string;
  region: string;
  monthsInBusiness: string;
  employees: string;
  annualRevenue: string;
  ownerAgeGroup: string;
  companyType: string;
}

/** 더미 초기값 (값 출처: 프로토타입 "프로필 수정" 화면). 백엔드 연동 시 API 응답으로 교체. */
const INITIAL_FORM: ProfileForm = {
  name: "김창업",
  bizName: "물꼬 커피",
  industryDesc: "커피전문점",
  region: "마포구",
  monthsInBusiness: "0",
  employees: "0",
  annualRevenue: "0원",
  ownerAgeGroup: "30대",
  companyType: "예비창업자",
};

const REGION_OPTIONS = ["마포구", "서대문구", "은평구"];
const AGE_GROUP_OPTIONS = ["20대", "30대", "40대", "50대 이상"];
const COMPANY_TYPE_OPTIONS = ["예비창업자", "중소", "소상공인", "창업벤처"];

/** 아래로 향하는 셰브론 (select 오른쪽). */
function Chevron() {
  return (
    <svg
      className={styles.selectChevron}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

/** 라벨 + 인풋 한 세트. `inter`는 숫자/라틴 값(Inter 폰트), `readOnly`는 수정 불가 필드. */
function TextField({
  label,
  name,
  value,
  onChange,
  inter = false,
  readOnly = false,
}: {
  label: string;
  name: string;
  value: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  inter?: boolean;
  readOnly?: boolean;
}) {
  const className = [
    styles.input,
    inter ? styles.inputInter : "",
    readOnly ? styles.inputReadonly : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={name}>
        {label}
      </label>
      <input
        id={name}
        name={name}
        className={className}
        value={value}
        onChange={onChange}
        readOnly={readOnly}
      />
    </div>
  );
}

/** 라벨 + select 한 세트. */
function SelectField({
  label,
  name,
  value,
  options,
  onChange,
}: {
  label: string;
  name: string;
  value: string;
  options: string[];
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
}) {
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={name}>
        {label}
      </label>
      <div className={styles.selectWrap}>
        <select
          id={name}
          name={name}
          className={styles.select}
          value={value}
          onChange={onChange}
        >
          {options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
        <Chevron />
      </div>
    </div>
  );
}

function ProfileEdit() {
  const navigate = useNavigate();
  const [form, setForm] = useState<ProfileForm>(INITIAL_FORM);
  const [email, setEmail] = useState(DEFAULT_READONLY_EMAIL);
  // null = 아직 조회 전(깜빡임 방지용 - 조회 끝나기 전엔 업로드/정적표시 둘 다 안 보임)
  const [hasBizCert, setHasBizCert] = useState<boolean | null>(null);

  const userId = getUserId() ?? FALLBACK_USER_ID;

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/mypage/profile?user_id=${userId}`)
      .then((res) => res.json())
      .then((res: { success: boolean; data?: ProfileApiData }) => {
        if (!res.success || !res.data) return;
        const d = res.data;
        setEmail(d.email);
        setHasBizCert(d.has_biz_cert);
        setForm((prev) => ({
          ...prev,
          name: d.name ?? prev.name,
          bizName: d.business_name ?? prev.bizName,
          industryDesc: d.industry_text ?? prev.industryDesc,
          region: d.region ?? prev.region,
          monthsInBusiness: d.business_age_months != null ? String(d.business_age_months) : prev.monthsInBusiness,
          employees: d.employee_count != null ? String(d.employee_count) : prev.employees,
          annualRevenue: d.annual_revenue != null ? String(d.annual_revenue) : prev.annualRevenue,
          ownerAgeGroup: d.founder_age_group ?? prev.ownerAgeGroup,
        }));
      })
      .catch(() => {
        /* 조회 실패 시 더미값 그대로 유지 */
      });
  }, [userId]);

  // BizCertUpload가 OCR 확인/수정까지 끝낸 값을 넘겨주면, 재OCR 없이 그대로 저장만 한다
  // (signup.tsx의 biz_cert_file/biz_cert_data 전송 패턴과 동일).
  const handleBizCertConfirm = async (fields: Record<string, string>, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("biz_cert_data", JSON.stringify(fields));

    try {
      await fetch(`${API_BASE_URL}/api/mypage/biz-cert?user_id=${userId}`, {
        method: "POST",
        body: formData,
      });
    } catch {
      /* 저장 실패해도 일단 정적 표시로 전환 (에러 UI는 이번 범위 아님) */
    }
    setHasBizCert(true);
    if (fields.company_name) {
      setForm((prev) => ({ ...prev, bizName: fields.company_name }));
    }
  };

  // input/select 공통 핸들러 — name 속성으로 어떤 필드인지 구분한다.
  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleBack = () => {
    navigate("/mypage");
  };

  const handlePhotoChange = () => {
    // TODO: 프로필 사진 변경 (이미지 선택/업로드) — 이번 범위 아님
  };

  const handleBizCertClick = () => {
    // TODO: 사업자등록증 재업로드 + OCR 재추출 연동 — 이번 범위 아님
  };

  const handleSave = async () => {
    try {
      await fetch(`${API_BASE_URL}/api/mypage/profile?user_id=${getUserId() ?? FALLBACK_USER_ID}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_name: form.bizName || null,
          industry_text: form.industryDesc || null,
          region: form.region || null,
          business_age_months: form.monthsInBusiness ? Number(form.monthsInBusiness) : null,
          annual_revenue: form.annualRevenue ? Number(form.annualRevenue) : null,
          employee_count: form.employees ? Number(form.employees) : null,
          founder_age_group: form.ownerAgeGroup || null,
        }),
      });
    } catch {
      /* 저장 실패해도 일단 마이페이지로 이동 (에러 UI는 이번 범위 아님) */
    }
    navigate("/mypage");
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      {/* 헤더: 뒤로가기(→ 마이페이지) + 타이틀 */}
      <header className={styles.header}>
        <button
          type="button"
          className={styles.backButton}
          onClick={handleBack}
          aria-label="뒤로가기"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M16 5l-8 7 8 7" />
          </svg>
        </button>
        <span className={styles.headerTitle}>프로필 수정</span>
      </header>

      <div className={styles.scrollArea}>
        {/* 프로필 사진 + "사진 변경"(TODO) */}
        <div className={styles.avatarBlock}>
          <span className={styles.avatar} aria-hidden="true">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="8" r="4" />
              <path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7" />
            </svg>
          </span>
          <button
            type="button"
            className={styles.avatarChange}
            onClick={handlePhotoChange}
          >
            사진 변경
          </button>
        </div>

        {/* 기본 정보: 이름(편집 가능) / 이메일(읽기전용) */}
        <div className={styles.group}>
          <span className={styles.groupTitle}>기본 정보</span>
          <TextField
            label="이름"
            name="name"
            value={form.name}
            onChange={handleChange}
          />
          <TextField label="이메일" name="email" value={email} inter readOnly />
        </div>

        <div className={styles.divider} />

        {/* 사업자 정보 */}
        <div className={styles.group}>
          <div className={styles.groupHead}>
            <span className={styles.groupTitle}>사업자 정보</span>
            <span className={styles.groupSub}>
              사업자등록증을 올리면 아래 항목이 자동으로 채워져요. 직접 입력하거나 수정할 수도 있어요.
            </span>
          </div>

          {/* 사업자등록증 — 등록된 게 없으면(hasBizCert===false) 실제 첨부 컴포넌트,
              있으면(true) 기존 정적 표시 행(클릭은 재업로드 TODO), 조회 전(null)엔 아무 것도 안 보임. */}
          {hasBizCert === false ? (
            <div className={styles.field}>
              <span className={styles.label}>사업자등록증 (등록된 사업자등록증이 없어요)</span>
              <BizCertUpload onConfirm={handleBizCertConfirm} onSkip={() => {}} />
            </div>
          ) : hasBizCert === true ? (
            <button
              type="button"
              className={styles.bizUpload}
              onClick={handleBizCertClick}
            >
              <span className={styles.bizThumb} aria-hidden="true">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect x="3" y="3" width="18" height="18" rx="3" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <path d="M21 15l-5-5L5 21" />
                </svg>
              </span>
              <span className={styles.bizUploadText}>
                <span className={styles.bizUploadTitle}>사업자등록증 업로드</span>
                <span className={styles.bizUploadSub}>사진 또는 PDF</span>
              </span>
            </button>
          ) : null}

          <TextField
            label="상호명"
            name="bizName"
            value={form.bizName}
            onChange={handleChange}
          />
          <TextField
            label="업종 설명(원문)"
            name="industryDesc"
            value={form.industryDesc}
            onChange={handleChange}
          />

          <SelectField
            label="사업장 지역"
            name="region"
            value={form.region}
            options={REGION_OPTIONS}
            onChange={handleChange}
          />

          <div className={styles.row}>
            <TextField
              label="업력(개월)"
              name="monthsInBusiness"
              value={form.monthsInBusiness}
              onChange={handleChange}
              inter
            />
            <TextField
              label="직원수"
              name="employees"
              value={form.employees}
              onChange={handleChange}
              inter
            />
          </div>

          <TextField
            label="연매출"
            name="annualRevenue"
            value={form.annualRevenue}
            onChange={handleChange}
            inter
          />

          <SelectField
            label="대표자 연령대"
            name="ownerAgeGroup"
            value={form.ownerAgeGroup}
            options={AGE_GROUP_OPTIONS}
            onChange={handleChange}
          />
          <SelectField
            label="기업유형"
            name="companyType"
            value={form.companyType}
            options={COMPANY_TYPE_OPTIONS}
            onChange={handleChange}
          />
        </div>
      </div>

      {/* 하단 CTA: 저장하기 (→ 마이페이지) */}
      <div className={styles.footer}>
        <button type="button" className={styles.saveButton} onClick={handleSave}>
          저장하기
        </button>
      </div>
    </div>
  );
}

export default ProfileEdit;
