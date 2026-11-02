import { useState } from "react";

import Modal from "./Modal";

export default function ConfirmDialog({
  title,
  message,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  danger = false,
  onConfirm,
  onClose,
}) {
  const [submitting, setSubmitting] = useState(false);

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      await onConfirm();
      onClose();
    } catch {
      // The API error is already shown as a toast; keep the dialog open.
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title={title}
      onClose={submitting ? () => {} : onClose}
      footer={
        <>
          <button type="button" className="button button-ghost" onClick={onClose} disabled={submitting}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`button${danger ? " button-danger" : ""}`}
            onClick={handleConfirm}
            disabled={submitting}
          >
            {submitting ? "Enviando..." : confirmLabel}
          </button>
        </>
      }
    >
      <p className="modal-text">{message}</p>
    </Modal>
  );
}
