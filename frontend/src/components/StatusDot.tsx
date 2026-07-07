interface Props {
  status: 'ok' | 'not_ready' | 'error'
  label?: string
}

export default function StatusDot({ status, label }: Props) {
  const colors = {
    ok: 'bg-pale-green-text',
    not_ready: 'bg-pale-yellow-text',
    error: 'bg-pale-red-text',
  }

  return (
    <span className="inline-flex items-center gap-2" title={label}>
      <span
        className={`inline-block h-2 w-2 rounded-full ${colors[status]} ${status === 'ok' ? '' : 'status-dot-pulse'}`}
      />
      {label && <span className="text-xs text-muted font-mono uppercase tracking-[0.05em]">{label}</span>}
    </span>
  )
}
