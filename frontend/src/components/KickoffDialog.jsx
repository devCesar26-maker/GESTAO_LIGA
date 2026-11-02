import { useState } from "react";

import { toDateTimeLocal } from "../lib/format";
import Modal from "./Modal";

export default function KickoffDialog({ match, onSubmit, onClose }) {
  const [value, setValue] = useState(toDateTimeLocal(match.kickoff_at));
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      const payload = value ? new Date(value).toISOString() : null;
      await onSubmit(payload);
      onClose();
    } catch {
      // Toast handled globally.
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal title="Alterar data e hora" onClose={submitting ? () => {} : onClose}>
      <form className="stack" onSubmit={handleSubmit}>
        <p className="modal-text">
          {match.home.team_name} × {match.away.team_name}
        </p>
        <label className="field">
          <span>Nova data e hora</span>
          <input
            type="datetime-local"
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
        </label>
        <p className="form-hint">Deixe em branco para marcar como “A definir”.</p>
        <button type="submit" className="button button-full" disabled={submitting}>
          {submitting ? "Salvando..." : "Salvar data"}
        </button>
      </form>
    </Modal>
  );
}
