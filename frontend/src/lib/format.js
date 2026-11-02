const dateTimeFormatter = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatKickoff(value) {
  if (!value) return "A definir";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "A definir";
  return dateTimeFormatter.format(date);
}

/** ISO string -> value accepted by <input type="datetime-local">. */
export function toDateTimeLocal(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

export function statusLabel(status) {
  const labels = {
    SCHEDULED: "Agendada",
    FINISHED: "Finalizada",
    CONTESTED: "Contestada",
    REGISTRATION: "Inscrições abertas",
    IN_PROGRESS: "Em andamento",
  };
  return labels[status] || status;
}

export function playableName(value) {
  return value || "Jogador";
}
