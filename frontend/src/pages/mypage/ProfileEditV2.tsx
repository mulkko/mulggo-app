import { useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/profileEditV2.module.css";
import { TextField, SelectField } from "../../components/FormField/FormField";
import logo from "../../assets/logo.svg";

/**
 * 프로필 수정 화면 V2 (17-1의 별도 배치 버전).
 *
 * 기존 `/mypage/edit`(ProfileEdit.tsx)는 건드리지 않고 완전히 분리된 화면으로 만든 것.
 * 다른 담당자가 백엔드 연동을 새로 붙일 예정이라 이번 라운드는 데이터 연동
 * (GET/PUT) 없이 정적 폼만 구성한다 — 초기값은 비워두고, 저장 버튼은 API 호출
 * 없이 /mypage로 이동만 한다.
 *
 * "사업자 정보" 섹션은 biz_registration_docs 테이블 기준, "기타 정보" 섹션은
 * business_profiles 테이블 기준. 두 섹션 모두 "상호명"에 해당하는 항목이 있지만
 * 서로 다른 테이블의 다른 값이라 state 이름을 bizDocCompanyName / profileCompanyName
 * 으로 분리해뒀다.
 */

const REGION_OPTIONS = ["마포구", "서대문구", "은평구"];
const AGE_GROUP_OPTIONS = ["20대", "30대", "40대", "50대 이상"];
const OWNER_TYPE_OPTIONS = ["개인", "법인"];

interface ProfileFormV2 {
  name: string;
  // 사업자 정보 (biz_registration_docs)
  bizNo: string;
  corpNo: string;
  bizDocCompanyName: string;
  repName: string;
  openDate: string;
  birthDate: string;
  bizAddress: string;
  hqAddress: string;
  bizType: string;
  // 기타 정보 (business_profiles)
  userType: string;
  ownerType: string;
  profileCompanyName: string;
  industryDesc: string;
  region: string;
  monthsInBusiness: string;
  employees: string;
  annualRevenue: string;
  ownerAgeGroup: string;
  qualifications: string;
}

const INITIAL_FORM: ProfileFormV2 = {
  name: "",
  bizNo: "",
  corpNo: "",
  bizDocCompanyName: "",
  repName: "",
  openDate: "",
  birthDate: "",
  bizAddress: "",
  hqAddress: "",
  bizType: "",
  userType: "",
  ownerType: OWNER_TYPE_OPTIONS[0],
  profileCompanyName: "",
  industryDesc: "",
  region: REGION_OPTIONS[0],
  monthsInBusiness: "",
  employees: "",
  annualRevenue: "",
  ownerAgeGroup: AGE_GROUP_OPTIONS[1],
  qualifications: "",
};

const DEFAULT_READONLY_EMAIL = "startup@email.com";

function ProfileEditV2() {
  const navigate = useNavigate();
  const [form, setForm] = useState<ProfileFormV2>(INITIAL_FORM);
  const [email] = useState(DEFAULT_READONLY_EMAIL);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleBack = () => {
    navigate("/mypage");
  };

  const handlePhotoChange = () => {
    // TODO: 프로필 사진 변경 — 이번 범위 아님 (ProfileEdit.tsx와 동일)
  };

  const handleBizDocUploadClick = () => {
    // TODO: 사업자등록증 업로드 — 백엔드 연동 담당자가 구현 예정, 이번엔 자리만 잡아둠
  };

  const handleSave = () => {
    // TODO: 저장 API 연동 — 백엔드 연동 담당자가 구현 예정, 이번엔 이동만 처리
    navigate("/mypage");
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      <header className={styles.header}>
        <button type="button" className={styles.backButton} onClick={handleBack} aria-label="뒤로가기">
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
        <div className={styles.avatarBlock}>
          <span className={styles.avatar} aria-hidden="true">
            <img src={logo} alt="물꼬 로고" style={{ width: 46, height: "auto", display: "block" }} />
          </span>
          <button type="button" className={styles.avatarChange} onClick={handlePhotoChange}>
            사진 변경
          </button>
        </div>

        {/* 기본 정보 */}
        <div className={styles.group}>
          <span className={styles.groupTitle}>기본 정보</span>
          <TextField styles={styles} label="이름" name="name" value={form.name} onChange={handleChange} />
          <TextField styles={styles} label="이메일" name="email" value={email} inter readOnly />
        </div>

        <div className={styles.divider} />

        {/* 사업자 정보 (biz_registration_docs) */}
        <div className={styles.group}>
          <span className={styles.groupTitle}>사업자 정보</span>

          <div className={styles.field}>
            <span className={styles.label}>사업자등록증 (선택)</span>
            <button type="button" className={styles.uploadBox} onClick={handleBizDocUploadClick}>
              <span className={styles.uploadTitle}>파일을 드래그하거나 클릭해서 업로드</span>
              <span className={styles.uploadSub}>JPG, PNG, PDF · 최대 10MB</span>
            </button>
          </div>

          <TextField styles={styles} label="사업자번호" name="bizNo" value={form.bizNo} onChange={handleChange} inter />
          <TextField styles={styles} label="법인등록번호" name="corpNo" value={form.corpNo} onChange={handleChange} inter />
          <TextField styles={styles}
            label="상호명/법인명"
            name="bizDocCompanyName"
            value={form.bizDocCompanyName}
            onChange={handleChange}
          />
          <TextField styles={styles} label="대표자명" name="repName" value={form.repName} onChange={handleChange} />
          <TextField styles={styles} label="개업연월일" name="openDate" value={form.openDate} onChange={handleChange} inter />
          <TextField styles={styles} label="생년월일" name="birthDate" value={form.birthDate} onChange={handleChange} inter />
          <TextField styles={styles} label="사업장소재지" name="bizAddress" value={form.bizAddress} onChange={handleChange} />
          <TextField styles={styles} label="본점소재지" name="hqAddress" value={form.hqAddress} onChange={handleChange} />
          <TextField styles={styles} label="업태/종목" name="bizType" value={form.bizType} onChange={handleChange} />
        </div>

        <div className={styles.divider} />

        {/* 기타 정보 (business_profiles) */}
        <div className={styles.group}>
          <span className={styles.groupTitle}>기타 정보</span>

          <div className={styles.row}>
            <TextField styles={styles} label="사용자 유형" name="userType" value={form.userType} onChange={handleChange} />
            <SelectField styles={styles}
              label="사업자구분"
              name="ownerType"
              value={form.ownerType}
              options={OWNER_TYPE_OPTIONS}
              onChange={handleChange}
            />
          </div>

          <TextField styles={styles}
            label="상호명"
            name="profileCompanyName"
            value={form.profileCompanyName}
            onChange={handleChange}
          />
          <TextField styles={styles}
            label="업종 설명(원문)"
            name="industryDesc"
            value={form.industryDesc}
            onChange={handleChange}
          />
          <SelectField styles={styles}
            label="사업장 지역"
            name="region"
            value={form.region}
            options={REGION_OPTIONS}
            onChange={handleChange}
          />

          <div className={styles.row}>
            <TextField styles={styles}
              label="업력(개월)"
              name="monthsInBusiness"
              value={form.monthsInBusiness}
              onChange={handleChange}
              inter
            />
            <TextField styles={styles} label="직원수" name="employees" value={form.employees} onChange={handleChange} inter />
          </div>

          <TextField styles={styles}
            label="연매출"
            name="annualRevenue"
            value={form.annualRevenue}
            onChange={handleChange}
            inter
          />

          <div className={styles.row}>
            <SelectField styles={styles}
              label="대표자 연령대"
              name="ownerAgeGroup"
              value={form.ownerAgeGroup}
              options={AGE_GROUP_OPTIONS}
              onChange={handleChange}
            />
            <TextField styles={styles}
              label="자격/우대"
              name="qualifications"
              value={form.qualifications}
              onChange={handleChange}
            />
          </div>
        </div>
      </div>

      <div className={styles.footer}>
        <button type="button" className={styles.saveButton} onClick={handleSave}>
          저장하기
        </button>
      </div>
    </div>
  );
}

export default ProfileEditV2;
