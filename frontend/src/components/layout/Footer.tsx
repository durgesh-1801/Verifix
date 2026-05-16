import { LogoMark } from '../ui/LogoMark'

const LINKS = {
  Product: ['Audit Engine', 'PO Reconciliation', 'Fraud Detection', 'Compliance'],
  Company: ['About', 'Security', 'Resources', 'Contact'],
  Legal: ['Privacy', 'Terms', 'Cookie Policy'],
} as const

export function Footer() {
  return (
    <footer className="border-t border-gray-100 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <div className="flex items-center gap-2.5">
              <LogoMark />
              <span className="text-lg font-bold text-[#1A1C2E]">Invoice AI</span>
            </div>
            <p className="mt-3 max-w-xs text-sm text-slate-500">
              Intelligent verification for finance teams. Built by Reconix.
            </p>
            <div className="mt-5 flex gap-2">
              {['X', 'in', 'GH'].map((s) => (
                <span
                  key={s}
                  className="flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 text-[10px] font-bold text-slate-400"
                  aria-hidden
                >
                  {s}
                </span>
              ))}
            </div>
          </div>
          {(Object.keys(LINKS) as (keyof typeof LINKS)[]).map((heading) => (
            <div key={heading}>
              <p className="text-xs font-semibold tracking-widest text-slate-400">{heading.toUpperCase()}</p>
              <ul className="mt-4 space-y-2.5">
                {LINKS[heading].map((link) => (
                  <li key={link}>
                    <button
                      type="button"
                      className="text-sm text-slate-600 transition hover:text-[#1A1C2E]"
                    >
                      {link}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-12 flex flex-col gap-3 border-t border-gray-100 pt-6 text-xs text-slate-400 sm:flex-row sm:items-center sm:justify-between">
          <p className="font-semibold tracking-wide">© 2024 INVOICE AI INC.</p>
          <p className="flex items-center gap-2">
            <span>STATUS: FULL OPERATIONAL</span>
            <span className="font-bold text-emerald-500">LIVE • 99.9% UPTIME</span>
          </p>
        </div>
      </div>
    </footer>
  )
}
