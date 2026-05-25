import { Link, useNavigate } from 'react-router-dom'
import { useState } from 'react'

export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // Simulated authentication bypass for the prototype
    navigate('/dashboard')
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-12 bg-white font-sans selection:bg-violet-100">
      
      {/* LEFT PANEL: Branding & Visual Ledger (5 columns) */}
      <div className="lg:col-span-5 hidden lg:flex flex-col justify-between bg-[#0A0D1A] p-10 xl:p-12 relative overflow-hidden text-white border-r border-white/5">
        
        {/* Subtle decorative grid overlay */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900 via-[#0A0D1A] to-[#05060B] z-0" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff03_1px,transparent_1px),linear-gradient(to_bottom,#ffffff03_1px,transparent_1px)] bg-[size:4rem_4rem] z-0" />

        <div className="relative z-10 space-y-6">
          {/* Logo Brand Block */}
          <div className="space-y-2">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#5B3DF5] shadow-sm shadow-[#5B3DF5]/30">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M13 2L3 10H9L8 14L14 6H8L13 2Z" fill="white" />
                </svg>
              </div>
              <span className="text-lg font-bold tracking-tight">INVOICE AI</span>
            </div>
            <span className="inline-flex items-center rounded-md bg-[#5B3DF5]/10 border border-[#5B3DF5]/20 px-2.5 py-0.5 text-[10px] font-bold tracking-wider text-[#818CF8] uppercase">
              A.I. Audit Infrastructure
            </span>
          </div>

          {/* Slogan */}
          <div className="space-y-4 pt-4">
            <h1 className="text-3xl xl:text-4xl font-extrabold leading-[1.15] tracking-tight">
              The ledger validation engine for{' '}
              <span className="bg-gradient-to-r from-[#818CF8] to-[#9333EA] bg-clip-text text-transparent">
                modern finance.
              </span>
            </h1>
            <p className="text-xs xl:text-sm text-slate-400 leading-relaxed max-w-sm">
              Automate OCR processing, line-item reconciliation, and dynamic audit reports within seconds. Safe, exact, enterprise ready.
            </p>
          </div>

          {/* Interactive visual Ledger component */}
          <div className="pt-6">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur-md space-y-4">
              <div className="flex items-center justify-between border-b border-white/5 pb-2.5">
                <p className="text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                  Instance Verification Ledger
                </p>
                <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[9px] font-bold tracking-wider text-emerald-400 uppercase">
                  Active Engine
                </span>
              </div>
              
              <ul className="space-y-2">
                <li className="flex items-center justify-between rounded-xl bg-white/5 border border-white/5 px-3 py-2.5 text-xs">
                  <span className="text-slate-300">Vendor: Stripe Inc</span>
                  <span className="font-semibold text-emerald-400">MATCH (99.8%)</span>
                </li>
                <li className="flex items-center justify-between rounded-xl bg-white/5 border border-white/5 px-3 py-2.5 text-xs">
                  <span className="text-slate-300">Cloud Billing TAX (18% vs 12%)</span>
                  <span className="font-semibold text-rose-400">MISMATCH</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Bottom stats and compliance badges */}
        <div className="relative z-10 space-y-6 pt-10 border-t border-white/5">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-lg xl:text-xl font-bold tracking-tight">99.8%</p>
              <p className="text-[9px] font-bold tracking-wider text-slate-400 uppercase mt-0.5">Extraction Precision</p>
            </div>
            <div>
              <p className="text-lg xl:text-xl font-bold tracking-tight">&lt; 2.5s</p>
              <p className="text-[9px] font-bold tracking-wider text-slate-400 uppercase mt-0.5">Processing Speed</p>
            </div>
            <div>
              <p className="text-lg xl:text-xl font-bold tracking-tight">SOC2</p>
              <p className="text-[9px] font-bold tracking-wider text-slate-400 uppercase mt-0.5">Certified Compliant</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 text-[8px] font-bold tracking-wider text-slate-500">
            <span className="border border-white/5 rounded px-1.5 py-0.5">SOC2 TYPE II</span>
            <span className="border border-white/5 rounded px-1.5 py-0.5">AUDIT TRAILS</span>
            <span className="border border-white/5 rounded px-1.5 py-0.5">ERP INTEGRATED</span>
          </div>
        </div>
      </div>

      {/* RIGHT PANEL: Sign In Form (7 columns) */}
      <div className="lg:col-span-7 flex flex-col justify-center items-center px-6 py-12 sm:px-12 md:px-20 lg:px-16 xl:px-24">
        <div className="w-full max-w-md space-y-8">
          
          {/* Mobile logo (only shown when large is hidden) */}
          <div className="flex items-center gap-2 lg:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#5B3DF5] text-white">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M13 2L3 10H9L8 14L14 6H8L13 2Z" fill="white" />
              </svg>
            </div>
            <span className="text-base font-bold tracking-tight text-[#1A1C2E]">Invoice AI</span>
          </div>

          {/* Heading */}
          <div>
            <h2 className="text-2xl font-bold text-slate-800 tracking-tight sm:text-3xl">
              Sign In to Dashboard
            </h2>
            <p className="mt-2 text-xs sm:text-sm text-slate-500">
              Enter your credentials to manage your AI invoices pipeline.
            </p>
          </div>

          {/* Form */}
          <form className="space-y-5" onSubmit={handleSubmit}>
            
            {/* Email Address */}
            <div className="space-y-1.5">
              <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Email Address
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-3 flex items-center text-slate-400">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                </span>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="w-full rounded-xl border border-slate-200 py-3 pl-10 pr-4 text-xs text-[#1A1C2E] placeholder-slate-400 outline-none transition focus:border-violet-500 focus:bg-white shadow-sm"
                />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  Password
                </label>
                <Link to="/login" className="text-[10px] font-bold text-[#5B3DF5] hover:text-[#4a32c8] transition">
                  Forgot Password?
                </Link>
              </div>
              <div className="relative">
                <span className="absolute inset-y-0 left-3 flex items-center text-slate-400">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                </span>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-xl border border-slate-200 py-3 pl-10 pr-4 text-xs text-[#1A1C2E] placeholder-slate-400 outline-none transition focus:border-violet-500 focus:bg-white shadow-sm"
                />
              </div>
            </div>

            {/* Remember Me */}
            <div className="flex items-center">
              <input
                id="remember_me"
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300 text-violet-600 focus:ring-violet-500 cursor-pointer accent-violet-600"
              />
              <label htmlFor="remember_me" className="ml-2 text-xs text-slate-500 font-semibold cursor-pointer">
                Remember me for 30 days
              </label>
            </div>

            {/* Sign In Button */}
            <button
              type="submit"
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#5B3DF5] py-3 text-xs sm:text-sm font-semibold text-white shadow-md shadow-violet-600/20 hover:bg-[#4a32c8] transition cursor-pointer"
            >
              Enter Active Workspace
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </button>
          </form>

          {/* SSO Separator */}
          <div className="relative py-2">
            <div className="absolute inset-0 flex items-center" aria-hidden="true">
              <div className="w-full border-t border-slate-100" />
            </div>
            <div className="relative flex justify-center text-[9px] font-bold uppercase tracking-wider text-slate-400 bg-white px-3">
              Or connect with sso
            </div>
          </div>

          {/* SSO Buttons */}
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              className="flex items-center justify-center gap-2.5 rounded-xl border border-slate-100 bg-slate-50/50 py-2.5 px-4 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition cursor-pointer"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/>
              </svg>
              Google Space
            </button>
            <button
              type="button"
              className="flex items-center justify-center gap-2.5 rounded-xl border border-slate-100 bg-slate-50/50 py-2.5 px-4 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition cursor-pointer"
            >
              <svg className="h-4 w-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              Okta SAML
            </button>
          </div>

          {/* Bottom account link */}
          <p className="text-center text-xs text-slate-500 font-medium">
            Don't have an audit account?{' '}
            <Link to="/signup" className="font-bold text-[#5B3DF5] hover:text-[#4a32c8] transition">
              Create Account
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
