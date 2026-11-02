import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { authApi } from "../api/endpoints";
import { useAuth } from "../context/AuthContext";

export default function ResetPasswordPage() {
  const { user, logout } = useAuth();
  const [searchParams] = useSearchParams();
  const uid = searchParams.get("uid") || "";
  const token = searchParams.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const linkIsValid = Boolean(uid && token);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");

    if (password.length < 8) {
      setError("A senha precisa ter pelo menos 8 caracteres.");
      return;
    }
    if (password !== confirmation) {
      setError("As duas senhas precisam ser iguais.");
      return;
    }

    setSubmitting(true);
    try {
      const { data } = await authApi.confirmPasswordReset({ uid, token, password });
      // The API cleared the cookies; reset the in-memory session too, so a
      // logged-in user is not sent back to the home page by the login route.
      if (user) await logout();
      setMessage(
        data.message || "Senha redefinida com sucesso. Entre com a nova senha.",
      );
    } catch (err) {
      setError(
        err.friendlyMessage ||
          "Não foi possível redefinir a senha. Solicite um novo link e tente novamente.",
      );
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
        <h1>Criar nova senha</h1>
        <p className="auth-subtitle">
          Escolha uma senha forte com pelo menos 8 caracteres.
        </p>

        {!linkIsValid && (
          <div className="notice notice-warning" role="alert">
            <strong>Link inválido.</strong>
            <span>
              O endereço não contém as informações necessárias. Solicite um novo link de
              recuperação.
            </span>
          </div>
        )}

        {message && (
          <div className="notice notice-success" role="status">
            <strong>Senha redefinida.</strong>
            <span>{message}</span>
          </div>
        )}

        {linkIsValid && !message && (
          <form className="stack" onSubmit={handleSubmit}>
            <label className="field">
              <span>Nova senha</span>
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength="8"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Mínimo de 8 caracteres"
              />
            </label>
            <label className="field">
              <span>Confirme a nova senha</span>
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength="8"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                placeholder="Digite a senha novamente"
              />
            </label>
            {error && (
              <p className="form-hint form-hint-warning" role="alert">
                {error}
              </p>
            )}

            <button type="submit" className="button button-full" disabled={submitting}>
              {submitting ? "Salvando..." : "Redefinir senha"}
            </button>
          </form>
        )}

        {message ? (
          <Link className="button button-full" to="/login">
            Ir para o login
          </Link>
        ) : (
          <p className="auth-footer">
            Precisa de outro link? <Link to="/esqueci-senha">Solicitar novamente</Link>
          </p>
        )}
        <Link to="/" className="auth-back">
          ← Voltar para a liga
        </Link>
      </main>
    </div>
  );
}
