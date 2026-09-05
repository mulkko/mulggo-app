import type { ReactNode } from "react";
// import { Navigate } from "react-router-dom";

export const ADMIN_AUTH_KEY = "mulkko_admin_authed";

function AdminRoute({ children }: { children: ReactNode }) {
  const isAuthed = localStorage.getItem(ADMIN_AUTH_KEY) === "true";

  // TODO: 로그인 기능(DB 연동) 붙기 전까지 임시로 가드 꺼둠 — 작업 끝나면 주석 해제
  // if (!isAuthed) {
  //   return <Navigate to="/admin/login" replace />;
  // }
  void isAuthed;

  return <>{children}</>;
}

export default AdminRoute;
