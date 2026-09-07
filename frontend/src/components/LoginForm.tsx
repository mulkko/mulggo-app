import { useState, type SubmitEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import styles from "../styles/login.module.css";
import { ADMIN_AUTH_KEY } from "../pages/admin/AdminRoute";
import logo from "../assets/logo.svg";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

interface AuthResponse {
  success: boolean;
  data: { user_id: number; email: string; name: string } | null;
  error: { message: string; code: string } | null;
}

interface LoginFormProps {
  variant: "user" | "admin";
}

const VARIANT_CONFIG = {
  user: {
    title: "로그인",
    endpoint: "/api/auth/login",
  },
  admin: {
    title: "관리자 로그인",
    endpoint: "/api/auth/admin-login",
  },
} as const;

function LoginForm({ variant }: LoginFormProps) {
  const navigate = useNavigate();
  const { title, endpoint } = VARIANT_CONFIG[variant];

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (event: SubmitEvent) => {
    event.preventDefault();
    setErrorMessage("");
    setSuccess(false);

    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data: AuthResponse = await response.json();

      if (!data.success) {
        setErrorMessage(data.error?.message ?? "로그인에 실패했습니다.");
        return;
      }

      if (variant === "admin") {
        localStorage.setItem(ADMIN_AUTH_KEY, "true");
        navigate("/admin");
      } else {
        setSuccess(true);
      }
    } catch {
      setErrorMessage("서버에 연결할 수 없습니다.");
    }
  };

  // 관리자 로그인 화면은 기존 마크업/스타일을 그대로 유지한다.
  if (variant === "admin") {
    return (
      <div className={styles.loginPage}>
        <div className={styles.titBox}>
          <p className={styles.logo}><a href="#none">mulkko로고</a></p>
          <h1>{title}</h1>
        </div>
        <div className={styles.loginBox}>
          <form onSubmit={handleSubmit}>
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
            <button type="submit" className="btnPrimary">로그인</button>
          </form>
        </div>

        {success && <p>로그인 성공</p>}
        {errorMessage && <p>{errorMessage}</p>}
      </div>
    );
  }

  // 사용자 로그인 화면 — webTokens.css / WebStyleGuide 기준 디자인 (겉모습만, 기능 로직은 위와 동일).
  return (
    <div className={styles.page}>
      <div className={styles.hero}>
        <div className={styles.badge}>
          <img src={logo} alt="물꼬 로고" />
        </div>
        <p className={styles.wordmark}>MULKKO</p>
        <p className={styles.tagline}>창업의 물꼬를 트다.</p>
        {/* 시안에는 없지만 스크린리더/문서 타이틀용으로 title을 숨겨 유지 */}
        <h1 className={styles.srOnly}>{title}</h1>
        <svg
          className={styles.wave}
          viewBox="0 0 390 60"
          preserveAspectRatio="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path d="M0 34 C 78 6, 156 6, 234 26 C 300 43, 350 43, 390 30 L390 60 L0 60 Z" />
        </svg>
      </div>

      <div className={styles.formArea}>
        <form onSubmit={handleSubmit}>
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
            <label htmlFor="password">비밀번호</label>
            <input
              id="password"
              type="password"
              className={styles.input}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <a href="#" className={styles.forgot}>비밀번호를 잊으셨나요?</a>
          <button type="submit" className={styles.submitBtn}>로그인</button>
        </form>

        <p className={styles.signupPrompt}>
          아직 계정이 없으신가요? <Link to="/signup">회원가입</Link>
        </p>

        {success && <p className={styles.success}>로그인 성공</p>}
        {errorMessage && <p className={styles.error}>{errorMessage}</p>}
      </div>
    </div>
  );
}

export default LoginForm;
