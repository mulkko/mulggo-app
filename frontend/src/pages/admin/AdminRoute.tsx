import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

export const ADMIN_AUTH_KEY = "mulkko_admin_authed";

function AdminRoute({ children }: { children: ReactNode }) {
  const isAuthed = localStorage.getItem(ADMIN_AUTH_KEY) === "true";

  if (!isAuthed) {
    return <Navigate to="/admin/login" replace />;
  }

  return <>{children}</>;
}

export default AdminRoute;
