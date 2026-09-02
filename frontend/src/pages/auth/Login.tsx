import { useState, type SubmitEvent } from "react";

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
    <div>
      <h1>로그인</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="email">이메일</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="password">비밀번호</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <button type="submit">로그인</button>
      </form>

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
