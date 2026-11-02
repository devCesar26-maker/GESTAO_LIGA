import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="page page-narrow">
      <div className="state-card empty-state">
        <span className="state-icon" aria-hidden="true">
          🧭
        </span>
        <h1>Página não encontrada</h1>
        <p>Não encontramos o que você procurava. Talvez o link esteja desatualizado.</p>
        <Link to="/" className="button">
          Voltar para a classificação
        </Link>
      </div>
    </div>
  );
}
