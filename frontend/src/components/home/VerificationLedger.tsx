import type { Discrepancy } from '../../types'

type RowStatus = 'match' | 'mismatch' | 'warning'

type LedgerRow = {
  label: string
  status: RowStatus
  detail?: string
}

const DEMO_ROWS: LedgerRow[] = [
  { label: 'Vendor: Stripe Inc.', status: 'match' },
  { label: 'Tax Rate (GST)', status: 'mismatch', detail: 'Expected 18%, found 12%' },
  { label: 'PO Reference', status: 'match' },
  { label: 'Bank Details', status: 'warning', detail: 'Secondary check required' },
]

function statusStyles(status: RowStatus) {
  if (status === 'match') {
    return {
      dot: 'bg-emerald-500',
      badge: 'bg-emerald-50 text-emerald-700',
      label: 'MATCH',
    }
  }
  if (status === 'mismatch') {
    return {
      dot: 'bg-red-500',
      badge: 'bg-orange-50 text-orange-700',
      label: 'MISMATCH',
    }
  }
  return {
    dot: 'bg-amber-500',
    badge: 'bg-amber-50 text-amber-700',
    label: 'WARNING',
  }
}

function discrepanciesToRows(rows: Discrepancy[]): LedgerRow[] {
  return rows.slice(0, 4).map((d) => ({
    label: `${d.field}: ${d.item}`,
    status: 'mismatch' as const,
    detail: d.issue,
  }))
}

export function VerificationLedger({
  flaggedCount,
  confidence,
  rows,
  onRunAudit,
}: {
  flaggedCount: number
  confidence: string
  rows?: LedgerRow[]
  onRunAudit: () => void
}) {
  const displayRows = rows && rows.length > 0 ? rows : DEMO_ROWS

  return (
    <div
      className="overflow-hidden rounded-2xl border border-gray-200/80 bg-white shadow-xl shadow-slate-200/50 ring-1 ring-gray-100"
      aria-label="Verification ledger preview"
    >
      <div className="flex min-h-[420px]">
        <aside className="hidden w-[120px] shrink-0 border-r border-gray-100 bg-[#FAFBFC] p-4 sm:block">
          <p className="text-[10px] font-semibold tracking-widest text-slate-400">WORKSPACE</p>
          <ul className="mt-4 space-y-1 text-xs font-medium">
            {['Ledger', 'Processing', 'Vendors', 'Settings'].map((item) => (
              <li
                key={item}
                className={
                  item === 'Ledger'
                    ? 'rounded-lg bg-[#5B3DF5]/10 px-2.5 py-2 text-[#5B3DF5]'
                    : 'rounded-lg px-2.5 py-2 text-slate-500'
                }
              >
                {item}
              </li>
            ))}
          </ul>
        </aside>

        <div className="flex flex-1 flex-col p-5 sm:p-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold tracking-tight text-[#1A1C2E]">Verification Ledger</h2>
              <p className="mt-0.5 text-[11px] text-slate-400">Instance ID · VF-8A2C-PROD</p>
            </div>
            <button
              type="button"
              onClick={onRunAudit}
              className="shrink-0 rounded-lg bg-[#5B3DF5] px-3 py-1.5 text-[11px] font-semibold text-white shadow-sm shadow-[#5B3DF5]/20 transition hover:bg-[#4a32c8]"
            >
              Run Audit
            </button>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-3">
            <div className="rounded-xl border border-gray-100 bg-[#FAFBFC] px-4 py-3">
              <p className="text-[10px] font-semibold tracking-wide text-slate-400">INPUT CONFIDENCE</p>
              <p className="mt-1 text-xl font-bold tabular-nums text-[#1A1C2E]">{confidence}</p>
            </div>
            <div className="rounded-xl border border-gray-100 bg-[#FAFBFC] px-4 py-3">
              <p className="text-[10px] font-semibold tracking-wide text-slate-400">FLAGGED ITEMS</p>
              <p className="mt-1 text-sm font-bold text-amber-800">
                {flaggedCount} {flaggedCount === 1 ? 'Discrepancy' : 'Discrepancies'}
              </p>
            </div>
          </div>

          <ul className="mt-4 flex-1 space-y-2">
            {displayRows.map((row) => {
              const s = statusStyles(row.status)
              return (
                <li
                  key={row.label}
                  className="rounded-xl border border-gray-100 px-4 py-3 transition hover:border-gray-200"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2">
                      <span className={`h-2 w-2 shrink-0 rounded-full ${s.dot}`} />
                      <span className="truncate text-sm font-medium text-[#1A1C2E]">{row.label}</span>
                    </div>
                    <span className={`shrink-0 rounded-md px-2 py-0.5 text-[10px] font-bold ${s.badge}`}>
                      {s.label}
                    </span>
                  </div>
                  {row.detail ? <p className="mt-1 pl-4 text-xs text-slate-500">{row.detail}</p> : null}
                </li>
              )
            })}
          </ul>

          <div className="mt-4 flex flex-wrap gap-4 border-t border-gray-100 pt-4 text-[10px] font-semibold tracking-wide text-slate-400">
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              ACTIVE OCR CORE
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-[#5B3DF5]" />
              AUDIT TRAILS LIVE
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

export { discrepanciesToRows, DEMO_ROWS }
export type { LedgerRow }
