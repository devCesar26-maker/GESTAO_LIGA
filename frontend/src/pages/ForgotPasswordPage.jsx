import { useState } from "react";
import { Link } from "react-router-dom";

import { authApi } from "../api/endpoints";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const { data } = await authApi.requestPasswordReset(email.trim());
      setMessage(
        data.message ||
          "Se este email estiver cadastrado, enviaremos as instruções para redefinir a senha.",
      );
    } catch (err) {
      setError(err.friendlyMessage || "Não foi possível enviar as instruções. Tente novamente.");
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
        <h1>Esqueci minha senha</h1>
        <p className="auth-subtitle">
          Informe o email da sua conta. Enviaremos um link para você escolher uma nova senha.
        </p>

        {message ? (
          <div className="notice notice-success" role="status">
            <strong>Verifique seu email.</strong>
            <span>{message}</span>
          </div>
        ) : (
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
            {error && (
              <p className="form-hint form-hint-warning" role="alert">
                {error}
              </p>
            )}

            <button type="submit" className="button button-full" disabled={submitting}>
              {submitting ? "Enviando..." : "Enviar instruções"}
            </button>
          </form>
        )}

        <p className="auth-footer">
          Lembrou a senha? <Link to="/login">Voltar para o login</Link>
        </p>
        <Link to="/" className="auth-back">
          ← Voltar para a liga
        </Link>
      </main>
    </div>
  );
}
