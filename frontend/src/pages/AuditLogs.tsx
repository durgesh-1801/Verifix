import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { 
  loadVerificationHistory, 
  generateTelemetryLogs, 
  safeRender
} from '../lib/analytics'
import type {
  HistoryItem,
  TelemetryLog
} from '../lib/analytics'

export default function AuditLogs() {
  const [reports, setReports] = useState<HistoryItem[]>([])

  useEffect(() => {
    setReports(loadVerificationHistory())
  }, [])

  // Dynamic telemetry log compiling calculated via centralized utility
  const logs = useMemo(() => generateTelemetryLogs(reports), [reports])

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8 font-sans">
      
      {/* HEADER SECTION */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-100 pb-5">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded bg-[#5B3DF5]/5 px-2 py-0.5 text-[9px] font-bold tracking-wider text-[#5B3DF5] uppercase">
              Telemetry Core
            </span>
            <span className="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 text-[9px] font-bold tracking-wider text-emerald-700 uppercase">
              Telemetry Core: ONLINE
            </span>
            <span className="inline-flex items-center gap-1 rounded bg-slate-50 border border-slate-100 px-2 py-0.5 text-[9px] font-bold tracking-wider text-slate-400 uppercase">
              Logging Stream: active
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#1A1C2E] mt-1.5">
            System Operational Logs
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-500">
            Real-time pipeline streams, OCR entity ingestion details, ledger discrepancy reports, and active compliance flags.
          </p>
        </div>

        <Link
          to="/workspace"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#5B3DF5] px-4.5 py-2.5 text-xs font-semibold text-white shadow-sm shadow-[#5B3DF5]/20 hover:bg-[#4a32c8] transition shrink-0"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 0 1-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 0 1 1.5.124m7.5 10.376A8.965 8.965 0 0 0 12 12.75c-.975 0-1.897.155-2.76.44m7.5 4.06a9 9 0 0 1-15 0M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
          </svg>
          ACTIVATE ACTIVE STREAMS
        </Link>
      </div>

      {/* TIMELINE FEED CARDS CONTAINER */}
      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-xs max-w-3xl mx-auto space-y-6">
        <div>
          <h2 className="text-base font-bold text-[#1A1C2E]">Live Telemetry Stream</h2>
          <p className="text-[10px] text-slate-400 mt-0.5">Sequential logging compiled directly from active OCR pipeline events</p>
        </div>

        {reports.length === 0 ? (
          /* Onboarding empty state block */
          <div className="py-12 text-center flex flex-col items-center justify-center max-w-sm mx-auto">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-50 border border-slate-100 text-slate-400 mb-3 shadow-xs">
              <svg className="h-5.5 w-5.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 17.25v1.007a3 3 0 0 1-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0 1 15 18.257V17.25m6-12V15a2.25 2.25 0 0 1-2.25 2.25H5.25A2.25 2.25 0 0 1 3 15V5.25m18 0A2.25 2.25 0 0 0 18.75 3H5.25A2.25 2.25 0 0 0 3 5.25m18 0V12a2.25 2.25 0 0 1-2.25 2.25H5.25A2.25 2.25 0 0 1 3 12V5.25" />
              </svg>
            </div>
            <h3 className="text-xs font-bold text-[#1A1C2E] uppercase tracking-wider">No Telemetry streams logged</h3>
            <p className="mt-1 text-[10px] text-slate-400 font-semibold leading-normal">
              OCR telemetry will appear after processing documents. Upload and reconcile an invoice to activate system operations feed.
            </p>
            <Link
              to="/workspace"
              className="mt-4.5 inline-flex items-center justify-center gap-1 text-[9.5px] font-bold rounded-xl bg-[#5B3DF5] px-3.5 py-1.5 text-white shadow-sm hover:bg-[#4a32c8] transition"
            >
              Verify Invoice
            </Link>
          </div>
        ) : (
          <ul className="space-y-6 pt-2">
            {logs.map((log: TelemetryLog, idx: number) => {
              const isWarning = log.status === 'WARNING'
              const isCompliance = log.status === 'COMPLIANCE'
              
              const badgeStyle = isWarning
                ? 'bg-rose-50 text-rose-700'
                : isCompliance
                  ? 'bg-emerald-50 text-emerald-700'
                  : 'bg-violet-50 text-violet-700'

              const iconStyle = isWarning
                ? 'bg-rose-100 text-rose-600'
                : isCompliance
                  ? 'bg-emerald-100 text-emerald-600'
                  : 'bg-violet-100 text-violet-600'

              return (
                <li key={idx} className="flex gap-4 text-xs leading-normal relative group">
                  {/* Timeline connectors */}
                  {idx < logs.length - 1 && (
                    <div className="absolute left-[17px] top-9 w-0.5 bg-slate-100 bottom-0 -mb-6" />
                  )}

                  {/* Indicator bullet */}
                  <div className="shrink-0 flex items-center justify-center">
                    <div className={`h-9 w-9 rounded-xl flex items-center justify-center shadow-xs transition duration-300 group-hover:scale-105 ${iconStyle}`}>
                      {isWarning ? (
                        <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                      ) : isCompliance ? (
                        <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z" />
                        </svg>
                      ) : (
                        <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 14.25v2.25m3-4.5v4.5m3-6.75v6.75m3-9v9M6 20.25h12A2.25 2.25 0 0 0 20.25 18V6A2.25 2.25 0 0 0 18 3.75H6A2.25 2.25 0 0 0 3.75 6v12A2.25 2.25 0 0 0 6 20.25Z" />
                        </svg>
                      )}
                    </div>
                  </div>

                  {/* Log Event Text Detail */}
                  <div className="space-y-1 bg-slate-50/50 rounded-2xl border border-slate-100 p-4 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[8.5px] font-bold tracking-wider uppercase ${badgeStyle}`}>
                        {safeRender(log.status)}
                      </span>
                      <span className="font-mono text-[9px] font-bold text-slate-400">
                        {safeRender(log.time)}
                      </span>
                    </div>
                    <p className="font-extrabold text-slate-800 text-[12px] pt-1">{safeRender(log.event)}</p>
                    <p className="text-[10px] text-slate-500 font-semibold leading-relaxed pt-0.5">{safeRender(log.detail)}</p>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
