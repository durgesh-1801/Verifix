import { Link, useNavigate } from 'react-router-dom'
import { useState } from 'react'

export default function Signup() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [agree, setAgree] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // Simulated registration bypass for the prototype
    navigate('/dashboard')
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-12 bg-white font-sans selection:bg-violet-100">
      
      {/* LEFT PANEL: Branding & Visual Bullet list (5 columns) */}
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
              Secure Pipeline Setup
            </span>
          </div>

          {/* Slogan */}
          <div className="space-y-4 pt-4">
            <h1 className="text-3xl xl:text-4xl font-extrabold leading-[1.15] tracking-tight">
              Smarter reconciliation,{' '}
              <span className="bg-gradient-to-r from-[#818CF8] to-[#9333EA] bg-clip-text text-transparent">
                zero manual entries.
              </span>
            </h1>
            <p className="text-xs xl:text-sm text-slate-400 leading-relaxed max-w-sm">
              Define custom matching pipelines, detect inconsistencies instantly, and synchronize verified invoice ledgers with your existing enterprise ERP systems.
            </p>
          </div>

          {/* Interactive Checkmark Benefit List */}
          <div className="pt-6">
            <ul className="space-y-3.5">
              {[
                'Enterprise-Grade OCR Parsing Hub',
                'Three-Way PO-Invoice Reconciliation System',
                'Realtime Discrepancy Tracking Ledger',
                'Automated AI-Report Audits & Insights',
              ].map((bullet, i) => (
                <li key={i} className="flex items-center gap-3 text-xs text-slate-300">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#5B3DF5]/20 text-[#818CF8]">
                    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  </span>
                  {bullet}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Bottom stats and compliance badges */}
        <div className="relative z-10 space-y-6 pt-10 border-t border-white/5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-lg xl:text-xl font-bold tracking-tight">99.8%</p>
              <p className="text-[9px] font-bold tracking-wider text-slate-400 uppercase mt-0.5">Extraction Precision</p>
            </div>
            <div>
              <p className="text-lg xl:text-xl font-bold tracking-tight">SOC2</p>
              <p className="text-[9px] font-bold tracking-wider text-slate-400 uppercase mt-0.5">Compliance Audited</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 text-[8px] font-bold tracking-wider text-slate-500">
            <span className="border border-white/5 rounded px-1.5 py-0.5">SOC2 TYPE II</span>
            <span className="border border-white/5 rounded px-1.5 py-0.5">AUDIT TRAILS</span>
            <span className="border border-white/5 rounded px-1.5 py-0.5">ERP INTEGRATED</span>
          </div>
        </div>
      </div>

      {/* RIGHT PANEL: Sign Up Form (7 columns) */}
      <div className="lg:col-span-7 flex flex-col justify-center items-center px-6 py-12 sm:px-12 md:px-20 lg:px-16 xl:px-24">
        <div className="w-full max-w-md space-y-8">
          
          {/* Mobile logo */}
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
              Create Audit Account
            </h2>
            <p className="mt-2 text-xs sm:text-sm text-slate-500">
              Deploy your first ledger pipeline in 2 minutes. No card details required.
            </p>
          </div>

          {/* Form */}
          <form className="space-y-4" onSubmit={handleSubmit}>
            
            {/* Full Name */}
            <div className="space-y-1">
              <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Full Name
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-3 flex items-center text-slate-400">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                    <circle cx="8.5" cy="7" r="4" />
                  </svg>
                </span>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Alex Rivera"
                  className="w-full rounded-xl border border-slate-200 py-3 pl-10 pr-4 text-xs text-[#1A1C2E] placeholder-slate-400 outline-none transition focus:border-violet-500 focus:bg-white shadow-sm"
                />
              </div>
            </div>

            {/* Work Email */}
            <div className="space-y-1">
              <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Work Email
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

            {/* Password Row */}
            <div className="grid grid-cols-2 gap-3">
              {/* Password */}
              <div className="space-y-1">
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  Password
                </label>
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
                    placeholder="••••••"
                    className="w-full rounded-xl border border-slate-200 py-3 pl-10 pr-4 text-xs text-[#1A1C2E] placeholder-slate-400 outline-none transition focus:border-violet-500 focus:bg-white shadow-sm"
                  />
                </div>
              </div>

              {/* Confirm Password */}
              <div className="space-y-1">
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  Confirm
                </label>
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
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••"
                    className="w-full rounded-xl border border-slate-200 py-3 pl-10 pr-4 text-xs text-[#1A1C2E] placeholder-slate-400 outline-none transition focus:border-violet-500 focus:bg-white shadow-sm"
                  />
                </div>
              </div>
            </div>

            {/* Terms checkbox */}
            <div className="flex items-start pt-1">
              <input
                id="agree"
                type="checkbox"
                required
                checked={agree}
                onChange={(e) => setAgree(e.target.checked)}
                className="h-4 w-4 mt-0.5 rounded border-slate-300 text-violet-600 focus:ring-violet-500 cursor-pointer accent-violet-600"
              />
              <label htmlFor="agree" className="ml-2 text-[10px] text-slate-500 font-semibold cursor-pointer leading-relaxed">
                I agree to the <span className="text-[#5B3DF5] cursor-pointer">Secure Auditing Terms, SLA</span> and <span className="text-[#5B3DF5] cursor-pointer">Privacy Guidelines</span>.
              </label>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#5B3DF5] py-3 text-xs sm:text-sm font-semibold text-white shadow-md shadow-violet-600/20 hover:bg-[#4a32c8] transition cursor-pointer"
            >
              Create Account & Enter
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </button>
          </form>

          {/* Bottom account link */}
          <p className="text-center text-xs text-slate-500 font-medium">
            Already have an audit workspace?{' '}
            <Link to="/login" className="font-bold text-[#5B3DF5] hover:text-[#4a32c8] transition">
              Sign In
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
