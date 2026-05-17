import { FileDropZone } from './FileDropZone'
import { DiscrepancyTable } from './DiscrepancyTable'
import { StatCard } from '../ui/StatCard'
import { Spinner } from '../ui/Spinner'
import type { VerifySuccessResponse } from '../../types'

type Banner = { type: 'success' | 'error'; message: string }

type Totals = {
  totalIssues: number
  totalRupeeDifference: number | string
  status: string
}

export function WorkspaceSection({
  invoiceFile,
  poFile,
  onInvoiceFile,
  onPoFile,
  loading,
  banner,
  result,
  totals,
  pdfLoading,
  onVerify,
  onClear,
  onDownloadPdf,
}: {
  invoiceFile: File | null
  poFile: File | null
  onInvoiceFile: (f: File | null) => void
  onPoFile: (f: File | null) => void
  loading: boolean
  banner: Banner | null
  result: VerifySuccessResponse | null
  totals: Totals | null
  pdfLoading: boolean
  onVerify: () => void
  onClear: () => void
  onDownloadPdf: () => void
}) {
  return (
    <section id="workspace" className="scroll-mt-24 py-16 sm:py-20">
      <div className="mb-8 max-w-2xl">
        <p className="text-[11px] font-semibold tracking-[0.14em] text-[#5B3DF5]">VERIFICATION WORKSPACE</p>
        <h2 className="mt-2 text-3xl font-bold tracking-tight text-[#1A1C2E]">Upload & verify documents</h2>
        <p className="mt-2 text-sm text-slate-600">
          Pair invoice and purchase-order files. Results stream from your Flask pipeline — no rules duplicated in the
          browser.
        </p>
      </div>

      {banner ? (
        <div
          role="status"
          className={`mb-6 rounded-xl border px-4 py-3 text-sm font-medium ${
            banner.type === 'success'
              ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
              : 'border-red-200 bg-red-50 text-red-900'
          }`}
        >
          {banner.message}
        </div>
      ) : null}

      <div className="relative rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8">
        {loading ? (
          <div
            className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 rounded-2xl bg-white/90 backdrop-blur-sm"
            aria-busy
            aria-label="Verifying documents"
          >
            <Spinner className="h-10 w-10 border-violet-200 border-t-[#5B3DF5]" />
            <p className="text-sm font-medium text-slate-700">Running OCR and comparison…</p>
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2">
          <FileDropZone
            label="Invoice"
            hint="PDF or TXT (max size enforced server-side)"
            file={invoiceFile}
            onFile={onInvoiceFile}
            disabled={loading}
            accent="violet"
          />
          <FileDropZone
            label="Purchase order"
            hint="PDF or TXT — must pair with invoice"
            file={poFile}
            onFile={onPoFile}
            disabled={loading}
            accent="slate"
          />
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={onVerify}
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#5B3DF5] px-5 py-2.5 text-sm font-semibold text-white shadow-sm shadow-[#5B3DF5]/20 transition hover:bg-[#4a32c8] disabled:cursor-not-allowed disabled:opacity-70"
          >
            {loading ? (
              <>
                <Spinner />
                Verifying…
              </>
            ) : (
              'Run verification'
            )}
          </button>
          <button
            type="button"
            onClick={onClear}
            disabled={loading}
            className="rounded-xl border border-gray-200 bg-white px-5 py-2.5 text-sm font-semibold text-[#1A1C2E] transition hover:border-gray-300 disabled:opacity-60"
          >
            Clear files
          </button>
        </div>
      </div>

      {result && totals ? (
        <div id="reports" className="mt-12 scroll-mt-24 space-y-6" aria-label="Verification results">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-[11px] font-semibold tracking-[0.14em] text-slate-400">REPORTS</p>
              <h2 className="text-2xl font-bold text-[#1A1C2E]">Verification results</h2>
            </div>
            <button
              type="button"
              onClick={onDownloadPdf}
              disabled={pdfLoading}
              className="inline-flex items-center justify-center gap-2 self-start rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-semibold text-[#1A1C2E] transition hover:border-[#5B3DF5]/40 hover:text-[#5B3DF5] disabled:opacity-60"
            >
              {pdfLoading ? (
                <>
                  <Spinner className="h-4 w-4 border-gray-200 border-t-[#5B3DF5]" />
                  Preparing PDF…
                </>
              ) : (
                'Download PDF report'
              )}
            </button>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard
              title="Verification status"
              value={totals.status}
              tone={totals.totalIssues ? 'amber' : 'green'}
            />
            <StatCard title="Total issues" value={totals.totalIssues} sub="Rows in discrepancy list" tone="purple" />
            <StatCard
              title="Total rupee difference"
              value={`₹${totals.totalRupeeDifference}`}
              sub="Summed from numeric differences"
              tone="slate"
            />
          </div>



          <div>
            <h3 className="mb-3 text-lg font-bold text-[#1A1C2E]">Discrepancy table</h3>
            <DiscrepancyTable rows={result.discrepancies} />
          </div>
        </div>
      ) : null}
    </section>
  )
}
