export function LoadingState({ label = "Carregando..." }) {
  return (
    <div className="state-card" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

export function EmptyState({ icon = "🗓️", title, description, action }) {
  return (
    <div className="state-card empty-state">
      <span className="state-icon" aria-hidden="true">
        {icon}
      </span>
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ onRetry }) {
  return (
    <div className="state-card error-state" role="alert">
      <span className="state-icon" aria-hidden="true">
        ⚠️
      </span>
      <h2>Não foi possível carregar os dados</h2>
      <p>Verifique sua conexão e tente novamente.</p>
      {onRetry && (
        <button type="button" className="button" onClick={onRetry}>
          Tentar novamente
        </button>
      )}
    </div>
  );
}
