import { Link } from 'react-router-dom'
import { useState, useEffect, useMemo } from 'react'
import { 
  loadVerificationHistory, 
  calculateKPIs, 
  aggregateVendorStats, 
  generateTelemetryLogs 
} from '../lib/analytics'
import type { HistoryItem } from '../lib/analytics'

// SVG Velocity Chart Dimensions & Coordinates
const CHART_GRID_LINES = [0, 8, 16, 24, 32]

export default function Dashboard() {
  const [reports, setReports] = useState<HistoryItem[]>([])

  useEffect(() => {
    setReports(loadVerificationHistory())
  }, [])

  // 1. Core KPIs dynamic calculations from centralized analytics engine
  const kpis = useMemo(() => calculateKPIs(reports), [reports])
  const {
    totalProcessed,
    totalDiscrepancies,
    flaggedRate,
    avgConfidence,
    avgDuration,
    successRate
  } = kpis

  // 2. Dynamic Chart coordinates calculation
  const chartData = useMemo(() => {
    if (reports.length === 0) return []
    const reversed = [...reports].reverse() // Chronological order
    const maxIssues = Math.max(...reversed.map(r => r.discrepancies), 4)
    const count = reversed.length
    const spacing = count > 1 ? 520 / (count - 1) : 520

    return reversed.map((run, idx) => {
      const x = 40 + idx * spacing
      const y = 180 - (run.discrepancies / maxIssues) * 130 // Fit in [50, 180]
      return { x, y, discrepancies: run.discrepancies, label: (run.vendor || 'Run').slice(0, 8) }
    })
  }, [reports])

  const areaPath = useMemo(() => {
    if (chartData.length === 0) return ''
    if (chartData.length === 1) return `M ${chartData[0].x} 180 L ${chartData[0].x} ${chartData[0].y} L ${chartData[0].x} 180 Z`
    return `M ${chartData[0].x} 180 ` + chartData.map(pt => `L ${pt.x} ${pt.y}`).join(' ') + ` L ${chartData[chartData.length - 1].x} 180 Z`
  }, [chartData])

  const strokePath = useMemo(() => {
    if (chartData.length === 0) return ''
    return chartData.map((pt, idx) => `${idx === 0 ? 'M' : 'L'} ${pt.x} ${pt.y}`).join(' ')
  }, [chartData])

  // 3. Dynamic issue breakdown
  const categoryBreakdown = useMemo(() => {
    const counts: Record<string, number> = {
      'Unit Price Mismatch': 0,
      'Missing in Purchase Order': 0,
      'Tax Handling Variance': 0,
      'Quantity Discrepancy': 0,
    }

    let total = 0
    reports.forEach((run) => {
      if (run.issues) {
        run.issues.forEach((issue) => {
          const key = Object.keys(counts).find((k) => k.toLowerCase() === issue.toLowerCase()) || 'Unit Price Mismatch'
          counts[key] += 1
          total += 1
        })
      }
    })

    if (total === 0) {
      return Object.keys(counts).map((k) => ({ label: k, pct: 0 }))
    }

    return Object.entries(counts).map(([label, count]) => ({
      label,
      pct: Math.round((count / total) * 100),
    }))
  }, [reports])

  // 4. Dynamic Vendor stats grouping via centralized aggregation
  const vendorStats = useMemo(() => aggregateVendorStats(reports), [reports])

  // 5. Dynamic Telemetry Logs via centralized stream compiler
  const telemetryLogs = useMemo(() => generateTelemetryLogs(reports), [reports])

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8 font-sans">
      
      {/* HEADER SECTION */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#1A1C2E]">
            Finance Operations Dashboard
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-500">
            Monitoring enterprise OCR extractions, three-way matches, and ledger discrepancies.
          </p>
        </div>
        
        <Link
          to="/workspace"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#5B3DF5] px-4.5 py-2.5 text-xs font-semibold text-white shadow-sm shadow-[#5B3DF5]/20 hover:bg-[#4a32c8] transition"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 4v16m8-8H4" />
          </svg>
          NEW VERIFICATION RUN
        </Link>
      </div>

      {/* 1. KPI METRIC GRID */}
      <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
        
        {/* Card 1: Total Processed */}
        <div className="group rounded-2xl border border-slate-100 bg-white p-5 shadow-sm hover:shadow-md transition duration-300 relative overflow-hidden">
          <div className="absolute right-0 top-0 h-16 w-16 -translate-y-4 translate-x-4 rounded-full bg-violet-50/40 group-hover:scale-110 transition-transform duration-300" />
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Total Processed</p>
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-50 text-[#5B3DF5] group-hover:bg-[#5B3DF5] group-hover:text-white transition duration-300">
              <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" />
              </svg>
            </span>
          </div>
          <p className="mt-3 text-3xl font-extrabold text-[#1A1C2E] tracking-tight">{totalProcessed}</p>
          <div className="mt-2.5 flex items-center gap-1.5">
            <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">
              Live Channels
            </span>
            <span className="text-[10px] font-semibold text-slate-400">active ledger runs</span>
          </div>
        </div>

        {/* Card 2: Discrepancies Flagged */}
        <div className="group rounded-2xl border border-slate-100 bg-white p-5 shadow-sm hover:shadow-md transition duration-300 relative overflow-hidden">
          <div className="absolute right-0 top-0 h-16 w-16 -translate-y-4 translate-x-4 rounded-full bg-rose-50/40 group-hover:scale-110 transition-transform duration-300" />
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Discrepancies Flagged</p>
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-rose-50 text-rose-600 group-hover:bg-rose-500 group-hover:text-white transition duration-300">
              <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </span>
          </div>
          <p className="mt-3 text-3xl font-extrabold text-[#1A1C2E] tracking-tight">{totalDiscrepancies}</p>
          <div className="mt-2.5 flex items-center gap-1.5">
            <span className="text-[10px] font-bold text-rose-600 bg-rose-50 px-1.5 py-0.5 rounded">
              {flaggedRate}
            </span>
            <span className="text-[10px] font-semibold text-slate-400">flagged rate</span>
          </div>
        </div>

        {/* Card 3: Average OCR Confidence */}
        <div className="group rounded-2xl border border-slate-100 bg-white p-5 shadow-sm hover:shadow-md transition duration-300 relative overflow-hidden">
          <div className="absolute right-0 top-0 h-16 w-16 -translate-y-4 translate-x-4 rounded-full bg-emerald-50/40 group-hover:scale-110 transition-transform duration-300" />
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Average OCR Confidence</p>
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 group-hover:bg-emerald-500 group-hover:text-white transition duration-300">
              <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <rect x="4" y="4" width="16" height="16" rx="2" />
                <path d="M9 9h6v6H9z" />
                <line x1="9" y1="1" x2="9" y2="4" />
                <line x1="15" y1="1" x2="15" y2="4" />
                <line x1="9" y1="20" x2="9" y2="23" />
                <line x1="15" y1="20" x2="15" y2="23" />
                <line x1="20" y1="9" x2="23" y2="9" />
                <line x1="20" y1="15" x2="23" y2="15" />
                <line x1="1" y1="9" x2="4" y2="9" />
                <line x1="1" y1="15" x2="4" y2="15" />
              </svg>
            </span>
          </div>
          <p className="mt-3 text-3xl font-extrabold text-[#1A1C2E] tracking-tight">{avgConfidence}</p>
          <div className="mt-2.5 flex items-center gap-1.5">
            <span className="text-[10px] font-bold text-[#5B3DF5] bg-violet-50 px-1.5 py-0.5 rounded">
              Stable
            </span>
            <span className="text-[10px] font-semibold text-slate-400">Across 14 fields</span>
          </div>
        </div>

        {/* Card 4: Processing Time */}
        <div className="group rounded-2xl border border-slate-100 bg-white p-5 shadow-sm hover:shadow-md transition duration-300 relative overflow-hidden">
          <div className="absolute right-0 top-0 h-16 w-16 -translate-y-4 translate-x-4 rounded-full bg-amber-50/40 group-hover:scale-110 transition-transform duration-300" />
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Processing Time</p>
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-50 text-amber-600 group-hover:bg-amber-500 group-hover:text-white transition duration-300">
              <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </span>
          </div>
          <p className="mt-3 text-3xl font-extrabold text-[#1A1C2E] tracking-tight">{avgDuration}</p>
          <div className="mt-2.5 flex items-center gap-1.5">
            <span className="text-[10px] font-bold text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded">
              OCR core
            </span>
            <span className="text-[10px] font-semibold text-slate-400">average execution</span>
          </div>
        </div>

        {/* Card 5: Success Rate */}
        <div className="group rounded-2xl border border-slate-100 bg-white p-5 shadow-sm hover:shadow-md transition duration-300 relative overflow-hidden">
          <div className="absolute right-0 top-0 h-16 w-16 -translate-y-4 translate-x-4 rounded-full bg-emerald-50/30 group-hover:scale-110 transition-transform duration-300" />
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Success Rate</p>
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 group-hover:bg-emerald-500 group-hover:text-white transition duration-300">
              <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z" />
              </svg>
            </span>
          </div>
          <p className="mt-3 text-3xl font-extrabold text-[#1A1C2E] tracking-tight">{successRate}</p>
          <div className="mt-2.5 flex items-center gap-1.5">
            <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">
              Perfect Matches
            </span>
            <span className="text-[10px] font-semibold text-slate-400">runs with 0 issues</span>
          </div>
        </div>

      </div>

      {/* 2. DISCREPANCY VELOCITY & METRIC BREAKDOWN ROW */}
      <div className="grid gap-6 lg:grid-cols-3">
        
        {/* Discrepancy Velocity Chart (2 cols) */}
        <div className="lg:col-span-2 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm space-y-4 relative">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-[#1A1C2E]">Discrepancy Velocity</h2>
              <p className="text-[10px] text-slate-400 mt-0.5">Daily discrepancy events detected across enterprise pipelines</p>
            </div>
            <span className="rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-1 text-[9px] font-bold text-[#5B3DF5] uppercase tracking-wider">
              Verification Trend
            </span>
          </div>

          {/* SVG Area Line Chart Container */}
          <div className="relative pt-4 w-full overflow-hidden">
            {/* SaaS Onboarding Overlay if empty */}
            {reports.length === 0 && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/70 backdrop-blur-xs text-center p-6 z-10">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-violet-50 text-[#5B3DF5] mb-2.5 shadow-sm">
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.25">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 14.25v2.25m3-4.5v4.5m3-6.75v6.75m3-9v9M6 20.25h12A2.25 2.25 0 0 0 20.25 18V6A2.25 2.25 0 0 0 18 3.75H6A2.25 2.25 0 0 0 3.75 6v12A2.25 2.25 0 0 0 6 20.25Z" />
                  </svg>
                </div>
                <h3 className="text-xs font-bold text-[#1A1C2E] uppercase tracking-wider">No Reconciliation Trends yet</h3>
                <p className="mt-1 text-[10px] text-slate-400 font-semibold max-w-xs leading-normal">
                  Discrepancy velocity waves and timeline analytics will populate dynamically once you execute your first invoice verification audit.
                </p>
                <Link to="/workspace" className="mt-3.5 rounded-xl bg-[#5B3DF5] px-3.5 py-1.5 text-[9.5px] font-bold text-white shadow-sm hover:bg-[#4a32c8] transition">
                  Ingest First Invoice
                </Link>
              </div>
            )}

            <svg viewBox="0 0 600 240" className="w-full h-auto overflow-visible select-none">
              <defs>
                <linearGradient id="area-gradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#5B3DF5" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#5B3DF5" stopOpacity="0" />
                </linearGradient>
              </defs>

              {/* Grid horizontal lines */}
              {CHART_GRID_LINES.map((val) => {
                const y = 200 - (val / 32) * 160
                return (
                  <g key={val}>
                    <line x1="20" y1={y} x2="580" y2={y} stroke="#F1F5F9" strokeWidth="1" strokeDasharray="4 4" />
                    <text x="0" y={y + 3} className="text-[8px] font-semibold fill-slate-400 font-mono text-right">{val}</text>
                  </g>
                )
              })}

              {/* Filled Area path */}
              {chartData.length > 0 && (
                <path d={areaPath} fill="url(#area-gradient)" />
              )}

              {/* Stroke Line path */}
              {chartData.length > 0 && (
                <path d={strokePath} fill="none" stroke="#5B3DF5" strokeWidth="2.75" strokeLinecap="round" strokeLinejoin="round" />
              )}

              {/* Data points (Interactive nodes) */}
              {chartData.map((pt, idx) => (
                <circle key={idx} cx={pt.x} cy={pt.y} r="3.5" fill="white" stroke="#5B3DF5" strokeWidth="2" />
              ))}

              {/* X Axis dates line */}
              <line x1="20" y1="205" x2="580" y2="205" stroke="#E2E8F0" strokeWidth="1" />

              {/* Dates labels under chart */}
              <g className="text-[7.5px] font-bold fill-slate-400 font-mono">
                {reports.length === 0 ? (
                  <>
                    <text x="300" y="218" textAnchor="middle">WAITING FOR RECONCILIATION RUN DATA</text>
                  </>
                ) : (
                  chartData.map((pt, idx) => (
                    <text key={idx} x={pt.x} y={218} textAnchor="middle">{pt.label}</text>
                  ))
                )}
              </g>
            </svg>
          </div>
        </div>

        {/* Metric Breakdown Progress Bars (1 col) */}
        <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm space-y-4">
          <div>
            <h2 className="text-base font-bold text-[#1A1C2E]">Metric Breakdown</h2>
            <p className="text-[10px] text-slate-400 mt-0.5">Distribution by category of detected issues</p>
          </div>

          <div className="space-y-4.5 pt-3">
            {reports.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 text-center text-slate-400">
                <p className="text-[11px] font-semibold">No discrepancy metrics logged.</p>
              </div>
            ) : (
              categoryBreakdown.map((item) => {
                const color =
                  item.label === 'Unit Price Mismatch'
                    ? 'bg-[#5B3DF5]'
                    : item.label === 'Missing in Purchase Order'
                      ? 'bg-amber-500'
                      : item.label === 'Tax Handling Variance'
                        ? 'bg-rose-500'
                        : 'bg-emerald-500'
                const textColor =
                  item.label === 'Unit Price Mismatch'
                    ? 'text-[#5B3DF5]'
                    : item.label === 'Missing in Purchase Order'
                      ? 'text-amber-600'
                      : item.label === 'Tax Handling Variance'
                        ? 'text-rose-600'
                        : 'text-emerald-600'

                return (
                  <div key={item.label} className="space-y-1">
                    <div className="flex justify-between items-center text-xs">
                      <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${color}`} />
                        <span className="font-semibold text-slate-700">{item.label}</span>
                      </div>
                      <span className={`font-bold font-mono ${textColor}`}>{item.pct}%</span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-slate-50 overflow-hidden">
                      <div className={`h-full rounded-full ${color}`} style={{ width: `${item.pct}%` }} />
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

      </div>

      {/* 3. VENDOR RISK PROFILES & OCR TELEMETRY LOGS */}
      <div className="grid gap-6 lg:grid-cols-3">
        
        {/* Vendor Risk Profiles Card (2 cols) */}
        <div className="lg:col-span-2 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm space-y-4">
          <div>
            <h2 className="text-base font-bold text-[#1A1C2E]">Vendor Risk Profiles</h2>
            <p className="text-[10px] text-slate-400 mt-0.5">Reconciliation discrepancy weights across core active suppliers</p>
          </div>

          {/* Grid of Vendor Risk Profiles */}
          <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
            {vendorStats.length === 0 ? (
              <div className="col-span-full py-10 flex flex-col items-center justify-center text-center">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-50 border border-slate-100 text-slate-400 mb-2">
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.005 9.005 0 0 0-3.151-5.652 4 4 0 1 0-5.698 0A9.005 9.005 0 0 0 6 18.72M12 22.5c5.799 0 10.5-4.701 10.5-10.5S17.799 1.5 12 1.5 1.5 6.201 1.5 12 6.201 22.5 12 22.5Z" />
                  </svg>
                </div>
                <h4 className="text-xs font-bold text-slate-700">No Vendor Profiles Active</h4>
                <p className="text-[10px] text-slate-400 font-semibold max-w-xs mt-0.5">
                  Vendor risk profiles build dynamically from reconciliations.
                </p>
              </div>
            ) : (
              vendorStats.map((vendor) => {
                const ringColor =
                  vendor.risk === 'HIGH'
                    ? 'border-rose-100 hover:border-rose-300'
                    : vendor.risk === 'MEDIUM'
                      ? 'border-amber-100 hover:border-amber-300'
                      : 'border-slate-100 hover:border-emerald-300'
                const badgeStyle =
                  vendor.risk === 'HIGH'
                    ? 'bg-rose-50 text-rose-700'
                    : vendor.risk === 'MEDIUM'
                      ? 'bg-amber-50 text-amber-700'
                      : 'bg-emerald-50 text-emerald-700'

                return (
                  <div
                    key={vendor.name}
                    className={`rounded-xl border bg-white p-4.5 transition duration-300 hover:shadow-sm ${ringColor}`}
                  >
                    <div className="flex justify-between items-start gap-2">
                      <p className="font-bold text-xs text-[#1A1C2E] truncate">{vendor.name}</p>
                      <span className={`text-[8.5px] font-bold rounded px-1.5 py-0.5 ${badgeStyle}`}>
                        {vendor.risk}
                      </span>
                    </div>
                    
                    <div className="mt-3 flex items-center justify-between text-[10px] text-slate-500 font-semibold uppercase tracking-wider">
                      <span>{vendor.bills} bills</span>
                      <span className="text-slate-400">Rate: <span className="font-mono font-bold text-[#1A1C2E]">{vendor.discrepancyRate}</span></span>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* OCR Telemetry Logs Stream (1 col) */}
        <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm space-y-4">
          <div>
            <h2 className="text-base font-bold text-[#1A1C2E]">OCR Telemetry Logs</h2>
            <p className="text-[10px] text-slate-400 mt-0.5">Live pipeline streaming data events</p>
          </div>

          <ul className="space-y-4 pt-1 max-h-[300px] overflow-y-auto">
            {telemetryLogs.map((log, idx) => (
              <li key={idx} className="flex gap-3 text-xs leading-normal">
                <div className="flex flex-col items-center shrink-0">
                  <span className="font-mono text-[9.5px] font-bold text-slate-400 bg-slate-50 border border-slate-100 px-1 rounded">
                    {log.time}
                  </span>
                  {idx < telemetryLogs.length - 1 && (
                    <div className="w-0.5 bg-slate-100 flex-1 my-1.5" />
                  )}
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5">
                    <span className="inline-flex items-center gap-1 rounded bg-[#5B3DF5]/5 px-1 py-0.2 text-[8px] font-bold tracking-wider text-[#5B3DF5]">
                      <span className="h-1 w-1 rounded-full bg-[#5B3DF5] animate-ping" />
                      STREAMED
                    </span>
                  </div>
                  <p className="font-semibold text-slate-700 text-[11.5px]">{log.event}</p>
                  <p className="text-[10px] text-slate-500">{log.detail}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

      </div>

      {/* 4. RECENT REPORTS TABLE */}
      <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm space-y-4">
        <div>
          <h2 className="text-base font-bold text-[#1A1C2E]">Recent Verification Reports</h2>
          <p className="text-[10px] text-slate-400 mt-0.5">Latest OCR matching run outcomes and active discrepancies</p>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-100 bg-white">
          <table className="w-full min-w-[720px] text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                <th className="px-4 py-3">Invoice ID</th>
                <th className="px-4 py-3">Vendor</th>
                <th className="px-4 py-3">Reconciliation Status</th>
                <th className="px-4 py-3">Discrepancy Count</th>
                <th className="px-4 py-3">Processed Time</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-xs font-bold text-slate-400">
                    <div className="flex flex-col items-center justify-center">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-50 border border-slate-100 text-slate-400 mb-2">
                        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                        </svg>
                      </div>
                      <p className="text-slate-700 font-bold">No Verification Reports Found</p>
                      <p className="text-[10px] text-slate-400 font-semibold mt-0.5">
                        Run your first verification to populate analytics.
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                reports.map((report) => {
                  const statusBadge =
                    report.status === 'MATCH'
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
                      : 'bg-rose-50 text-rose-700 border-rose-100'

                  return (
                    <tr key={report.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50/20 transition duration-150">
                      <td className="px-4 py-3.5 font-mono font-bold text-[#1A1C2E]">{report.id}</td>
                      <td className="px-4 py-3.5 font-semibold text-slate-700">{report.vendor}</td>
                      <td className="px-4 py-3.5">
                        <span className={`inline-flex items-center rounded border px-2 py-0.5 text-[9px] font-bold ${statusBadge}`}>
                          {report.status}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 font-mono font-semibold text-slate-600">
                        {report.discrepancies > 0 ? (
                          <span className="text-rose-600">{report.discrepancies} items</span>
                        ) : (
                          <span className="text-emerald-600">0 issues</span>
                        )}
                      </td>
                      <td className="px-4 py-3.5 text-slate-400 font-semibold">{report.time}</td>
                      <td className="px-4 py-3.5 text-right">
                        <button
                          type="button"
                          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[10px] font-bold text-slate-600 transition hover:border-[#5B3DF5]/30 hover:text-[#5B3DF5] cursor-pointer"
                        >
                          VIEW RUN
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
