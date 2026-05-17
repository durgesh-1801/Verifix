import type { Discrepancy, VerifyErrorBody, VerifySuccessResponse } from './types'

/**
 * Base URL for Flask. In dev, leave unset to use Vite proxy (same-origin `/api`, `/export-pdf`).
 * For production, set `VITE_API_BASE_URL` to your deployed API origin (no trailing slash).
 */
export function apiOrigin(): string {
  const raw = import.meta.env.VITE_API_BASE_URL
  if (typeof raw === 'string' && raw.trim().length > 0) {
    return raw.replace(/\/$/, '')
  }
  return 'http://127.0.0.1:5000'
}

function url(path: string): string {
  const origin = apiOrigin()
  return origin ? `${origin}${path}` : path
}

export async function verifyInvoice(
  invoiceFile: File,
  poFile: File,
): Promise<{ ok: true; data: VerifySuccessResponse } | { ok: false; status: number; body: VerifyErrorBody }> {
  const fd = new FormData()
  fd.append('invoice', invoiceFile)
  fd.append('purchase_order', poFile)

  const res = await fetch(url('/verify'), {
    method: 'POST',
    body: fd,
  })

  const body = (await res.json()) as VerifySuccessResponse | VerifyErrorBody

  if (!res.ok) {
    return { ok: false, status: res.status, body: body as VerifyErrorBody }
  }

  return { ok: true, data: body as VerifySuccessResponse }
}

export async function downloadPdfReport(params: {
  status: string
  totalIssues: number
  totalRupeeDifference: number | string
  discrepancies: Discrepancy[]
}): Promise<void> {
  const fd = new FormData()
  fd.append('status', params.status)
  fd.append('total_issues', String(params.totalIssues))
  fd.append('total_difference', String(params.totalRupeeDifference))
  fd.append('discrepancies_json', JSON.stringify(params.discrepancies))

  const res = await fetch(url('/export-pdf'), { method: 'POST', body: fd })
  if (!res.ok) {
    throw new Error(`PDF export failed (${res.status})`)
  }

  const blob = await res.blob()
  const href = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = href
  a.download = 'invoice_ai_report.pdf'
  a.rel = 'noopener'
  a.click()
  URL.revokeObjectURL(href)
}
