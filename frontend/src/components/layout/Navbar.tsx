import { Link } from 'react-router-dom'
import { LogoMark } from '../ui/LogoMark'
import { scrollToId } from '../../lib/scroll'

const NAV = [
  { label: 'Ledger', id: 'hero' },
  { label: 'Verification', id: 'workspace' },
  { label: 'Pipelines', id: 'pipeline' },
  { label: 'Reports', id: 'workspace' },
] as const

export function Navbar({ onOpenWorkspace }: { onOpenWorkspace: () => void }) {
  return (
    <header className="sticky top-0 z-50 border-b border-gray-100 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <button
          type="button"
          onClick={() => scrollToId('top')}
          className="flex items-center gap-2.5 rounded-lg outline-none ring-[#5B3DF5] focus-visible:ring-2"
        >
          <LogoMark />
          <span className="text-base font-bold tracking-tight text-[#1A1C2E]">Invoice AI</span>
        </button>

        <nav className="hidden items-center gap-8 md:flex" aria-label="Product">
          {NAV.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => scrollToId(item.id)}
              className="text-[11px] font-semibold tracking-[0.12em] text-slate-400 transition hover:text-slate-700"
            >
              {item.label.toUpperCase()}
            </button>
          ))}
        </nav>

        <div className="flex items-center gap-1.5 sm:gap-2.5">
          <Link
            to="/login"
            className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-[10px] font-semibold tracking-wide text-[#1A1C2E] shadow-sm transition hover:bg-slate-50 hover:border-gray-300 sm:px-4 sm:text-xs"
          >
            LOGIN
          </Link>
          <Link
            to="/signup"
            className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-[10px] font-semibold tracking-wide text-[#1A1C2E] shadow-sm transition hover:bg-slate-50 hover:border-gray-300 sm:px-4 sm:text-xs"
          >
            SIGNUP
          </Link>
          <button
            type="button"
            onClick={onOpenWorkspace}
            className="ml-1 rounded-lg bg-[#5B3DF5] px-3 py-2 text-[10px] font-semibold tracking-wide text-white shadow-sm shadow-[#5B3DF5]/25 transition hover:bg-[#4a32c8] sm:px-4 sm:text-xs"
          >
            OPEN WORKSPACE
          </button>
        </div>
      </div>
    </header>
  )
}
