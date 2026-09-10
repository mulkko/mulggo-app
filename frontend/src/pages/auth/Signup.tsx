import { useState, type SubmitEvent } from "react";
import { useNavigate } from "react-router-dom";
// [2026-09-10, 임시 주석] BizCertUpload를 쓰는 페이지 자체를 바꿀 예정이라 잠시 꺼둠.
// import BizCertUpload from "../../components/BizCertUpload/BizCertUpload";
import TermsModal from "../../components/TermsModal/TermsModal";
import backArrow from "../../assets/backArrow.svg";
import styles from "../../styles/signup.module.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

interface SignupResponse {
  success: boolean;
  data: { user_id: number; email: string; name: string } | null;
  error: { message: string; code: string } | null;
}

// 약관 "보기" 팝업에 넣을 내용. 실제 약관 페이지/문구가 아직 없어 placeholder만 둔다.
// TODO: 실제 약관 내용으로 교체 필요
const TERMS_CONTENT = {
  terms: {
    title: "서비스 이용약관",
    body: "이용약관 내용은 준비 중입니다. (추후 업데이트 예정)",
  },
  privacy: {
    title: "개인정보 수집 및 이용",
    body: "개인정보 수집 및 이용 안내는 준비 중입니다. (추후 업데이트 예정)",
  },
} as const;

type TermsKey = keyof typeof TERMS_CONTENT;

function Signup() {
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [agreePrivacy, setAgreePrivacy] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showToast, setShowToast] = useState(false);
  // 열려 있는 약관 팝업 (없으면 null). 화면 표시용, 서버와 무관.
  const [openTerms, setOpenTerms] = useState<TermsKey | null>(null);

  // [2026-09-10, 임시 주석] 사업자등록증: 확인/수정까지 끝낸 값(bizCertFile+bizCertFields)
  // 또는 "나중에 하기"(bizCertSkipped) 중 하나. 둘 다 비어있으면 아직 업로드 컴포넌트를 보여주는 중.
  // const [bizCertFile, setBizCertFile] = useState<File | null>(null);
  // const [bizCertFields, setBizCertFields] = useState<Record<string, string> | null>(null);
  // const [bizCertSkipped, setBizCertSkipped] = useState(false);

  // "전체 동의"는 서버로 보내지 않는 화면 편의 요소 — 필수 약관 두 개를 한 번에 토글만 한다.
  // (백엔드 /api/auth/signup 은 agree_terms, agree_privacy 만 받는다.)
  const agreeAll = agreeTerms && agreePrivacy;
  const handleAgreeAll = (checked: boolean) => {
    setAgreeTerms(checked);
    setAgreePrivacy(checked);
  };

  // const handleBizCertConfirm = (fields: Record<string, string>, file: File) => {
  //   setBizCertFields(fields);
  //   setBizCertFile(file);
  // };

  // const handleBizCertReset = () => {
  //   setBizCertFields(null);
  //   setBizCertFile(null);
  //   setBizCertSkipped(false);
  // };

  const handleSubmit = async (event: SubmitEvent) => {
    event.preventDefault();
    setErrorMessage("");

    if (password !== passwordConfirm) {
      setErrorMessage("비밀번호가 일치하지 않습니다.");
      return;
    }

    const formData = new FormData();
    formData.append("email", email);
    formData.append("name", name);
    formData.append("password", password);
    formData.append("password_confirm", passwordConfirm);
    formData.append("agree_terms", String(agreeTerms));
    formData.append("agree_privacy", String(agreePrivacy));
    // if (bizCertFile && bizCertFields) {
    //   formData.append("biz_cert_file", bizCertFile);
    //   formData.append("biz_cert_data", JSON.stringify(bizCertFields));
    // }

    setSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/signup`, {
        method: "POST",
        body: formData,
      });
      const data: SignupResponse = await response.json();

      if (data.success) {
        setShowToast(true);
        setTimeout(() => navigate("/onboarding"), 1400);
      } else {
        setErrorMessage(data.error?.message ?? "회원가입에 실패했습니다.");
      }
    } catch {
      setErrorMessage("서버에 연결할 수 없습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <button
          type="button"
          className={styles.back}
          onClick={() => navigate("/login")}
          aria-label="로그인 화면으로 돌아가기"
        >
          <img src={backArrow} alt="" />
        </button>
        <h1 className={styles.headerTitle}>회원가입</h1>
      </header>

      <form className={styles.form} onSubmit={handleSubmit}>
        <h2 className={styles.sectionTitle}>가입 정보</h2>

        <div className={styles.field}>
          <label htmlFor="email">아이디(이메일)</label>
          <input
            id="email"
            type="email"
            className={styles.input}
            placeholder="example@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="name">이름</label>
          <input
            id="name"
            type="text"
            className={styles.input}
            placeholder="김창업"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="password">비밀번호</label>
          <input
            id="password"
            type="password"
            className={styles.input}
            placeholder="영문·숫자·특수문자 조합 8자 이상"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="password-confirm">비밀번호 확인</label>
          <input
            id="password-confirm"
            type="password"
            className={styles.input}
            placeholder="비밀번호를 다시 입력해주세요"
            value={passwordConfirm}
            onChange={(e) => setPasswordConfirm(e.target.value)}
          />
        </div>

        {/* [2026-09-10, 임시 주석] 사업자등록증 업로드 - 사용 페이지 변경 예정이라 잠시 뺌.
        <div className={styles.bizField}>
          <div className={styles.bizRow}>
            <span className={styles.bizLabel}>사업자등록증 (선택)</span>
            <span className={styles.bizHint}>등록하면 매칭서비스를 바로 이용할 수 있어요</span>
          </div>
          {bizCertFields ? (
            <p className={styles.bizSummary}>
              사업자등록증 확인 완료 ✓{" "}
              <button type="button" className={styles.linkBtn} onClick={handleBizCertReset}>
                변경
              </button>
            </p>
          ) : bizCertSkipped ? (
            <p className={styles.bizSummary}>
              사업자등록증 나중에 등록{" "}
              <button type="button" className={styles.linkBtn} onClick={handleBizCertReset}>
                지금 등록
              </button>
            </p>
          ) : (
            <BizCertUpload
              onConfirm={handleBizCertConfirm}
              onSkip={() => setBizCertSkipped(true)}
            />
          )}
        </div>
        */}

        <div className={styles.divider} />

        <div className={styles.agreeGroup}>
          <label className={styles.agreeAll}>
            <input
              type="checkbox"
              className={`${styles.checkbox} ${styles.checkboxAll}`}
              checked={agreeAll}
              onChange={(e) => handleAgreeAll(e.target.checked)}
            />
            전체 동의
          </label>

          <div className={styles.agreeRow}>
            <label className={styles.agreeItem}>
              <input
                type="checkbox"
                className={styles.checkbox}
                checked={agreeTerms}
                onChange={(e) => setAgreeTerms(e.target.checked)}
              />
              (필수) 서비스 이용약관 동의
            </label>
            <button
              type="button"
              className={styles.agreeView}
              onClick={() => setOpenTerms("terms")}
            >
              보기
            </button>
          </div>

          <div className={styles.agreeRow}>
            <label className={styles.agreeItem}>
              <input
                type="checkbox"
                className={styles.checkbox}
                checked={agreePrivacy}
                onChange={(e) => setAgreePrivacy(e.target.checked)}
              />
              (필수) 개인정보 수집 및 이용 동의
            </label>
            <button
              type="button"
              className={styles.agreeView}
              onClick={() => setOpenTerms("privacy")}
            >
              보기
            </button>
          </div>
        </div>

        <button type="submit" className={styles.submitBtn} disabled={submitting || showToast}>
          {submitting ? "가입 중..." : "가입하기"}
        </button>

        {errorMessage && <p className={styles.error}>{errorMessage}</p>}
      </form>

      {showToast && (
        <div className={styles.toast} role="status">
          가입이 완료되었습니다
        </div>
      )}

      {openTerms && (
        <TermsModal
          title={TERMS_CONTENT[openTerms].title}
          body={TERMS_CONTENT[openTerms].body}
          onClose={() => setOpenTerms(null)}
        />
      )}
    </div>
  );
}

export default Signup;
