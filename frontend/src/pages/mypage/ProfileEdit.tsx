import { useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/profileEdit.module.css";

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
 * 실제 동작: 뒤로가기(→ /mypage), 저장하기(→ /mypage).
 * TODO로만 남긴 것: 프로필 사진 변경, 사업자등록증 재업로드/OCR, 저장 API 연동.
 * (사업자등록증 행은 기존 BizCertUpload 컴포넌트를 재사용하지 않고 이 화면에선 정적 표시만 한다.)
 */

/** 계정 이메일 — 읽기전용(이 화면에서 수정 불가). 백엔드 연동 시 로그인 사용자 정보로 교체. */
const READONLY_EMAIL = "startup@email.com";

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

  const handleSave = () => {
    // TODO: 백엔드 프로필 저장 API 연동 (form 전송) — 성공 시 마이페이지로 이동
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
          <TextField label="이메일" name="email" value={READONLY_EMAIL} inter readOnly />
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

          {/* 사업자등록증 업로드 행 (정적 표시 — 클릭은 TODO) */}
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
