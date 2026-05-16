type LogLine = {
  time: string
  tone: 'ok' | 'warn' | 'error' | 'sync'
  text: string
  highlight?: string
}

const BASE_LOG: LogLine[] = [
  { time: '14:20:01', tone: 'ok', text: 'Initializing OCR backend...' },
  { time: '14:20:02', tone: 'ok', text: 'Scanning document geometry (layers: 4)...' },
  { time: '14:20:04', tone: 'ok', text: '12 line items extracted | high confidence' },
  { time: '14:20:05', tone: 'ok', text: 'Cross-referencing Vendor: Stripe (ID: 99x)' },
  {
    time: '14:20:07',
    tone: 'warn',
    text: 'Flagging GST mismatch in Row 2: Expected 18%',
    highlight: 'ERROR_RESOLVER: Compliance warning: IGST/SGST mismatch',
  },
  { time: '14:20:08', tone: 'ok', text: '3-Way matching with PO-X22 succeeded' },
  { time: '14:20:10', tone: 'sync', text: 'Pushing audit trail to verification ledger...' },
]

function toneColor(tone: LogLine['tone']) {
  if (tone === 'ok') return 'text-emerald-400'
  if (tone === 'warn') return 'text-amber-400'
  if (tone === 'error') return 'text-red-400'
  return 'text-sky-400'
}

function StatusIcon({ tone }: { tone: LogLine['tone'] }) {
  if (tone === 'sync') {
    return (
      <svg className="text-sky-400" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 12a9 9 0 1 1-9-9" />
        <path d="M21 3v6h-6" />
      </svg>
    )
  }
  if (tone === 'warn') {
    return <span className="text-amber-400">⚠</span>
  }
  if (tone === 'error') {
    return <span className="text-red-400">✕</span>
  }
  return <span className="text-emerald-400">✓</span>
}

export function ActivitySection({ loading, issueCount }: { loading: boolean; issueCount: number | null }) {
  const accuracy = issueCount === 0 ? '99.8%' : issueCount != null ? `${Math.max(94, 99.8 - issueCount).toFixed(1)}%` : '99.8%'

  const logs: LogLine[] = loading
    ? [
        ...BASE_LOG.slice(0, 3),
        { time: '14:20:06', tone: 'sync', text: 'Running LLM comparison pipeline...' },
      ]
    : issueCount != null && issueCount > 0
      ? BASE_LOG
      : issueCount === 0
        ? BASE_LOG.filter((l) => l.tone !== 'warn')
        : BASE_LOG

  return (
    <section className="py-16 sm:py-20 lg:py-24">
      <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full bg-[#5B3DF5]/10 px-3 py-1 text-[11px] font-semibold tracking-wide text-[#5B3DF5]">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="4" y="4" width="16" height="16" rx="2" />
              <path d="M9 9h6v6H9z" />
            </svg>
            PROCESSING CORE
          </span>
          <h2 className="mt-5 text-3xl font-bold tracking-tight text-[#1A1C2E] sm:text-4xl">
            Real-time AI Activity
            <span className="mt-1 block text-slate-400">Operational Log Feed</span>
          </h2>
          <p className="mt-4 max-w-md text-base leading-relaxed text-slate-600">
            Transparent step-by-step verification logic — every OCR pass, field match, and compliance flag streams
            into your audit ledger in real time.
          </p>
          <div className="mt-10 flex gap-12">
            <div>
              <p className="text-3xl font-bold tabular-nums text-[#1A1C2E]">{accuracy}</p>
              <p className="mt-1 text-xs font-semibold tracking-wide text-slate-400">ACCURACY</p>
            </div>
            <div>
              <p className="text-3xl font-bold tabular-nums text-[#1A1C2E]">450/min</p>
              <p className="mt-1 text-xs font-semibold tracking-wide text-slate-400">PROCESSING</p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl bg-[#0B0F1A] p-1 shadow-2xl ring-1 ring-white/5">
          <div className="rounded-xl bg-[#0B0F1A] p-5 font-mono text-[13px] leading-relaxed sm:p-6">
            <div className="mb-4 flex items-center justify-between border-b border-white/10 pb-3">
              <span className="text-slate-400">&gt;_ SYSTEM_ACTIVITY.LOG</span>
              <span className="flex gap-1.5" aria-hidden>
                <span className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500/80" />
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/80" />
              </span>
            </div>
            <ul className="space-y-2.5 text-slate-300">
              {logs.map((line) => (
                <li key={`${line.time}-${line.text}`}>
                  <div className="flex gap-2">
                    <span className="shrink-0 text-slate-500">{line.time}</span>
                    <StatusIcon tone={line.tone} />
                    <span className={toneColor(line.tone)}>{line.text}</span>
                  </div>
                  {line.highlight ? (
                    <p className="mt-1.5 ml-[4.5rem] rounded border border-red-500/30 bg-red-950/50 px-2 py-1 text-xs text-red-300">
                      {line.highlight}
                    </p>
                  ) : null}
                </li>
              ))}
              {loading ? (
                <li className="flex gap-2 text-sky-400">
                  <span className="text-slate-500">···</span>
                  <span className="animate-pulse">Processing documents…</span>
                </li>
              ) : null}
            </ul>
          </div>
        </div>
      </div>
    </section>
  )
}
