import { useState } from "react";

import Modal from "./Modal";

export default function ResultDialog({ match, mode = "report", user, onSubmit, onClose }) {
  const [homeGoals, setHomeGoals] = useState(match.home_goals ?? "");
  const [awayGoals, setAwayGoals] = useState(match.away_goals ?? "");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const isCorrection = mode === "correct";
  const home = homeGoals === "" ? null : Number(homeGoals);
  const away = awayGoals === "" ? null : Number(awayGoals);
  const scoresValid =
    Number.isInteger(home) &&
    Number.isInteger(away) &&
    home >= 0 &&
    home <= 30 &&
    away >= 0 &&
    away <= 30;

  const userIsHome = user?.id === match.home.user_id;
  const userIsAway = user?.id === match.away.user_id;
  const reportsOwnMatch = !isCorrection && (userIsHome || userIsAway);
  const loserSubmitting =
    reportsOwnMatch &&
    scoresValid &&
    home !== away &&
    (userIsHome ? home < away : away < home);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    if (!scoresValid) {
      setError("Informe um placar válido, com números inteiros de 0 a 30.");
      return;
    }
    if (loserSubmitting) {
      setError("Quem registra o resultado é o vencedor da partida.");
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit(home, away, note);
      onClose();
    } catch {
      // Toast handled globally.
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title={isCorrection ? "Corrigir resultado" : "Inserir resultado"}
      onClose={submitting ? () => {} : onClose}
    >
      <form className="stack" onSubmit={handleSubmit}>
        <div className="score-grid">
          <label className="field">
            <span>{match.home.team_name}</span>
            <small>{match.home.player_name}</small>
            <input
              type="number"
              inputMode="numeric"
              min="0"
              max="30"
              step="1"
              value={homeGoals}
              onChange={(event) => setHomeGoals(event.target.value)}
              aria-label={`Gols de ${match.home.team_name}`}
              autoFocus
            />
          </label>

          <span className="score-separator" aria-hidden="true">
            ×
          </span>

          <label className="field">
            <span>{match.away.team_name}</span>
            <small>{match.away.player_name}</small>
            <input
              type="number"
              inputMode="numeric"
              min="0"
              max="30"
              step="1"
              value={awayGoals}
              onChange={(event) => setAwayGoals(event.target.value)}
              aria-label={`Gols de ${match.away.team_name}`}
            />
          </label>
        </div>

        {isCorrection && (
          <label className="field">
            <span>Observação (opcional)</span>
            <input
              type="text"
              maxLength="500"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Ex.: placar digitado errado"
            />
          </label>
        )}

        {loserSubmitting && (
          <p className="form-hint form-hint-warning">
            Só quem venceu pode registrar este placar. Peça ao seu adversário para lançar.
          </p>
        )}
        {error && <p className="form-hint form-hint-warning">{error}</p>}

        <button type="submit" className="button button-full" disabled={submitting}>
          {submitting ? "Salvando..." : isCorrection ? "Salvar correção" : "Confirmar resultado"}
        </button>
      </form>
    </Modal>
  );
}
