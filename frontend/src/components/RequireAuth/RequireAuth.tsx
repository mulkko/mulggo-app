import { useEffect, useState } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { authHeaders, clearSession, getAuthToken } from "../../auth/session";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

/**
 * [2026-09-15, 사용자 확인] "로그인 안 하면 서비스 자체를 못 쓴다"는 원칙을 라우트
 * 레벨에서 한 곳에 모아둔 가드. 레이아웃 라우트로 쓴다 -
 * `<Route element={<RequireAuth />}>...로그인 필요한 라우트들...</Route>` 형태로 감싸면
 * 하위는 <Outlet/>으로 그대로 렌더되고, 관리자 페이지의 AdminRoute.tsx와 같은 역할을
 * 사용자 화면 쪽에서 담당한다(관리자는 그쪽 가드를 그대로 씀, 이건 건드리지 않음).
 *
 * 토큰이 아예 없으면 바로 /login. 있으면 GET /api/auth/me로 서버에 검증해서 무효면
 * (백엔드 재시작 시 전체 세션 초기화 등) 로컬 토큰을 지우고 마찬가지로 /login.
 * 검증하는 짧은 순간엔 아무것도 안 그린다(깜빡였다가 리다이렉트되는 것 방지).
 */
function RequireAuth() {
  const [status, setStatus] = useState<"checking" | "authed" | "unauthed">(
    getAuthToken() ? "checking" : "unauthed",
  );

  useEffect(() => {
    if (!getAuthToken()) return;
    fetch(`${API_BASE_URL}/api/auth/me`, { headers: authHeaders() })
      .then((res) => {
        if (res.ok) {
          setStatus("authed");
        } else {
          clearSession();
          setStatus("unauthed");
        }
      })
      .catch(() => setStatus("authed")); // 네트워크 오류 - 판단 보류, 있던 세션은 유지
  }, []);

  if (status === "unauthed") return <Navigate to="/login" replace />;
  if (status === "checking") return null;
  return <Outlet />;
}

export default RequireAuth;
