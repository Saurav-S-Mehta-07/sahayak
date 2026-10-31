import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export function RequireAuth({ admin = false }) {
  const { user, loading, signingOut } = useAuth();
  const location = useLocation();

  if (loading) return <div className="page-loading" role="status">Checking your session…</div>;
  if (!user) {
    return <Navigate to={signingOut ? "/" : "/login"} replace state={{ from: location }} />;
  }
  if (admin && user.role !== "admin") return <Navigate to="/chat" replace />;
  return <Outlet />;
}
