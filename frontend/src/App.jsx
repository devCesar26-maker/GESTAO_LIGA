import { Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import { AdminRoute, PrivateRoute } from "./components/ProtectedRoute";
import AccessDeniedPage from "./pages/AccessDeniedPage";
import AdminPage from "./pages/AdminPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import ProfilePage from "./pages/ProfilePage";
import RegisterPage from "./pages/RegisterPage";
import RoundsPage from "./pages/RoundsPage";
import StandingsPage from "./pages/StandingsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/cadastro" element={<RegisterPage />} />
      <Route element={<Layout />}>
        <Route index element={<StandingsPage />} />
        <Route path="rodadas" element={<RoundsPage />} />
        <Route
          path="perfil"
          element={
            <PrivateRoute>
              <ProfilePage />
            </PrivateRoute>
          }
        />
        <Route
          path="admin"
          element={
            <AdminRoute>
              <AdminPage />
            </AdminRoute>
          }
        />
        <Route path="sem-acesso" element={<AccessDeniedPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
