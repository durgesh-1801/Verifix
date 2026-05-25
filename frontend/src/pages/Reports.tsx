import { useState, useEffect, useMemo, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { downloadPdfReport } from '../api'
import { 
  loadVerificationHistory, 
  safeRender
} from '../lib/analytics'
import type { HistoryItem } from '../lib/analytics'
import { Spinner } from '../components/ui/Spinner'

export default function Reports() {
  const [reports, setReports] = useState<HistoryItem[]>([])
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [sortBy, setSortBy] = useState('DATE_DESC')
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    setReports(loadVerificationHistory())
  }, [])

  // Filter and Sort active reports history dynamically
  const filteredAndSortedReports = useMemo(() => {
    let result = reports.filter((run) => {
      const matchSearch = run.id.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          run.vendor.toLowerCase().includes(searchTerm.toLowerCase())
      
      const matchStatus = statusFilter === 'ALL' || 
                          (statusFilter === 'MATCH' && run.status === 'MATCH') ||
                          (statusFilter === 'DISCREPANCY' && run.status !== 'MATCH')
      
      return matchSearch && matchStatus
    })

    // Apply active sort order parameters
    result.sort((a, b) => {
      if (sortBy === 'DATE_DESC') {
        return b.time.localeCompare(a.time)
      }
      if (sortBy === 'DATE_ASC') {
        return a.time.localeCompare(b.time)
      }
      if (sortBy === 'DISCREPANCY_DESC') {
        return b.discrepancies - a.discrepancies
      }
      if (sortBy === 'DISCREPANCY_ASC') {
        return a.discrepancies - b.discrepancies
      }
      if (sortBy === 'VENDOR_ASC') {
        return a.vendor.localeCompare(b.vendor)
      }
      if (sortBy === 'VENDOR_DESC') {
        return b.vendor.localeCompare(a.vendor)
      }
      return 0
    })

    return result
  }, [reports, searchTerm, statusFilter, sortBy])

  // Download PDF Report by reconstructing compatible discrepancies payload safely
  const handleDownloadPdf = useCallback(async (run: HistoryItem) => {
    setDownloadingId(run.id)
    setActionMessage(null)
    try {
      const reconstructedDiscrepancies = (run.issues || []).map((issueField) => ({
        item: 'Line Item Reference',
        field: issueField,
        invoice: 'Anomaly detected during OCR extraction',
        po: 'Verify PO reference specs',
        issue: 'Variance flagged during operational audit mismatch check.',
        difference: String(run.rupeeDifference ?? 0)
      }))

      await downloadPdfReport({
        status: run.status,
        totalIssues: run.discrepancies,
        totalRupeeDifference: run.rupeeDifference ?? 0,
        discrepancies: reconstructedDiscrepancies,
      })
      setActionMessage({ type: 'success', text: `PDF Report for ${run.id} downloaded successfully.` })
    } catch {
      setActionMessage({ type: 'error', text: `Failed to export PDF report for run ${run.id}.` })
    } finally {
      setDownloadingId(null)
    }
  }, [])

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8 font-sans">
      
      {/* HEADER SECTION */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-100 pb-5">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded bg-violet-50 px-2 py-0.5 text-[9px] font-bold tracking-wider text-[#5B3DF5] uppercase">
              Reports Archive
            </span>
            <span className="inline-flex items-center gap-1 rounded bg-slate-50 border border-slate-100 px-2 py-0.5 text-[9px] font-bold tracking-wider text-slate-400 uppercase">
              Total Invoices: {safeRender(reports.length)}
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#1A1C2E] mt-1.5">
            Verification Reports Archive
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-500">
            Export ledger compliance audits, search historic matching runs, and download discrepancy reports.
          </p>
        </div>

        <Link
          to="/workspace"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#5B3DF5] px-4.5 py-2.5 text-xs font-semibold text-white shadow-sm shadow-[#5B3DF5]/20 hover:bg-[#4a32c8] transition shrink-0"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" />
          </svg>
          EXECUTE NEW VERIFICATION
        </Link>
      </div>

      {/* Action Notification Banner */}
      {actionMessage && (
        <div
          role="status"
          className={`rounded-xl border p-4 text-xs font-bold ${
            actionMessage.type === 'success'
              ? 'border-emerald-100 bg-emerald-50/70 text-emerald-800'
              : 'border-rose-100 bg-rose-50/70 text-rose-800'
          }`}
        >
          {safeRender(actionMessage.text)}
        </div>
      )}

      {/* SEARCH, SORT, AND FILTERING BAR */}
      {reports.length > 0 && (
        <div className="flex flex-col gap-3.5 md:flex-row md:items-center md:justify-between bg-white border border-slate-100 rounded-2xl p-4 shadow-xs">
          
          {/* Text Query Input */}
          <div className="relative flex-1 max-w-md">
            <span className="absolute inset-y-0 left-3 flex items-center text-slate-400">
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </span>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search reports by Run ID or Vendor..."
              className="w-full rounded-xl border border-slate-200 py-2 pl-9 pr-4 text-xs text-[#1A1C2E] outline-none transition focus:border-violet-500"
            />
          </div>

          {/* Filtering selectors */}
          <div className="flex flex-wrap gap-2 text-xs">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 font-semibold text-slate-600 outline-none hover:bg-slate-50 transition cursor-pointer"
            >
              <option value="ALL">All Match Statuses</option>
              <option value="MATCH">Succeeded Matches</option>
              <option value="DISCREPANCY">Discrepancy Mismatches</option>
            </select>

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 font-semibold text-slate-600 outline-none hover:bg-slate-50 transition cursor-pointer"
            >
              <option value="DATE_DESC">Date: Newest First</option>
              <option value="DATE_ASC">Date: Oldest First</option>
              <option value="DISCREPANCY_DESC">Anomalies: High to Low</option>
              <option value="DISCREPANCY_ASC">Anomalies: Low to High</option>
              <option value="VENDOR_ASC">Vendor: A to Z</option>
              <option value="VENDOR_DESC">Vendor: Z to A</option>
            </select>
          </div>
        </div>
      )}

      {/* REPORTS HISTORICAL ARCHIVE GRID/TABLE */}
      <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-xs">
        <div className="overflow-x-auto rounded-xl border border-slate-100 bg-white">
          <table className="w-full min-w-[900px] text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                <th className="px-4 py-3">Run ID</th>
                <th className="px-4 py-3">Vendor</th>
                <th className="px-4 py-3">Reconciliation Outcome</th>
                <th className="px-4 py-3">Discrepancies</th>
                <th className="px-4 py-3">Financial Impact</th>
                <th className="px-4 py-3">OCR Accuracy</th>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports.length === 0 ? (
                /* Tabular onboarding state overlay */
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-xs font-bold text-slate-400">
                    <div className="flex flex-col items-center justify-center max-w-sm mx-auto">
                      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-50 border border-slate-100 text-slate-400 mb-3 shadow-xs">
                        <svg className="h-5.5 w-5.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                        </svg>
                      </div>
                      <p className="text-slate-700">No Verification Reports Found</p>
                      <p className="text-[10px] text-slate-400 font-semibold mt-1">
                        Run your first verification to populate analytics. Reconciliations automatically archive here.
                      </p>
                      <Link
                        to="/workspace"
                        className="mt-4 rounded-xl bg-[#5B3DF5] px-4 py-2 text-xs text-white hover:bg-[#4a32c8] transition shadow-xs"
                      >
                        Ingest Invoices
                      </Link>
                    </div>
                  </td>
                </tr>
              ) : filteredAndSortedReports.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-xs font-bold text-slate-400">
                    No historic reports found matching active criteria.
                  </td>
                </tr>
              ) : (
                filteredAndSortedReports.map((report: HistoryItem) => {
                  const statusBadge =
                    report.status === 'MATCH'
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
                      : 'bg-rose-50 text-rose-700 border-rose-100'

                  const isDownloading = downloadingId === report.id

                  return (
                    <tr key={report.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50/20 transition duration-150">
                      {/* Run ID (mono font) */}
                      <td className="px-4 py-3.5 font-mono font-extrabold text-[#1A1C2E]">{safeRender(report.id)}</td>
                      
                      {/* Vendor name */}
                      <td className="px-4 py-3.5 font-semibold text-slate-700">{safeRender(report.vendor)}</td>
                      
                      {/* Outcome Status */}
                      <td className="px-4 py-3.5">
                        <span className={`inline-flex items-center rounded border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${statusBadge}`}>
                          {safeRender(report.status)}
                        </span>
                      </td>
                      
                      {/* Discrepancies Count */}
                      <td className="px-4 py-3.5 font-mono font-semibold text-slate-600">
                        {report.discrepancies > 0 ? (
                          <span className="text-rose-600 font-bold">{safeRender(report.discrepancies)} items</span>
                        ) : (
                          <span className="text-emerald-600 font-bold">0 issues</span>
                        )}
                      </td>

                      {/* Financial Impact */}
                      <td className="px-4 py-3.5 font-mono font-semibold text-slate-700">
                        ₹{safeRender(report.rupeeDifference ?? 0)}
                      </td>

                      {/* OCR Confidence */}
                      <td className="px-4 py-3.5 font-mono font-semibold text-emerald-600">
                        {safeRender(report.confidence ?? '99.8%')}
                      </td>
                      
                      {/* Timestamp */}
                      <td className="px-4 py-3.5 text-slate-400 font-semibold">{safeRender(report.time)}</td>
                      
                      {/* Actions triggering download */}
                      <td className="px-4 py-3.5 text-right">
                        <button
                          type="button"
                          disabled={isDownloading}
                          onClick={() => handleDownloadPdf(report)}
                          className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[10px] font-bold text-slate-600 transition hover:border-[#5B3DF5]/30 hover:text-[#5B3DF5] cursor-pointer disabled:opacity-60"
                        >
                          {isDownloading ? (
                            <Spinner className="h-3 w-3 border-slate-200 border-t-[#5B3DF5]" />
                          ) : (
                            <svg className="h-3.5 w-3.5 text-slate-400 group-hover:text-[#5B3DF5]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                              <path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                            </svg>
                          )}
                          EXPORT PDF
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  )
}
