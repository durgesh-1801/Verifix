import { LogoMark } from '../ui/LogoMark'

export function FinanceOSPanel({
  onConfigure,
  onDemo,
  invoiceLabel,
  validated,
  savings,
  accuracy,
}: {
  onConfigure: () => void
  onDemo: () => void
  invoiceLabel: string
  validated: boolean
  savings: string
  accuracy: string
}) {
  return (
    <section className="py-16 sm:py-20">
      <div className="overflow-hidden rounded-3xl border border-gray-200/80 bg-white shadow-xl shadow-slate-200/40">
        <div className="grid lg:grid-cols-[1.1fr_0.9fr]">
          <div className="p-8 sm:p-10 lg:p-12">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#5B3DF5]/10 text-[#5B3DF5]">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
            </div>
            <h2 className="mt-6 text-3xl font-bold tracking-tight text-[#1A1C2E] sm:text-4xl">
              The OS for{' '}
              <span className="text-[#5B3DF5]">AI-first finance.</span>
            </h2>
            <p className="mt-4 max-w-md text-base leading-relaxed text-slate-600">
              Stop manually scrolling through PDFs. Deploy your first AI verification pipeline in minutes.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={onConfigure}
                className="inline-flex items-center gap-2 rounded-xl bg-[#5B3DF5] px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-[#5B3DF5]/20 transition hover:bg-[#4a32c8]"
              >
                Configure Workspace
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </button>
              <button
                type="button"
                onClick={onDemo}
                className="rounded-xl border border-gray-200 bg-white px-5 py-3 text-sm font-semibold text-[#1A1C2E] transition hover:border-gray-300"
              >
                Book Enterprise Demo
              </button>
            </div>
            <div className="mt-10 flex flex-wrap gap-6 border-t border-gray-100 pt-8 text-[11px] font-semibold tracking-wide text-slate-400">
              <span>SOC2 TYPE II</span>
              <span>ERP INTEGRATED</span>
              <span>FULL AUDIT LOGS</span>
            </div>
          </div>

          <div className="relative bg-gradient-to-br from-[#5B3DF5] via-[#5B3DF5] to-[#4338CA] p-8 sm:p-10">
            <div className="space-y-4">
              <div className="rounded-2xl border border-white/20 bg-white/10 p-4 backdrop-blur-md">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-semibold tracking-widest text-white/60">ACTIVE VERIFICATION</p>
                    <p className="mt-1 font-mono text-sm font-bold text-white">{invoiceLabel}</p>
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                      validated ? 'bg-emerald-400/20 text-emerald-200' : 'bg-amber-400/20 text-amber-100'
                    }`}
                  >
                    {validated ? 'VALIDATED' : 'PENDING'}
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-2xl border border-white/20 bg-white/10 p-4 backdrop-blur-md">
                  <p className="text-[10px] font-semibold tracking-widest text-white/60">SAVINGS</p>
                  <p className="mt-1 text-2xl font-bold text-white">{savings}</p>
                </div>
                <div className="rounded-2xl border border-white/20 bg-white/10 p-4 backdrop-blur-md">
                  <p className="text-[10px] font-semibold tracking-widest text-white/60">ACCURACY</p>
                  <p className="mt-1 text-2xl font-bold text-white">{accuracy}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-2xl border border-white/20 bg-white/10 p-4 backdrop-blur-md">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/15">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                    <path d="M9 12l2 2 4-4" />
                  </svg>
                </div>
                <div>
                  <p className="text-[10px] font-semibold tracking-widest text-white/60">COMPLIANCE</p>
                  <p className="font-semibold text-white">Audit-Ready Ledger</p>
                </div>
              </div>
            </div>
            <LogoMark className="absolute bottom-6 right-6 opacity-20" />
          </div>
        </div>
      </div>
    </section>
  )
}
