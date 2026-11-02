import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

export default function ProfilePage() {
  const { user, updateProfile, logout } = useAuth();
  const { notify } = useToast();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: user?.name || "", team_name: user?.team_name || "" });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) setForm({ name: user.name || "", team_name: user.team_name || "" });
  }, [user]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      const data = await updateProfile({
        name: form.name.trim(),
        team_name: form.team_name.trim(),
      });
      notify(data.message || "Perfil atualizado com sucesso.", "success");
    } catch {
      // Toast handled globally.
    } finally {
      setSubmitting(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate("/", { replace: true });
  };

  return (
    <div className="page page-narrow">
      <section className="page-head">
        <div>
          <p className="eyebrow">Sua conta</p>
          <h1 className="page-title">Perfil</h1>
          <p className="page-subtitle">Atualize seu nome e o nome do seu time.</p>
        </div>
      </section>

      <section className="panel profile-summary">
        <div className="profile-avatar" aria-hidden="true">
          {(user?.team_name || user?.name || "?").slice(0, 1).toUpperCase()}
        </div>
        <div>
          <strong>{user?.team_name}</strong>
          <span>{user?.name}</span>
          <span className="muted">{user?.email}</span>
          {user?.is_staff && <span className="badge badge-registration">Administrador</span>}
        </div>
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>Dados do jogador</h2>
        </header>
        <form className="stack" onSubmit={handleSubmit}>
          <label className="field">
            <span>Nome do time</span>
            <input
              type="text"
              required
              maxLength="60"
              value={form.team_name}
              onChange={(event) =>
                setForm((current) => ({ ...current, team_name: event.target.value }))
              }
            />
          </label>
          <label className="field">
            <span>Seu nome</span>
            <input
              type="text"
              required
              maxLength="120"
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
          </label>
          <label className="field">
            <span>Email</span>
            <input type="email" value={user?.email || ""} disabled />
            <small>O email de login não pode ser alterado.</small>
          </label>
          <button type="submit" className="button" disabled={submitting}>
            {submitting ? "Salvando..." : "Salvar alterações"}
          </button>
        </form>
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>Sessão</h2>
        </header>
        <button type="button" className="button button-ghost" onClick={handleLogout}>
          Sair da conta
        </button>
      </section>
    </div>
  );
}
