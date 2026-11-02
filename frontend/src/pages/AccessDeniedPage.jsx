import { Link, useNavigate } from "react-router-dom";

export default function AccessDeniedPage() {
  const navigate = useNavigate();
  return (
    <div className="page page-narrow">
      <div className="state-card empty-state">
        <span className="state-icon" aria-hidden="true">
          🚧
        </span>
        <h1>Você não tem acesso a esta área</h1>
        <p>
          Esta página é exclusiva do administrador da liga. Se você acredita que deveria ter
          acesso, fale com o administrador.
        </p>
        <div className="inline-actions">
          <button type="button" className="button button-ghost" onClick={() => navigate(-1)}>
            Voltar
          </button>
          <Link to="/" className="button">
            Ir para a classificação
          </Link>
        </div>
      </div>
    </div>
  );
}
