import { useState, type SubmitEvent } from "react";
import styles from "../../styles/login.module.css";

function Signup() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [nickname, setNickname] = useState("");
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [agreePrivacy, setAgreePrivacy] = useState(false);

  // TODO: 회원가입 로직 대기 중 — 백엔드 연동 확정되면 /auth/signup fetch 붙이기
  const handleSubmit = (event: SubmitEvent) => {
    event.preventDefault();
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
            <label htmlFor="nickname">닉네임</label>
            <input
              id="nickname"
              type="text"
              className="text-input"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
            />
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
          <button type="submit" className="btnPrimary">회원가입</button>
        </form>
      </div>
    </div>
  );
}

export default Signup;
