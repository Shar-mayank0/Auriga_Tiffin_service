export default function StatusBadge({ status }) {
  const normalized = String(status || 'inactive').toLowerCase()
  return <span className={`status status-${normalized}`}>{normalized}</span>
}