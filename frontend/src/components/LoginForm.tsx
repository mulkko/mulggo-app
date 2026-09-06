import { useState, type SubmitEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import styles from "../styles/login.module.css";
import { ADMIN_AUTH_KEY } from "../pages/admin/AdminRoute";

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
        {variant === "user" && (
          <p>
            아직 계정이 없으신가요? <Link to="/signup">회원가입</Link>
          </p>
        )}
      </div>

      {success && <p>로그인 성공</p>}
      {errorMessage && <p>{errorMessage}</p>}
    </div>
  );
}

export default LoginForm;
