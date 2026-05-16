export function StatCard({
  title,
  value,
  sub,
  tone,
}: {
  title: string
  value: string | number
  sub?: string
  tone: 'purple' | 'green' | 'amber' | 'slate'
}) {
  const ring =
    tone === 'purple'
      ? 'ring-violet-100'
      : tone === 'green'
        ? 'ring-emerald-100'
        : tone === 'amber'
          ? 'ring-amber-100'
          : 'ring-slate-100'
  const text =
    tone === 'purple'
      ? 'text-[#5B3DF5]'
      : tone === 'green'
        ? 'text-emerald-700'
        : tone === 'amber'
          ? 'text-amber-800'
          : 'text-slate-800'

  return (
    <div className={`rounded-xl border border-gray-100 bg-white p-5 shadow-sm ring-1 ${ring}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</p>
      <p className={`mt-2 text-2xl font-bold tabular-nums ${text}`}>{value}</p>
      {sub ? <p className="mt-1 text-xs text-gray-500">{sub}</p> : null}
    </div>
  )
}
