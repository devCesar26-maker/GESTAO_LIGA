import { statusLabel } from "../lib/format";

export default function StatusBadge({ status }) {
  return <span className={`badge badge-${status?.toLowerCase()}`}>{statusLabel(status)}</span>;
}
