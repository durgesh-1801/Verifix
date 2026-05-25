import { BrowserRouter, Routes, Route, Outlet, useNavigate } from 'react-router-dom'
import { Navbar } from './components/layout/Navbar'
import { Footer } from './components/layout/Footer'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Dashboard from './pages/Dashboard'
import Workspace from './pages/Workspace'
import Reports from './pages/Reports'
import Vendors from './pages/Vendors'
import AuditLogs from './pages/AuditLogs'
import RootLayout from './components/layout/RootLayout'
import { useCallback } from 'react'

// Layout for the public landing page (replicates the original App structure)
function LandingLayout() {
  const navigate = useNavigate()

  const handleOpenWorkspace = useCallback(() => {
    const el = document.getElementById('workspace')
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' })
    } else {
      navigate('/workspace')
    }
  }, [navigate])

  return (
    <div className="min-h-screen bg-[#F9FAFB] text-[#1A1C2E] flex flex-col justify-between">
      <div>
        <Navbar onOpenWorkspace={handleOpenWorkspace} />
        <Outlet />
      </div>
      <Footer />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Full-screen auth pages */}
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />

        {/* Public Landing View */}
        <Route path="/" element={<LandingLayout />}>
          <Route index element={<Landing />} />
        </Route>

        {/* Premium SaaS Application Shell */}
        <Route path="/" element={<RootLayout />}>
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="workspace" element={<Workspace />} />
          <Route path="reports" element={<Reports />} />
          <Route path="vendors" element={<Vendors />} />
          <Route path="logs" element={<AuditLogs />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
