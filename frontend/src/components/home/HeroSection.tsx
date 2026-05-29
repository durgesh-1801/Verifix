import { VerificationLedger, discrepanciesToRows } from './VerificationLedger'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

function MetaItem({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <span className="flex items-center gap-2 text-[11px] font-semibold tracking-wide text-slate-400">
      {icon}
      {label}
    </span>
  )
}

export function HeroSection({
  onOpenWorkspace,
  onTryDemo,
  onRunAudit,
  flaggedCount,
  ledgerRows,
}: {
  onOpenWorkspace: () => void
  onTryDemo: () => void
  onRunAudit: () => void
  flaggedCount: number
  ledgerRows?: ReturnType<typeof discrepanciesToRows>
}) {
  const confidence = flaggedCount === 0 ? '99.8%' : `${Math.max(92, 99.8 - flaggedCount * 2).toFixed(1)}%`

  return (
    <section id="hero" className="scroll-mt-20 py-12 sm:py-16 lg:py-20">
      <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
        <div>
          <h1 className="max-w-xl text-4xl font-extrabold leading-[1.08] tracking-tight text-[#1A1C2E] sm:text-5xl lg:text-[3.25rem]">
            AI invoice verification{' '}
            <span className="bg-gradient-to-r from-[#5B3DF5] to-[#3B82F6] bg-clip-text text-transparent">
              for modern finance.
            </span>
          </h1>
          <p className="mt-5 max-w-lg text-base leading-relaxed text-slate-600 sm:text-lg">
            Automate OCR, reconciliation, and audit workflows in one unified AI workspace.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={onOpenWorkspace}
              className="rounded-xl bg-[#5B3DF5] px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-[#5B3DF5]/25 transition hover:bg-[#4a32c8]"
            >
              Open Workspace
            </button>
            <button
              type="button"
              onClick={onTryDemo}
              className="rounded-xl border border-gray-200 bg-white px-6 py-3 text-sm font-semibold text-[#1A1C2E] shadow-sm transition hover:border-gray-300"
            >
              Try Demo
            </button>
            <Link
              to="/login"
              className="rounded-xl border border-gray-200 bg-white px-6 py-3 text-sm font-semibold text-[#1A1C2E] shadow-sm transition hover:border-gray-300 hover:bg-slate-50"
            >
              Login
            </Link>
            <Link
              to="/signup"
              className="rounded-xl bg-[#5B3DF5] px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-[#5B3DF5]/25 transition hover:bg-[#4a32c8]"
            >
              Signup
            </Link>
          </div>
          <div className="mt-10 flex flex-wrap gap-6 border-t border-gray-100 pt-8">
            <MetaItem
              label="SOC2 CERTIFIED"
              icon={
                <svg className="text-slate-400" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
              }
            />
            <MetaItem
              label="AUDIT TRAILS"
              icon={
                <svg className="text-slate-400" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <path d="M14 2v6h6" />
                </svg>
              }
            />
            <MetaItem
              label="ERP READY"
              icon={
                <svg className="text-slate-400" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="2" y="3" width="20" height="14" rx="2" />
                  <path d="M8 21h8M12 17v4" />
                </svg>
              }
            />
          </div>
        </div>

        <VerificationLedger
          flaggedCount={flaggedCount}
          confidence={confidence}
          rows={ledgerRows}
          onRunAudit={onRunAudit}
        />
      </div>
    </section>
  )
}
