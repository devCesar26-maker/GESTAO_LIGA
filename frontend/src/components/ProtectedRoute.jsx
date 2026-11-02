import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import AccessDeniedPage from "../pages/AccessDeniedPage";
import { LoadingState } from "./PageState";

export function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <LoadingState label="Carregando seu perfil..." />;
  if (!user) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  return children;
}

export function AdminRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) return <LoadingState label="Verificando seu acesso..." />;
  if (!user) {
    return <Navigate to={`/login?next=${encodeURIComponent("/admin")}`} replace />;
  }
  if (!user.is_staff) return <AccessDeniedPage />;
  return children;
}
