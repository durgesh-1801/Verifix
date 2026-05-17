import type { Discrepancy } from '../../types'

function renderCellValue(value: unknown): string | number {
  if (value == null) return 'N/A'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function DiscrepancyTable({ rows }: { rows: Discrepancy[] }) {
  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-emerald-100 bg-emerald-50/60 px-4 py-8 text-center text-sm font-medium text-emerald-800">
        No discrepancies — invoice and PO align on checked fields.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
      <table className="min-w-[720px] w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-[#FAFBFC] text-xs font-semibold uppercase tracking-wide text-slate-600">
            <th className="px-4 py-3">Item</th>
            <th className="px-4 py-3">Field</th>
            <th className="px-4 py-3">Invoice</th>
            <th className="px-4 py-3">PO</th>
            <th className="px-4 py-3">Difference (₹)</th>
            <th className="px-4 py-3">Issue</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((d, i) => (
            <tr key={`${d.item}-${d.field}-${i}`} className="border-b border-gray-100 last:border-0">
              <td className="max-w-[180px] px-4 py-3 font-medium text-[#1A1C2E]">{d.item}</td>
              <td className="px-4 py-3 text-slate-700">{d.field}</td>
              <td className="px-4 py-3 text-slate-700 font-mono text-[11px] break-all">{renderCellValue(d.invoice)}</td>
              <td className="px-4 py-3 text-slate-700 font-mono text-[11px] break-all">{renderCellValue(d.po)}</td>
              <td className="px-4 py-3 font-medium text-[#5B3DF5]">{d.difference ?? 'N/A'}</td>
              <td className="max-w-[220px] px-4 py-3 text-slate-600">{d.issue}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
