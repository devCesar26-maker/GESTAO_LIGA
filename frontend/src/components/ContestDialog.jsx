import { useState } from "react";

import Modal from "./Modal";

export default function ContestDialog({ match, onSubmit, onClose }) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit(reason);
      onClose();
    } catch {
      // Toast handled globally.
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal title="Contestar resultado" onClose={submitting ? () => {} : onClose}>
      <form className="stack" onSubmit={handleSubmit}>
        <p className="modal-text">
          Contestar {match.home.team_name} {match.home_goals} × {match.away_goals}{" "}
          {match.away.team_name}? O administrador será avisado.
        </p>
        <label className="field">
          <span>Conte o que aconteceu (opcional)</span>
          <textarea
            rows="3"
            maxLength="500"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Ex.: o placar correto era 2 a 1"
          />
        </label>
        <button type="submit" className="button button-full" disabled={submitting}>
          {submitting ? "Enviando..." : "Contestar resultado"}
        </button>
      </form>
    </Modal>
  );
}
