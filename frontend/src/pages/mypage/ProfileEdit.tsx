import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/profileEditV2.module.css";
import { getUserId } from "../../auth/session";
import BizCertUpload from "../../components/BizCertUpload/BizCertUpload";
import BottomNav from "../../components/BottomNav/BottomNav";
import { TextField, SelectField } from "../../components/FormField/FormField";
import SelectSheet from "../../components/SelectSheet/SelectSheet";
import logo from "../../assets/logo.svg";

/**
 * 프로필 수정 화면 (17-1).
 *
 * [2026-09-14] 팀원이 만든 ProfileEditV2.tsx(/edit-v2, 정적 목업 - 데이터 연동 없음)의
 * "기본정보/사업자정보/기타정보" 3분할 디자인을 이 화면(실제 기능이 붙은 화면)에
 * 이식했다 - 기능은 100% 그대로 유지, 디자인(레이아웃·CSS)만 profileEditV2.module.css로
 * 교체. "사업자 정보" 섹션은 V2에선 정적 입력창이었지만, 여기선 biz_registration_docs
 * 원본 데이터(사업자번호/법인등록번호/대표자명/개업연월일/생년월일/사업장·본점소재지/
 * 업태·종목)를 실제로 읽기전용 표시한다 - 전부 사업자등록증 OCR로 확정된 값이라
 * 이 화면에서 직접 수정 불가, 바꾸려면 재등록 팝업으로 새 사업자등록증을 올려야 함
 * (기존 "기업유형"과 동일한 원칙). V2의 "자격/우대" 필드는 대응하는 백엔드 컬럼이
 * 없어서 이번 포팅에서 제외했다 - 연결할 데이터가 없는 채로 두면 오히려 혼란만
 * 줄 것 같아서(사용자 확인 필요 시 별도 컬럼 설계부터).
 *
 * 마이페이지(`/mypage`)의 프로필 요약 카드를 누르면 `/mypage/edit`로 들어온다.
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
 * 바꿀 수 있는 값이 아니라서 select 아님 - V2 목업은 select였지만 실제 업무 규칙상
 * 틀린 것이라 여기선 반영 안 함). "기업 규모"(중소/소상공인/창업벤처,
 * 「소상공인기본법」상 상시근로자수·매출 기준 - entity_type과는 다른 축)는 완전히
 * 별개 항목으로 분리했고, 전용 컬럼 없이 business_profiles.profile_attributes
 * (JSONB)에 company_size 키로 저장한다(2026-09-11, 사용자 확인).
 *
 * 실제 동작: 뒤로가기(→ /mypage), 저장하기(→ API PUT 후 /mypage).
 * [2026-09-10] 이름 저장도 연동함 - business_profiles가 아니라 users.name이라
 * backend/api/mypage.py에서 fields에서 따로 빼서 별도 UPDATE users 문으로 처리.
 * [2026-09-10] 예비창업자는 상호명/업력/직원수/연매출 입력창을 숨기고 안내 문구로
 * 대체함(profile_type 기준).
 * [2026-09-12] 사업자등록증 재등록: 업로드 행 클릭 시 팝업으로 BizCertUpload를 다시
 * 띄운다(사용자 설계 - "등록 내역 있음 표시 + 팝업으로 변경"). 최초 등록과 동일한
 * handleBizCertConfirm을 그대로 재사용.
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
  business_category: string | null;
  business_item: string | null;
  has_biz_cert: boolean;
  biz_no: string | null;
  corp_no: string | null;
  biz_doc_company_name: string | null;
  ceo_name: string | null;
  open_date: string | null;
  birth_date: string | null;
  business_address: string | null;
  head_address: string | null;
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
  // [2026-09-14, 사용자 확인] V2 목업에 있던 "자격/우대" - 대응하는 백엔드 컬럼이
  // 없어서 화면에만 두고 저장은 안 한다(handleSave의 PUT 요청 본문에 안 넣음).
  // 컬럼이 생기면 그때 실제로 연결.
  qualifications: string;
}

/** "사업자 정보" 섹션 - biz_registration_docs 원본, 전부 읽기전용(OCR 확정값). */
interface BizDocInfo {
  bizNo: string | null;
  corpNo: string | null;
  companyName: string | null;
  repName: string | null;
  openDate: string | null;
  birthDate: string | null;
  bizAddress: string | null;
  headAddress: string | null;
  bizType: string | null;
}

const EMPTY_BIZ_DOC: BizDocInfo = {
  bizNo: null,
  corpNo: null,
  companyName: null,
  repName: null,
  openDate: null,
  birthDate: null,
  bizAddress: null,
  headAddress: null,
  bizType: null,
};

/** 업태/종목 두 값을 "업태 / 종목" 한 줄로 합친다. 하나만 있으면 그것만, 둘 다 없으면 null. */
function combineBizType(category: string | null, item: string | null): string | null {
  const parts = [category, item].filter((v): v is string => Boolean(v && v.trim()));
  return parts.length > 0 ? parts.join(" / ") : null;
}

/** 초기값 - API 응답 오기 전 잠깐 보이는 값이라 전부 빈 값/미선택으로 둔다. */
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
  qualifications: "",
};

// [2026-09-12] "사업장 지역" 하나(문자열)에서 여러 개(칩) 방식으로 전환.
// backend/auth/signup.py::SIDO_NAMES와 반드시 동일한 목록으로 유지할 것.
const SIDO_OPTIONS = [
  "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시",
  "울산광역시", "세종특별자치시", "경기도", "강원특별자치도", "충청북도", "충청남도",
  "전북특별자치도", "전라남도", "경상북도", "경상남도", "제주특별자치도",
];

// backend/auth/signup.py::derive_sido_from_address()와 동일 로직.
function deriveSidoFromAddress(address: string | undefined): string | null {
  if (!address) return null;
  const text = address.trim();
  return SIDO_OPTIONS.find((sido) => text.startsWith(sido)) ?? null;
}
const AGE_GROUP_OPTIONS = ["미선택", "10대", "20대", "30대", "40대", "50대 이상"];
const COMPANY_SIZE_OPTIONS = ["미선택", "소상공인", "중소기업", "창업벤처"];

function ProfileEdit() {
  const navigate = useNavigate();
  const [form, setForm] = useState<ProfileForm>(INITIAL_FORM);
  const [email, setEmail] = useState(DEFAULT_READONLY_EMAIL);
  // null = 아직 조회 전(깜빡임 방지용 - 조회 끝나기 전엔 업로드/정적표시 둘 다 안 보임)
  const [hasBizCert, setHasBizCert] = useState<boolean | null>(null);
  const [profileType, setProfileType] = useState<string | null>(null);
  // 기업유형 표시용("개인"/"법인") - entity_types.name, OCR 성공 전까지 null(예비창업자 문구로 대체됨).
  const [entityTypeName, setEntityTypeName] = useState<string | null>(null);
  // [2026-09-11] 사업자등록증 등록 시 검색/확정한 업종코드(KSIC).
  const [ksicCode, setKsicCode] = useState<string | null>(null);
  const [ksicName, setKsicName] = useState<string | null>(null);
  // [2026-09-14] "사업자 정보" 섹션 - biz_registration_docs 원본, 전부 읽기전용.
  const [bizDoc, setBizDoc] = useState<BizDocInfo>(EMPTY_BIZ_DOC);
  // [2026-09-12] 사업자등록증 재등록 팝업 열림 상태.
  const [bizCertPopupOpen, setBizCertPopupOpen] = useState(false);

  const userId = getUserId() ?? FALLBACK_USER_ID;
  const isProspective = profileType === "예비창업자";

  // [2026-09-15] 사업자등록증 등록 직후 "재등록 영역"이 안 보이는 버그 수정 - 마운트 시
  // 보낸 프로필 조회가 네트워크 지연(Supabase 클라우드 DB)으로 늦게 응답하면, 그 사이
  // handleBizCertConfirm이 낙관적으로 갱신한 최신 state를 옛날 값으로 덮어써버렸다.
  // 요청마다 증가하는 시퀀스 번호로 "가장 최근에 시작한 요청"의 응답만 반영한다.
  const latestProfileFetchId = useRef(0);

  useEffect(() => {
    const fetchId = ++latestProfileFetchId.current;
    fetch(`${API_BASE_URL}/api/mypage/profile?user_id=${userId}`)
      .then((res) => res.json())
      .then((res: { success: boolean; data?: ProfileApiData }) => {
        if (fetchId !== latestProfileFetchId.current) return; // 그 사이 더 최신 값이 반영됨 - 무시
        if (!res.success || !res.data) return;
        const d = res.data;
        setEmail(d.email);
        setHasBizCert(d.has_biz_cert);
        setProfileType(d.profile_type);
        setEntityTypeName(d.entity_type_name);
        setKsicCode(d.ksic_code);
        setKsicName(d.ksic_name);
        setBizDoc({
          bizNo: d.biz_no,
          corpNo: d.corp_no,
          companyName: d.biz_doc_company_name,
          repName: d.ceo_name,
          openDate: d.open_date,
          birthDate: d.birth_date,
          bizAddress: d.business_address,
          headAddress: d.head_address,
          bizType: combineBizType(d.business_category, d.business_item),
        });
        setForm((prev) => ({
          ...prev,
          name: d.name ?? prev.name,
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

  // BizCertUpload가 OCR 확인/수정까지 끝낸 값을 넘겨주면, 재OCR 없이 그대로 저장만 한다.
  const handleBizCertConfirm = async (fields: Record<string, string>, file: File) => {
    // 아직 응답 안 온 예전 프로필 조회가 있다면 무효화 - 뒤늦게 응답 와도 아래 낙관적
    // 업데이트를 덮어쓰지 못하게 막는다.
    latestProfileFetchId.current++;
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
    setProfileType("기존사업자");
    if (fields.entity_type) setEntityTypeName(fields.entity_type);
    if (fields.company_name) {
      setForm((prev) => ({ ...prev, bizName: fields.company_name }));
    }
    // [2026-09-14] "사업자 정보" 섹션도 같이 낙관적 업데이트 - head_address는 OCR
    // 리뷰 필드 목록(BizCertUpload.tsx REVIEW_FIELDS)에 없어서 fields에 안 들어있음,
    // 기존 값 그대로 둔다(어차피 지금까지 항상 비어있었음).
    setBizDoc((prev) => ({
      bizNo: fields.biz_no || prev.bizNo,
      corpNo: fields.corp_no || prev.corpNo,
      companyName: fields.company_name || prev.companyName,
      repName: fields.ceo_name || prev.repName,
      openDate: fields.open_date || prev.openDate,
      birthDate: fields.birth_date || prev.birthDate,
      bizAddress: fields.business_address || prev.bizAddress,
      headAddress: prev.headAddress,
      bizType: combineBizType(
        fields.business_category || null,
        fields.business_item || null,
      ) ?? prev.bizType,
    }));
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
    setBizCertPopupOpen(false);
  };

  // input/select 공통 핸들러 — name 속성으로 어떤 필드인지 구분한다.
  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

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
    // TODO: 비밀번호 변경 — 시간 부족으로 버튼만 존재, 기능은 없음(사용자 확인).
  };

  const handlePhotoChange = () => {
    // TODO: 프로필 사진 변경 — 이번 범위 아님
  };

  const handleBizCertClick = () => {
    setBizCertPopupOpen(true);
  };

  const closeBizCertPopup = () => {
    setBizCertPopupOpen(false);
  };

  const handleSave = async () => {
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
      {/* "MULKKO PAGE" 브랜드 행 - MyPage.tsx와 같은 그룹, 모든 화면 공통 방침(2026-09-13) */}
      <div className={styles.brandRow}>
        <span className={styles.logo}>
          <span className={styles.logoText}>MULKKO PAGE</span>
          <img src={logo} alt="물꼬 로고" className={styles.logoMark} />
        </span>
      </div>

      <header className={styles.header}>
        <button type="button" className={styles.backButton} onClick={handleBack} aria-label="뒤로가기">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M16 5l-8 7 8 7" />
          </svg>
        </button>
        <span className={styles.headerTitle}>프로필 수정</span>
      </header>

      <div className={styles.scrollArea}>
        {/* 프로필 사진 + "사진 변경"(TODO) — V2 디자인대로 로고 이미지 사용 */}
        <div className={styles.avatarBlock}>
          <span className={styles.avatar} aria-hidden="true">
            <img src={logo} alt="" style={{ width: 46, height: "auto", display: "block" }} />
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
          <button type="button" className={styles.avatarChange} onClick={handlePasswordChangeClick}>
            비밀번호 변경
          </button>
        </div>

        <div className={styles.divider} />

        {/* 사업자 정보 — biz_registration_docs 원본(전부 읽기전용, OCR 확정값) */}
        <div className={styles.group}>
          <div className={styles.groupHeadRow}>
            <div className={styles.groupHead}>
              <span className={styles.groupTitle}>사업자 정보</span>
              <span className={styles.groupSub}>
                사업자등록증에 등록된 원본 정보예요. 바꾸려면 사업자등록증을 다시 올려주세요.
              </span>
            </div>
            {hasBizCert === true && (
              <button type="button" className={styles.avatarChange} onClick={handleBizCertClick}>
                변경하기
              </button>
            )}
          </div>

          {hasBizCert === false ? (
            <div className={styles.field}>
              <span className={styles.label}>사업자등록증 (등록된 사업자등록증이 없어요)</span>
              <BizCertUpload onConfirm={handleBizCertConfirm} onSkip={() => {}} />
            </div>
          ) : hasBizCert === true ? (
            <>
              <button type="button" className={styles.bizUpload} onClick={handleBizCertClick}>
                <span className={styles.bizThumb} aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
                    <path d="M14 3v5h5" />
                    <path d="M9 13h6" />
                    <path d="M9 17h6" />
                  </svg>
                </span>
                <span className={styles.bizUploadText}>
                  <span className={styles.bizUploadTitle}>사업자등록증 재등록</span>
                  <span className={styles.bizUploadSub}>탭해서 새 사업자등록증 올리기</span>
                </span>
              </button>

              <TextField styles={styles} label="사업자번호" name="bizNo" value={bizDoc.bizNo ?? "-"} inter readOnly />
              {bizDoc.corpNo && (
                <TextField styles={styles} label="법인등록번호" name="corpNo" value={bizDoc.corpNo} inter readOnly />
              )}
              <TextField styles={styles}
                label="상호명/법인명"
                name="bizDocCompanyName"
                value={bizDoc.companyName ?? "-"}
                readOnly
              />
              <TextField styles={styles} label="대표자명" name="repName" value={bizDoc.repName ?? "-"} readOnly />
              <TextField styles={styles} label="개업연월일" name="openDate" value={bizDoc.openDate ?? "-"} inter readOnly />
              {bizDoc.birthDate && (
                <TextField styles={styles} label="생년월일" name="birthDate" value={bizDoc.birthDate} inter readOnly />
              )}
              <TextField styles={styles} label="사업장소재지" name="bizAddress" value={bizDoc.bizAddress ?? "-"} readOnly />
              <TextField styles={styles} label="본점소재지" name="headAddress" value={bizDoc.headAddress ?? "-"} readOnly />
              <TextField styles={styles} label="업태/종목" name="bizType" value={bizDoc.bizType ?? "-"} readOnly />
            </>
          ) : null}
        </div>

        <div className={styles.divider} />

        {/* 기타 정보 — business_profiles (사용자가 직접 입력/수정) */}
        <div className={styles.group}>
          <span className={styles.groupTitle}>기타 정보</span>

          <div className={styles.row}>
            <TextField styles={styles}
              label="사용자 유형"
              name="userType"
              value={isProspective ? "예비창업자" : "기존사업자"}
              readOnly
            />
            <TextField styles={styles}
              label="사업자구분"
              name="entityType"
              value={isProspective ? "예비창업자" : entityTypeName ?? "-"}
              readOnly
            />
          </div>

          {!isProspective && (
            <TextField styles={styles}
              label="상호명"
              name="bizName"
              value={form.bizName}
              onChange={handleChange}
            />
          )}
          <TextField styles={styles}
            label="업종 설명(원문)"
            name="industryDesc"
            value={form.industryDesc}
            onChange={handleChange}
          />

          {ksicCode && (
            <TextField styles={styles}
              label="선택한 업종(KSIC)"
              name="ksic"
              value={ksicName ? `${ksicName} (${ksicCode})` : ksicCode}
              readOnly
            />
          )}

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
          </div>
          {/* [2026-09-14] 네이티브 select 대신 SelectSheet(하단 시트 팝업) - "지역 추가"는
              고른 즉시 칩으로 옮겨가고 자기 자신은 항상 빈 값(value="")으로 리셋되는
              add-menu라 FormField.tsx의 SelectField(값 바인딩형)로는 안 맞아 직접 씀. */}
          <SelectSheet
            label="지역 추가"
            name="regionAdd"
            value=""
            placeholder="지역 선택"
            options={SIDO_OPTIONS.filter((sido) => !form.regions.includes(sido)).map((sido) => ({
              label: sido,
              value: sido,
            }))}
            onChange={addRegion}
          />

          {isProspective ? (
            <p className={styles.groupSub}>
              업력·직원수·연매출은 사업자등록증을 등록하면 자동으로 채워져요.
            </p>
          ) : (
            <>
              <div className={styles.row}>
                <TextField styles={styles}
                  label="업력(개월)"
                  name="monthsInBusiness"
                  value={form.monthsInBusiness}
                  onChange={handleChange}
                  inter
                />
                <TextField styles={styles}
                  label="직원수"
                  name="employees"
                  value={form.employees}
                  onChange={handleChange}
                  inter
                />
              </div>

              <TextField styles={styles}
                label="연매출"
                name="annualRevenue"
                value={form.annualRevenue}
                onChange={handleChange}
                inter
              />
            </>
          )}

          <div className={styles.row}>
            <SelectField styles={styles}
              label="대표자 연령대"
              name="ownerAgeGroup"
              value={form.ownerAgeGroup}
              options={AGE_GROUP_OPTIONS}
              onChange={handleChange}
            />
            {/* [2026-09-14] V2 목업에 있던 필드 - 대응 백엔드 컬럼이 아직 없어서 저장은
                안 되고 화면에만 있음(handleSave 참고). */}
            <TextField styles={styles}
              label="자격/우대"
              name="qualifications"
              value={form.qualifications}
              onChange={handleChange}
            />
          </div>

          {!isProspective && (
            <SelectField styles={styles}
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

      {/* 사업자등록증 재등록 팝업 */}
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

      <BottomNav active="my" />
    </div>
  );
}

export default ProfileEdit;
