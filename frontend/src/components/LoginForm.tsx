import { useState, type SubmitEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import styles from "../styles/login.module.css";
import { ADMIN_AUTH_KEY } from "../pages/admin/AdminRoute";
import { getAuthToken, setSession } from "../auth/session";
import logo from "../assets/logo.svg";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

interface AuthResponse {
  success: boolean;
  data: { user_id: number; email: string; name: string; token?: string } | null;
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
  const isLoggedIn = Boolean(getAuthToken());

  const goToNextScreen = () => {
    if (variant === "admin") {
      localStorage.setItem(ADMIN_AUTH_KEY, "true");
      navigate("/admin");
    } else {
      navigate("/home");
    }
  };

  const handleSubmit = async (event: SubmitEvent) => {
    event.preventDefault();
    setErrorMessage("");

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

      if (data.data?.token) {
        setSession(data.data.token, data.data.user_id, data.data.email);
      }

      goToNextScreen();
    } catch {
      setErrorMessage("서버에 연결할 수 없습니다.");
    }
  };

  // webTokens.css / WebStyleGuide 기준 디자인. 관리자/사용자 공용(variant로 문구·동작만 분기).
  return (
    <div className={styles.page}>
      <div className={styles.hero}>
        <div className={styles.badge}>
          <img src={logo} alt="물꼬 로고" />
        </div>
        <p className={styles.wordmark}>{variant === "admin" ? "MULKKO 관리자" : "MULKKO"}</p>
        <p className={styles.tagline}>{variant === "admin" ? "관리자 전용 페이지입니다." : "창업의 물꼬를 트다."}</p>
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
        <form onSubmit={handleSubmit} noValidate>
          <div className={styles.field}>
            <label htmlFor="email">아이디(이메일){variant === "admin" && " - 관리자 로그인"}</label>
            <input
              id="email"
              type="email"
              className={`${styles.input} ${errorMessage ? styles.inputError : ""}`}
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
              className={`${styles.input} ${errorMessage ? styles.inputError : ""}`}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {/* [2026-09-12, 사용자 확인] 아이디/비밀번호 찾기는 시간 부족으로 기능 없이
              자리표시자만 - 눌러도 아무 동작 없음. */}
          <div className={styles.forgotRow}>
            {variant === "user" && !isLoggedIn && (
              <>
                <Link to="/signup" className={styles.forgot}>회원가입</Link>
                <span className={styles.forgotDivider}>|</span>
              </>
            )}
            <a href="#" className={styles.forgot}>아이디 찾기</a>
            <span className={styles.forgotDivider}>|</span>
            <a href="#" className={styles.forgot}>비밀번호찾기</a>
          </div>
          <button type="submit" className={styles.submitBtn}>로그인</button>
        </form>

        {errorMessage && <p className={styles.error}>{errorMessage}</p>}
      </div>
    </div>
  );
}

export default LoginForm;
