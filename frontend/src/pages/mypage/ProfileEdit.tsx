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
 * "기업유형"은 예비창업자/개인/법인 3가지뿐 - business_profiles.profile_type +
 * entity_type_code(OCR로 자동 판별)를 그대로 읽기전용으로 보여준다(사용자가 임의로
 * 바꿀 수 있는 값이 아니라서 select 아님). "기업 규모"(중소/소상공인/창업벤처,
 * 「소상공인기본법」상 상시근로자수·매출 기준 - entity_type과는 다른 축)는 완전히
 * 별개 항목으로 분리했고, 전용 컬럼 없이 business_profiles.profile_attributes
 * (JSONB, 그동안 미사용이었음 - 실측 확인, 10행 전부 NULL)에 company_size 키로
 * 저장한다(2026-09-11, 사용자 확인 - 값 직접 선택, 자동 판정 로직은 다음 과제).
 *
 * 실제 동작: 뒤로가기(→ /mypage), 저장하기(→ API PUT 후 /mypage).
 * [2026-09-10] 이름 저장도 연동함 - business_profiles가 아니라 users.name이라
 * backend/api/mypage.py에서 fields에서 따로 빼서 별도 UPDATE users 문으로 처리.
 * [2026-09-10] 예비창업자는 상호명/업력/직원수/연매출 입력창을 숨기고 안내 문구로
 * 대체함(profile_type 기준) - 실측 확인 결과 예비창업자 8명 전원 이 4개 필드가
 * NULL이었음(사업자등록증이 없으니 당연). 저장 시에도 이 필드들은 요청 본문에서
 * 아예 빼서 보이지 않는 값이 조용히 덮어써지는 일이 없게 함.
 * [2026-09-12] 사업자등록증 재등록: 업로드 행 클릭 시 팝업으로 BizCertUpload를 다시
 * 띄운다(사용자 설계 - "등록 내역 있음 표시 + 팝업으로 변경"). 최초 등록과 동일한
 * handleBizCertConfirm을 그대로 재사용 - save_biz_cert_data()가 profile_id 기준으로
 * UPDATE/INSERT를 알아서 분기하므로 재등록 전용 API가 따로 필요 없다. 재등록 시
 * profile_business_types에 새 is_primary=true 행이 쌓이며 예전 행이 안 내려가던
 * 버그는 signup.py에서 같이 고침(기존 행 전부 false로 내린 뒤 새로 insert).
 * TODO로만 남긴 것: 프로필 사진 변경.
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
  regions: string[] | null;
  business_age_months: number | null;
  annual_revenue: number | null;
  employee_count: number | null;
  founder_age_group: string | null;
  company_size: string | null;
  ksic_code: string | null;
  ksic_name: string | null;
  has_biz_cert: boolean;
}

interface ProfileForm {
  name: string;
  bizName: string;
  industryDesc: string;
  regions: string[];
  monthsInBusiness: string;
  employees: string;
  annualRevenue: string;
  ownerAgeGroup: string;
  companySize: string;
}

/** 초기값 - API 응답 오기 전 잠깐 보이는 값이라 전부 빈 값/미선택으로 둔다.
 * [2026-09-11] 예전엔 "물꼬 커피"/"커피전문점"/"마포구"/"30대" 같은 프로토타입 더미값을
 * 썼는데, API가 null을 내려줘도(사업자등록증 막 등록해서 업종·지역·연령대는 아직
 * 없는 게 정상인 경우) 이 더미값으로 덮여서 "실제로 값이 있는 것처럼" 보이는 버그가
 * 있었다(실측 확인 - 사업자등록증 등록해도 화면이 안 바뀌는 것처럼 보임). name만
 * 예외로 실제 더미를 유지 - 계정 이름은 회원가입 때부터 항상 값이 있어서 null이
 * 나올 일이 없음. */
const INITIAL_FORM: ProfileForm = {
  name: "김창업",
  bizName: "",
  industryDesc: "",
  regions: [],
  monthsInBusiness: "0",
  employees: "0",
  annualRevenue: "0원",
  ownerAgeGroup: "미선택",
  companySize: "미선택",
};

// [2026-09-12] "사업장 지역" 하나(문자열)에서 여러 개(칩) 방식으로 전환 - 사용자 확인.
// 기존사업자는 사업자등록증 business_address에서 자동으로 뽑은 시/도가 기본으로 들어가고
// (사실 기반), 예비창업자는 자동으로 채울 사업자등록증 자체가 없으니 처음엔 빈 채로 시작해
// 사용자가 직접 "지원받고 싶은 지역"을 칩으로 추가한다(선호 기반) - 둘 다 여러 개일 수
// 있어서(법인은 본점·사업장 시/도가 다를 수 있고, 예비창업자는 애초에 여러 지역에 관심
// 가질 수 있음) DB도 배열(regions TEXT[])로 바꿈. 이전엔 마포구/서대문구/은평구(구 단위)
// 3개짜리 셀렉트였는데, 실제 공고 매칭 필터(announcements.regions)가 구 단위를 아예 안
// 담고 시/도까지만 있어서(matching.py 참고) 그 단위에 맞는 시/도 17개로 교체.
// backend/auth/signup.py::SIDO_NAMES와 반드시 동일한 목록으로 유지할 것.
const SIDO_OPTIONS = [
  "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시",
  "울산광역시", "세종특별자치시", "경기도", "강원특별자치도", "충청북도", "충청남도",
  "전북특별자치도", "전라남도", "경상북도", "경상남도", "제주특별자치도",
];

// backend/auth/signup.py::derive_sido_from_address()와 동일 로직 - 사업자등록증
// OCR 확인 즉시 화면에 반영하려고 프론트에서도 미리 계산한다(백엔드 저장 완료를
// 기다렸다가 재조회하지 않음, bizName/ksic_code와 동일한 낙관적 업데이트 패턴).
function deriveSidoFromAddress(address: string | undefined): string | null {
  if (!address) return null;
  const text = address.trim();
  return SIDO_OPTIONS.find((sido) => text.startsWith(sido)) ?? null;
}
const AGE_GROUP_OPTIONS = ["미선택", "10대", "20대", "30대", "40대", "50대 이상"];
// "미선택"은 저장 시 null로 보냄(company_size 초기화). 소상공인기본법상
// 상시근로자수·매출 기준(제조업 등은 10인 미만, 그 외 5인 미만)을 직접 계산해
// 자동 채우는 로직은 다음 과제 - 지금은 사용자가 직접 고른다.
const COMPANY_SIZE_OPTIONS = ["미선택", "소상공인", "중소기업", "창업벤처"];

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
  // null = 아직 조회 전. [2026-09-10] 예비창업자(사업자등록증 없음)는 상호명/업력/
  // 직원수/연매출을 알 수도, 입력할 수도 없는 값이라 - 실측으로도 예비창업자 8명
  // 전원 이 4개 필드가 NULL이었음(사용자 확인) - profile_type 기준으로 그 4개
  // 필드를 숨기고 안내 문구로 대체한다.
  const [profileType, setProfileType] = useState<string | null>(null);
  // 기업유형 표시용("개인"/"법인") - entity_types.name, OCR 성공 전까지 null(예비창업자 문구로 대체됨).
  const [entityTypeName, setEntityTypeName] = useState<string | null>(null);
  // [2026-09-11] 사업자등록증 등록 시 검색/확정한 업종코드(KSIC) - "업종 설명(원문)"
  // (industry_text)과는 별개 테이블(profile_business_types)이라 따로 상태로 둠.
  const [ksicCode, setKsicCode] = useState<string | null>(null);
  const [ksicName, setKsicName] = useState<string | null>(null);
  // [2026-09-12] 사업자등록증 재등록 팝업 열림 상태.
  const [bizCertPopupOpen, setBizCertPopupOpen] = useState(false);

  const userId = getUserId() ?? FALLBACK_USER_ID;
  const isProspective = profileType === "예비창업자";

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/mypage/profile?user_id=${userId}`)
      .then((res) => res.json())
      .then((res: { success: boolean; data?: ProfileApiData }) => {
        if (!res.success || !res.data) return;
        const d = res.data;
        setEmail(d.email);
        setHasBizCert(d.has_biz_cert);
        setProfileType(d.profile_type);
        setEntityTypeName(d.entity_type_name);
        setKsicCode(d.ksic_code);
        setKsicName(d.ksic_name);
        setForm((prev) => ({
          ...prev,
          name: d.name ?? prev.name,
          // [2026-09-10] 값이 없을 때 더미값(prev)으로 남겨두면 예비창업자 화면에
          // "물꼬 커피" 같은 가짜 상호명이 실제 값인 것처럼 보이는 버그가 있었음
          // (실측 확인) - 빈 문자열로 고침. 어차피 예비창업자는 이 필드 자체를
          // 아래에서 숨기지만, 안전하게 데이터도 맞춰둔다.
          bizName: d.business_name ?? "",
          industryDesc: d.industry_text ?? "",
          regions: d.regions ?? [],
          monthsInBusiness: d.business_age_months != null ? String(d.business_age_months) : "",
          employees: d.employee_count != null ? String(d.employee_count) : "",
          annualRevenue: d.annual_revenue != null ? String(d.annual_revenue) : "",
          ownerAgeGroup: d.founder_age_group ?? "미선택",
          companySize: d.company_size ?? "미선택",
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
    // backend/auth/signup.py::save_biz_cert_data()가 이 시점에 business_profiles.
    // profile_type을 "기존사업자"로 바꿔주므로, 화면도 같이 맞춰야 업력/직원수/
    // 연매출 입력창이 새로고침 없이 바로 나타난다.
    setProfileType("기존사업자");
    // fields.entity_type은 OCR 확인 팝업에서 넘어온 "법인"/"개인" 원문 그대로 -
    // entity_types.name과 표기가 같아서 그대로 써도 된다(재조회 없이 즉시 반영용).
    if (fields.entity_type) setEntityTypeName(fields.entity_type);
    if (fields.company_name) {
      setForm((prev) => ({ ...prev, bizName: fields.company_name }));
    }
    // [2026-09-12] 사업장 지역 - business_address에서 뽑아낸 시/도로 자동 채움.
    // 못 뽑으면(주소 미인식 등) 기존 선택값 그대로 둔다. 뽑혔으면 기존 칩을 지우지
    // 않고 없을 때만 추가 - 사용자가 직접 추가해둔 다른 지역(칩)을 재등록 때마다
    // 덮어써서 날리면 안 됨.
    const derivedRegion = deriveSidoFromAddress(fields.business_address);
    if (derivedRegion) {
      setForm((prev) =>
        prev.regions.includes(derivedRegion) ? prev : { ...prev, regions: [...prev.regions, derivedRegion] },
      );
    }
    if (fields.ksic_code) {
      setKsicCode(fields.ksic_code);
      setKsicName(fields.ksic_name || null);
    }
    // 재등록 팝업에서 온 경우 닫는다 - 최초 등록(hasBizCert===false) 경로는 팝업을
    // 안 쓰므로 이미 false라 아무 효과 없음.
    setBizCertPopupOpen(false);
  };

  // input/select 공통 핸들러 — name 속성으로 어떤 필드인지 구분한다.
  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  // [2026-09-12] 지역 칩 추가/삭제 - 드롭다운에서 고르면 즉시 칩으로 추가되고
  // 드롭다운은 다시 placeholder로 돌아간다(select 자체를 값 저장소로 안 씀).
  const addRegion = (sido: string) => {
    if (!sido) return;
    setForm((prev) => (prev.regions.includes(sido) ? prev : { ...prev, regions: [...prev.regions, sido] }));
  };

  const removeRegion = (sido: string) => {
    setForm((prev) => ({ ...prev, regions: prev.regions.filter((r) => r !== sido) }));
  };

  const handleBack = () => {
    navigate("/mypage");
  };

  const handlePasswordChangeClick = () => {
    // TODO: 비밀번호 변경 (현재/새 비밀번호 입력 폼 + 백엔드 검증) — 시간 부족으로
    // 버튼만 존재, 기능은 없음(사용자 확인, 2026-09-12) - 아이디/비밀번호 찾기 스텁과 동일.
  };

  const handlePhotoChange = () => {
    // TODO: 프로필 사진 변경 (이미지 선택/업로드) — 이번 범위 아님
  };

  const handleBizCertClick = () => {
    setBizCertPopupOpen(true);
  };

  const closeBizCertPopup = () => {
    setBizCertPopupOpen(false);
  };

  const handleSave = async () => {
    // 예비창업자는 상호명/업력/직원수/연매출 입력창 자체를 안 보여주므로, 저장 요청에도
    // 안 실어보낸다(키를 아예 빼면 백엔드가 exclude_unset으로 그 컬럼은 안 건드림) -
    // 안 그러면 화면에 안 보이는 필드의 빈 값(""→null)이 조용히 덮어써질 수 있음.
    const body: Record<string, string | number | string[] | null> = {
      name: form.name || null,
      industry_text: form.industryDesc || null,
      regions: form.regions.length > 0 ? form.regions : null,
      founder_age_group: form.ownerAgeGroup !== "미선택" ? form.ownerAgeGroup : null,
    };
    if (!isProspective) {
      body.business_name = form.bizName || null;
      body.business_age_months = form.monthsInBusiness ? Number(form.monthsInBusiness) : null;
      body.annual_revenue = form.annualRevenue ? Number(form.annualRevenue) : null;
      body.employee_count = form.employees ? Number(form.employees) : null;
      body.company_size = form.companySize !== "미선택" ? form.companySize : null;
    }

    try {
      await fetch(`${API_BASE_URL}/api/mypage/profile?user_id=${getUserId() ?? FALLBACK_USER_ID}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
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
          <button type="button" className={styles.avatarChange} onClick={handlePasswordChangeClick}>
            비밀번호 변경
          </button>
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
              {/* [2026-09-12] 이미지 썸네일처럼 보이던 아이콘은 빼고(원본 이미지는 저장 안
                  함), 대신 서류 자체를 뜻하는 문서 아이콘으로 교체 - DocPreview.tsx의
                  .docIcon(서류 미리보기 화면)과 동일한 svg 재사용. */}
              <span className={styles.bizThumb} aria-hidden="true">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
                  <path d="M14 3v5h5" />
                  <path d="M9 13h6" />
                  <path d="M9 17h6" />
                </svg>
              </span>
              <span className={styles.bizUploadText}>
                <span className={styles.bizUploadTitle}>사업자등록증 업로드</span>
                <span className={styles.bizUploadSub}>사진 또는 PDF</span>
              </span>
            </button>
          ) : null}

          {!isProspective && (
            <TextField
              label="상호명"
              name="bizName"
              value={form.bizName}
              onChange={handleChange}
            />
          )}
          <TextField
            label="업종 설명(원문)"
            name="industryDesc"
            value={form.industryDesc}
            onChange={handleChange}
          />

          {/* [2026-09-11] 사업자등록증 등록 시 검색/확정한 업종코드 - industryDesc(원문
              설명)와 별개로 profile_business_types에 저장된 값을 읽기전용으로 보여줌.
              아직 없으면(코드 미확정) 아예 안 보여줌. */}
          {ksicCode && (
            <TextField
              label="선택한 업종(KSIC)"
              name="ksic"
              value={ksicName ? `${ksicName} (${ksicCode})` : ksicCode}
              readOnly
            />
          )}

          {/* [2026-09-12] 문자열 하나(SelectField) 대신 칩 목록 - 기존사업자는 사업자
              등록증에서 자동으로 채워진 지역이 기본으로 들어있고(사실), 예비창업자는
              빈 채로 시작해 지원받고 싶은 지역을 직접 추가한다(선호). 둘 다 여러 개 가능. */}
          <div className={styles.field}>
            <span className={styles.label}>사업장 지역</span>
            {form.regions.length > 0 && (
              <div className={styles.regionChipList}>
                {form.regions.map((sido) => (
                  <span key={sido} className={styles.regionChip}>
                    {sido}
                    <button
                      type="button"
                      className={styles.regionChipRemove}
                      onClick={() => removeRegion(sido)}
                      aria-label={`${sido} 삭제`}
                    >
                      ✕
                    </button>
                  </span>
                ))}
              </div>
            )}
            <div className={styles.selectWrap}>
              <select
                className={styles.select}
                value=""
                onChange={(e) => addRegion(e.target.value)}
              >
                <option value="" disabled>
                  지역 추가
                </option>
                {SIDO_OPTIONS.filter((sido) => !form.regions.includes(sido)).map((sido) => (
                  <option key={sido} value={sido}>
                    {sido}
                  </option>
                ))}
              </select>
              <Chevron />
            </div>
          </div>

          {isProspective ? (
            <p className={styles.groupSub}>
              업력·직원수·연매출은 사업자등록증을 등록하면 자동으로 채워져요.
            </p>
          ) : (
            <>
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
            </>
          )}

          <SelectField
            label="대표자 연령대"
            name="ownerAgeGroup"
            value={form.ownerAgeGroup}
            options={AGE_GROUP_OPTIONS}
            onChange={handleChange}
          />
          <TextField
            label="기업유형"
            name="entityType"
            value={isProspective ? "예비창업자" : entityTypeName ?? "-"}
            readOnly
          />

          {/* [2026-09-11] 기업 규모(중소/소상공인/창업벤처) - entity_type(개인/법인)과는
              다른 축(상시근로자수·매출 기준)이라 별도 항목으로 분리. 예비창업자는 분류할
              사업 자체가 없어 다른 사업자 전용 필드들과 같이 숨김. 전용 컬럼 없이
              business_profiles.profile_attributes(JSONB)에 저장 - 값은 사용자가 직접
              선택(법정 기준 자동 판정은 다음 과제, 사용자 확인). */}
          {!isProspective && (
            <SelectField
              label="기업 규모"
              name="companySize"
              value={form.companySize}
              options={COMPANY_SIZE_OPTIONS}
              onChange={handleChange}
            />
          )}
        </div>
      </div>

      {/* 하단 CTA: 저장하기 (→ 마이페이지) */}
      <div className={styles.footer}>
        <button type="button" className={styles.saveButton} onClick={handleSave}>
          저장하기
        </button>
      </div>

      {/* [2026-09-12] 사업자등록증 재등록 팝업 - onboarding.module.css의 동일 팝업
          패턴 재사용. BizCertUpload가 review 단계까지 자체적으로 화면을 관리하므로
          여기선 그냥 감싸기만 하면 됨(Onboarding.tsx처럼 deferStart로 별도 실행/진행
          버튼을 둘 필요 없음 - 최초 등록(hasBizCert===false)과 동일한 단순 패턴). */}
      {bizCertPopupOpen && (
        <div className={styles.bizPopupOverlay} onClick={closeBizCertPopup}>
          <div
            className={styles.bizPopupCard}
            role="dialog"
            aria-modal="true"
            aria-label="사업자등록증 재등록"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className={styles.bizPopupTitle}>사업자등록증 재등록</h2>
            <p className={styles.bizPopupSub}>
              새 사업자등록증을 올리면 회원님의 사업 정보가 최신 내용으로 갱신돼요.
            </p>
            <BizCertUpload onConfirm={handleBizCertConfirm} onSkip={closeBizCertPopup} />
            <button type="button" className={styles.bizPopupCancelBtn} onClick={closeBizCertPopup}>
              취소
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProfileEdit;
