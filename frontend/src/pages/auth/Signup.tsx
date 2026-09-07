import { useState, type SubmitEvent } from "react";
import { useNavigate } from "react-router-dom";
import BizCertUpload from "../../components/BizCertUpload/BizCertUpload";
import styles from "../../styles/login.module.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

interface SignupResponse {
  success: boolean;
  data: { user_id: number; email: string; name: string } | null;
  error: { message: string; code: string } | null;
}

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

  // 사업자등록증: 확인/수정까지 끝낸 값(bizCertFile+bizCertFields) 또는 "나중에 하기"(bizCertSkipped) 중 하나.
  // 둘 다 비어있으면 아직 업로드 컴포넌트를 보여주는 중.
  const [bizCertFile, setBizCertFile] = useState<File | null>(null);
  const [bizCertFields, setBizCertFields] = useState<Record<string, string> | null>(null);
  const [bizCertSkipped, setBizCertSkipped] = useState(false);

  const handleBizCertConfirm = (fields: Record<string, string>, file: File) => {
    setBizCertFields(fields);
    setBizCertFile(file);
  };

  const handleBizCertReset = () => {
    setBizCertFields(null);
    setBizCertFile(null);
    setBizCertSkipped(false);
  };

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
    if (bizCertFile && bizCertFields) {
      formData.append("biz_cert_file", bizCertFile);
      formData.append("biz_cert_data", JSON.stringify(bizCertFields));
    }

    setSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/signup`, {
        method: "POST",
        body: formData,
      });
      const data: SignupResponse = await response.json();

      if (data.success) {
        navigate("/login");
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
    <div className={styles.loginPage}>
      <div className={styles.titBox}>
        <p className={styles.logo}><a href="#none">mulkko로고</a></p>
        <h1>회원가입</h1>
      </div>
      <div className={styles.loginBox}>
        <form onSubmit={handleSubmit}>
          <div className={styles.formField}>
            <label htmlFor="name">이름</label>
            <input
              id="name"
              type="text"
              className="text-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className={styles.formField}>
            <label htmlFor="email">이메일</label>
            <input
              id="email"
              type="email"
              className="text-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className={styles.formField}>
            <label htmlFor="password">비밀번호</label>
            <input
              id="password"
              type="password"
              className="text-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div className={styles.formField}>
            <label htmlFor="password-confirm">비밀번호 확인</label>
            <input
              id="password-confirm"
              type="password"
              className="text-input"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
            />
          </div>
          <div className={styles.formField}>
            {bizCertFields ? (
              <p>
                사업자등록증 확인 완료 ✓{" "}
                <button type="button" onClick={handleBizCertReset}>
                  변경
                </button>
              </p>
            ) : bizCertSkipped ? (
              <p>
                사업자등록증 나중에 등록{" "}
                <button type="button" onClick={handleBizCertReset}>
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
          <div className={styles.formField}>
            <label htmlFor="agree-terms">
              <input
                id="agree-terms"
                type="checkbox"
                checked={agreeTerms}
                onChange={(e) => setAgreeTerms(e.target.checked)}
              />
              {" "}이용약관 동의
            </label>
          </div>
          <div className={styles.formField}>
            <label htmlFor="agree-privacy">
              <input
                id="agree-privacy"
                type="checkbox"
                checked={agreePrivacy}
                onChange={(e) => setAgreePrivacy(e.target.checked)}
              />
              {" "}개인정보처리방침 동의
            </label>
          </div>
          <button type="submit" className="btnPrimary" disabled={submitting}>
            {submitting ? "가입 중..." : "회원가입"}
          </button>
        </form>

        {errorMessage && <p>{errorMessage}</p>}
      </div>
    </div>
  );
}

export default Signup;
