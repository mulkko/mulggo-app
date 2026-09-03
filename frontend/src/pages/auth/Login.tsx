import { useState, type SubmitEvent } from "react";
import styles from '../../styles/login.module.css'; // 객체 형태로 불러옴

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

interface AuthResponse {
  success: boolean;
  errors: string[];
}

function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (event: SubmitEvent) => {
    event.preventDefault();
    setErrors([]);
    setSuccess(false);

    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data: AuthResponse = await response.json();
      setSuccess(data.success);
      setErrors(data.errors);
    } catch {
      setErrors(["서버에 연결할 수 없습니다."]);
    }
  };

  return (
    <div className={styles.loginPage}>
      <div className={styles.titBox}>
        <p className={styles.logo}><a href="#none">mulkko로고</a></p>
        <h1>로그인</h1>
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
      {errors.length > 0 && (
        <ul>
          {errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default Login;
