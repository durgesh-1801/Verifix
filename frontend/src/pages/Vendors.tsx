import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { 
  loadVerificationHistory, 
  aggregateVendorStats, 
  safeRender
} from '../lib/analytics'
import type {
  HistoryItem,
  VendorStat
} from '../lib/analytics'

export default function Vendors() {
  const [reports, setReports] = useState<HistoryItem[]>([])
  const [searchTerm, setSearchTerm] = useState('')
  const [riskFilter, setRiskFilter] = useState<string>('ALL')

  useEffect(() => {
    setReports(loadVerificationHistory())
  }, [])

  // Dynamic vendor stats grouping calculated via centralized utility
  const vendorStats = useMemo(() => aggregateVendorStats(reports), [reports])

  // Filter vendor list by search term and risk category
  const filteredVendors = useMemo(() => {
    return vendorStats.filter((v) => {
      const matchSearch = v.name.toLowerCase().includes(searchTerm.toLowerCase())
      const matchRisk = riskFilter === 'ALL' || v.risk === riskFilter
      return matchSearch && matchRisk
    })
  }, [vendorStats, searchTerm, riskFilter])

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8 font-sans">
      
      {/* HEADER SECTION */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-100 pb-5">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded bg-violet-50 px-2 py-0.5 text-[9px] font-bold tracking-wider text-[#5B3DF5] uppercase">
              Compliance Core
            </span>
            <span className="inline-flex items-center gap-1 rounded bg-slate-50 border border-slate-100 px-2 py-0.5 text-[9px] font-bold tracking-wider text-slate-400 uppercase">
              Active profiles: {safeRender(vendorStats.length)}
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#1A1C2E] mt-1.5">
            Vendor Risk Matrix
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-500">
            Monitor discrepancy frequencies, average extraction accuracy, and severity weight distributions.
          </p>
        </div>

        <Link
          to="/workspace"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#5B3DF5] px-4.5 py-2.5 text-xs font-semibold text-white shadow-sm shadow-[#5B3DF5]/20 hover:bg-[#4a32c8] transition shrink-0"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 4v16m8-8H4" />
          </svg>
          RUN COMPLIANCE AUDIT
        </Link>
      </div>

      {/* DYNAMIC SEARCH & FILTERING CONTROL BAR */}
      {vendorStats.length > 0 && (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between bg-white border border-slate-100 rounded-2xl p-4 shadow-xs">
          {/* Search Box */}
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
              placeholder="Search vendor profile names..."
              className="w-full rounded-xl border border-slate-200 py-2 pl-9 pr-4 text-xs text-[#1A1C2E] outline-none transition focus:border-violet-500"
            />
          </div>

          {/* Filters Select */}
          <div className="flex gap-2 shrink-0">
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 outline-none hover:bg-slate-50 transition cursor-pointer"
            >
              <option value="ALL">All Risk Ratings</option>
              <option value="LOW">Low Risk Only</option>
              <option value="MEDIUM">Medium Risk Only</option>
              <option value="HIGH">High Risk Only</option>
            </select>
          </div>
        </div>
      )}

      {/* REAL-DATA VENDOR COMPLIANCE CARDS GRID */}
      {reports.length === 0 ? (
        /* Onboarding empty state block */
        <div className="rounded-2xl border border-slate-100 bg-white p-8 py-16 text-center shadow-xs flex flex-col items-center justify-center max-w-xl mx-auto">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-50 border border-slate-100 text-slate-400 mb-4 shadow-xs">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.005 9.005 0 0 0-3.151-5.652 4 4 0 1 0-5.698 0A9.005 9.005 0 0 0 6 18.72M12 22.5c5.799 0 10.5-4.701 10.5-10.5S17.799 1.5 12 1.5 1.5 6.201 1.5 12 6.201 22.5 12 22.5Z" />
            </svg>
          </div>
          <h3 className="text-sm font-bold text-[#1A1C2E] uppercase tracking-wider">No Active Vendor Profiles</h3>
          <p className="mt-1.5 text-xs text-slate-400 font-semibold leading-relaxed max-w-sm">
            Vendor risk profiles build dynamically from reconciliations. Upload and verify an invoice in the workspace to initiate risk scoring pipeline.
          </p>
          <Link
            to="/workspace"
            className="mt-5 inline-flex items-center justify-center gap-1.5 rounded-xl bg-[#5B3DF5] px-4.5 py-2 text-xs font-semibold text-white shadow-sm shadow-[#5B3DF5]/20 hover:bg-[#4a32c8] transition"
          >
            Upload Document Run
          </Link>
        </div>
      ) : filteredVendors.length === 0 ? (
        <div className="text-center py-10 bg-white rounded-2xl border border-slate-100 text-xs font-bold text-slate-400">
          No vendor profiles match search query or selected filter criteria.
        </div>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {filteredVendors.map((vendor: VendorStat) => {
            const isHigh = vendor.risk === 'HIGH'
            const isMed = vendor.risk === 'MEDIUM'
            
            const ringColor = isHigh
              ? 'border-rose-100 hover:border-rose-300 hover:shadow-rose-50/20'
              : isMed
                ? 'border-amber-100 hover:border-amber-300 hover:shadow-amber-50/20'
                : 'border-slate-100 hover:border-emerald-300 hover:shadow-emerald-50/20'

            const badgeStyle = isHigh
              ? 'bg-rose-50 text-rose-700'
              : isMed
                ? 'bg-amber-50 text-amber-700'
                : 'bg-emerald-50 text-emerald-700'

            const totalSeverity = vendor.lowSeverityCount + vendor.mediumSeverityCount + vendor.highSeverityCount
            const lowPct = totalSeverity > 0 ? (vendor.lowSeverityCount / totalSeverity) * 100 : 0
            const medPct = totalSeverity > 0 ? (vendor.mediumSeverityCount / totalSeverity) * 100 : 0
            const highPct = totalSeverity > 0 ? (vendor.highSeverityCount / totalSeverity) * 100 : 0

            return (
              <div
                key={vendor.name}
                className={`rounded-2xl border bg-white p-5 shadow-xs transition duration-300 hover:shadow-md ${ringColor}`}
              >
                {/* Vendor Identity & Risk Classification pill */}
                <div className="flex justify-between items-start gap-3">
                  <div className="min-w-0">
                    <h3 className="font-extrabold text-sm text-[#1A1C2E] truncate">{safeRender(vendor.name)}</h3>
                    <p className="text-[10px] text-slate-400 font-semibold mt-0.5">Active Compliance Rating</p>
                  </div>
                  <span className={`text-[8.5px] font-bold rounded px-2 py-0.5 tracking-wider uppercase shrink-0 ${badgeStyle}`}>
                    {safeRender(vendor.risk)} Risk
                  </span>
                </div>

                {/* Numeric operational summaries */}
                <div className="grid grid-cols-2 gap-4 border-y border-slate-50 py-3.5 my-4 text-xs">
                  <div>
                    <span className="text-[9px] font-bold text-slate-400 uppercase">Bills Audited</span>
                    <p className="font-bold text-[#1A1C2E] mt-0.5">{safeRender(vendor.bills)} invoices</p>
                  </div>
                  <div>
                    <span className="text-[9px] font-bold text-slate-400 uppercase">Extraction Confidence</span>
                    <p className="font-mono font-bold text-emerald-600 mt-0.5">{safeRender(vendor.avgConfidence)}</p>
                  </div>
                </div>

                {/* Discrepancy details & Severity distributions */}
                <div className="space-y-3">
                  <div className="flex justify-between items-center text-[10px] font-bold uppercase text-slate-500 tracking-wider">
                    <span>Discrepancy Rate</span>
                    <span className={vendor.discrepancies > 0 ? 'text-rose-600' : 'text-emerald-600'}>
                      {safeRender(vendor.discrepancyRate)}
                    </span>
                  </div>

                  {/* Visual stacked discrepancy severity indicator bar */}
                  {totalSeverity > 0 ? (
                    <div className="space-y-2">
                      <div className="h-2 w-full rounded-full bg-slate-50 overflow-hidden flex">
                        {highPct > 0 && <div className="h-full bg-rose-500" style={{ width: `${highPct}%` }} title="High Severity" />}
                        {medPct > 0 && <div className="h-full bg-amber-500" style={{ width: `${medPct}%` }} title="Medium Severity" />}
                        {lowPct > 0 && <div className="h-full bg-[#5B3DF5]" style={{ width: `${lowPct}%` }} title="Low Severity" />}
                      </div>
                      <div className="flex justify-between text-[9px] font-bold text-slate-400 font-mono">
                        <span className="flex items-center gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-[#5B3DF5]" />
                          LOW: {vendor.lowSeverityCount}
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                          MED: {vendor.mediumSeverityCount}
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
                          HIGH: {vendor.highSeverityCount}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-2 rounded-lg bg-emerald-50/50 border border-emerald-100 text-[9.5px] font-extrabold text-emerald-800">
                      ✓ No anomalies flagged. 100% matched.
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
