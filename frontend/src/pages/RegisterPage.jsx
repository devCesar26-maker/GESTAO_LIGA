import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { leagueApi } from "../api/endpoints";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

export default function RegisterPage() {
  const { user, register } = useAuth();
  const { notify } = useToast();
  const navigate = useNavigate();

  const [form, setForm] = useState({ email: "", password: "", name: "", team_name: "" });
  const [league, setLeague] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [closedMessage, setClosedMessage] = useState("");

  useEffect(() => {
    let active = true;
    leagueApi
      .getLeague()
      .then((response) => {
        if (!active) return;
        setLeague(response.data);
        if (!response.data.registration_open) setClosedMessage(response.data.status);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  if (user) return <Navigate to="/" replace />;
  const registrationClosed = Boolean(closedMessage) || league?.registration_open === false;

  const update = (field) => (event) =>
    setForm((current) => ({ ...current, [field]: event.target.value }));

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (registrationClosed) return;
    setSubmitting(true);
    try {
      const data = await register({
        email: form.email.trim(),
        password: form.password,
        name: form.name.trim(),
        team_name: form.team_name.trim(),
      });
      notify(data.message || "Cadastro realizado com sucesso!", "success");
      navigate("/", { replace: true });
    } catch {
      // Friendly message is shown by the API interceptor.
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
        <h1>Criar minha conta</h1>
        <p className="auth-subtitle">
          Escolha o nome do seu time e entre na disputa com os amigos.
        </p>

        {registrationClosed && (
          <div className="notice notice-warning" role="status">
            <strong>As inscrições estão encerradas.</strong>
            <span>
              Os confrontos já foram gerados. Fale com o administrador da liga para entrar.
            </span>
          </div>
        )}

        <form className="stack" onSubmit={handleSubmit}>
          <label className="field">
            <span>Seu nome</span>
            <input
              type="text"
              autoComplete="name"
              required
              maxLength="120"
              value={form.name}
              onChange={update("name")}
              placeholder="Como quer ser chamado"
            />
          </label>
          <label className="field">
            <span>Nome do time</span>
            <input
              type="text"
              required
              maxLength="60"
              value={form.team_name}
              onChange={update("team_name")}
              placeholder="Ex.: Trovão FC"
            />
          </label>
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              autoComplete="email"
              required
              value={form.email}
              onChange={update("email")}
              placeholder="voce@email.com"
            />
          </label>
          <label className="field">
            <span>Senha</span>
            <input
              type="password"
              autoComplete="new-password"
              required
              minLength="8"
              value={form.password}
              onChange={update("password")}
              placeholder="Mínimo de 8 caracteres"
            />
          </label>
          <button
            type="submit"
            className="button button-full"
            disabled={submitting || registrationClosed}
          >
            {submitting ? "Criando conta..." : "Entrar na liga"}
          </button>
        </form>

        <p className="auth-footer">
          Já tem conta? <Link to="/login">Entrar</Link>
        </p>
        <Link to="/" className="auth-back">
          ← Voltar para a liga
        </Link>
      </main>
    </div>
  );
}
