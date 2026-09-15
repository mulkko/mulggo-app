// 로그인 세션(토큰) 저장/조회. backend/auth/session.py가 발급하는 토큰을
// localStorage에 두고, 요청마다 Authorization 헤더로 실어 보낸다.

const TOKEN_KEY = "mulkko_auth_token";
const USER_ID_KEY = "mulkko_user_id";
const EMAIL_KEY = "mulkko_user_email";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getUserId(): number | null {
  const raw = localStorage.getItem(USER_ID_KEY);
  return raw ? Number(raw) : null;
}

export function getUserEmail(): string | null {
  return localStorage.getItem(EMAIL_KEY);
}

export function setSession(token: string, userId: number, email?: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_ID_KEY, String(userId));
  if (email) localStorage.setItem(EMAIL_KEY, email);
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_ID_KEY);
  localStorage.removeItem(EMAIL_KEY);
}

export function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * [2026-09-12] 로그아웃 - clearSession()은 브라우저 저장소만 지우고 서버 auth_sessions의
 * 토큰은 그대로 살려뒀었다(사용자 확인 후 보완) - 로그아웃 버튼은 이제 이 함수를 써서
 * 서버에도 같이 무효화 요청을 보낸다. 토큰을 지우기 전에 먼저 헤더를 만들어야 하므로
 * clearSession()보다 항상 나중에 지운다. API 호출이 실패해도(네트워크 문제 등) 클라이언트
 * 쪽은 무조건 로그아웃 처리한다 - 사용자 입장에서 로그아웃 버튼이 안 먹으면 안 됨.
 */
export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/api/auth/logout`, { method: "POST", headers: authHeaders() });
  } catch {
    // 서버에 못 알렸어도 클라이언트 쪽 로그아웃은 아래에서 그대로 진행
  } finally {
    clearSession();
  }
}
