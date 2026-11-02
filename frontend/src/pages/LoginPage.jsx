import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // Shown inline as well as in the toast, so a failure is never silent.
  const [error, setError] = useState("");

  const rawNext = new URLSearchParams(location.search).get("next");
  const next = rawNext && rawNext.startsWith("/") && !rawNext.startsWith("//") ? rawNext : "/";

  if (user) return <Navigate to={next} replace />;

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate(next, { replace: true });
    } catch (err) {
      setError(err.friendlyMessage || "Não foi possível entrar. Tente novamente.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-shell">
      <main className="auth-card">
        <Link to="/" className="auth-brand">
          <span aria-hidden="true">⚽</span> LIGA <strong>eFootball</strong>
        </Link>
        <h1>Entrar</h1>
        <p className="auth-subtitle">Acompanhe a classificação e registre seus resultados.</p>

        <form className="stack" onSubmit={handleSubmit}>
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="voce@email.com"
            />
          </label>
          <label className="field">
            <span>Senha</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Sua senha"
            />
          </label>
          {error && (
            <p className="form-hint form-hint-warning" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="button button-full" disabled={submitting}>
            {submitting ? "Entrando..." : "Entrar"}
          </button>
        </form>

        <p className="auth-footer">
          Ainda não tem conta? <Link to="/cadastro">Cadastre-se</Link>
          <br />
          <Link to="/esqueci-senha">Esqueci minha senha</Link>
        </p>
        <Link to="/" className="auth-back">
          ← Voltar para a liga
        </Link>
      </main>
    </div>
  );
}
