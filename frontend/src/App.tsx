import { useCallback, useMemo, useState } from 'react'
import { downloadPdfReport, verifyInvoice } from './api'
import type { VerifySuccessResponse } from './types'
import { sumRupeeDifference, verificationStatusFrom } from './totals'
import { scrollToId } from './lib/scroll'
import { Navbar } from './components/layout/Navbar'
import { Footer } from './components/layout/Footer'
import { HeroSection } from './components/home/HeroSection'
import { PipelineBar } from './components/home/PipelineBar'
import { ActivitySection } from './components/home/ActivitySection'
import { FinanceOSPanel } from './components/home/FinanceOSPanel'
import { discrepanciesToRows } from './components/home/VerificationLedger'
import { WorkspaceSection } from './components/workspace/WorkspaceSection'

export default function App() {
  const [invoiceFile, setInvoiceFile] = useState<File | null>(null)
  const [poFile, setPoFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [banner, setBanner] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [result, setResult] = useState<VerifySuccessResponse | null>(null)
  const [pdfLoading, setPdfLoading] = useState(false)

  const openWorkspace = useCallback(() => scrollToId('workspace'), [])

  const totals = useMemo(() => {
    if (!result) return null
    const diff = sumRupeeDifference(result.discrepancies)
    const status = verificationStatusFrom(result.discrepancies)
    return {
      totalIssues: result.discrepancies.length,
      totalRupeeDifference: diff,
      status,
    }
  }, [result])

  const flaggedCount = totals?.totalIssues ?? 2
  const ledgerRows = result ? discrepanciesToRows(result.discrepancies) : undefined

  const runVerify = useCallback(async () => {
    setBanner(null)
    setResult(null)
    if (!invoiceFile || !poFile) {
      setBanner({ type: 'error', message: 'Please choose both an invoice file and a PO file (.pdf or .txt).' })
      openWorkspace()
      return
    }
    setLoading(true)
    openWorkspace()
    try {
      const out = await verifyInvoice(invoiceFile, poFile)
      if (!out.ok) {
        setBanner({
          type: 'error',
          message: out.body.error || `Verification failed (${out.status}).`,
        })
        return
      }
      setResult(out.data)
      setBanner({
        type: 'success',
        message:
          out.data.discrepancies.length > 0
            ? 'Verification complete — review discrepancies below.'
            : 'Verification complete — no discrepancies detected.',
      })
    } catch {
      setBanner({
        type: 'error',
        message: 'Network error — is the Flask server running (port 5000) or is VITE_API_BASE_URL correct?',
      })
    } finally {
      setLoading(false)
    }
  }, [invoiceFile, poFile, openWorkspace])

  const onDownloadPdf = useCallback(async () => {
    if (!result || !totals) return
    setPdfLoading(true)
    setBanner(null)
    try {
      await downloadPdfReport({
        status: totals.status,
        totalIssues: totals.totalIssues,
        totalRupeeDifference: totals.totalRupeeDifference,
        discrepancies: result.discrepancies,
      })
      setBanner({ type: 'success', message: 'PDF report downloaded.' })
    } catch {
      setBanner({ type: 'error', message: 'Could not generate the PDF. Try again.' })
    } finally {
      setPdfLoading(false)
    }
  }, [result, totals])

  const savings = totals ? `$${(Number(totals.totalRupeeDifference) / 1000).toFixed(1)}k` : '$4.2k'

  const accuracy =
    totals && totals.totalIssues === 0 ? '99.8%' : totals ? `${Math.max(94, 99.8 - totals.totalIssues).toFixed(1)}%` : '99.8%'

  return (
    <div className="min-h-screen bg-[#F9FAFB] text-[#1A1C2E]">
      <Navbar onOpenWorkspace={openWorkspace} />

      <main id="top" className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <HeroSection
          onOpenWorkspace={openWorkspace}
          onTryDemo={openWorkspace}
          onRunAudit={runVerify}
          flaggedCount={flaggedCount}
          ledgerRows={ledgerRows}
        />

        <PipelineBar />

        <ActivitySection loading={loading} issueCount={totals?.totalIssues ?? null} />

        <FinanceOSPanel
          onConfigure={openWorkspace}
          onDemo={openWorkspace}
          invoiceLabel={invoiceFile?.name?.toUpperCase() ?? 'INV_JAN_STRP.pdf'}
          validated={Boolean(totals && totals.totalIssues === 0)}
          savings={savings}
          accuracy={accuracy}
        />

        <WorkspaceSection
          invoiceFile={invoiceFile}
          poFile={poFile}
          onInvoiceFile={setInvoiceFile}
          onPoFile={setPoFile}
          loading={loading}
          banner={banner}
          result={result}
          totals={totals}
          pdfLoading={pdfLoading}
          onVerify={runVerify}
          onClear={() => {
            setInvoiceFile(null)
            setPoFile(null)
            setResult(null)
            setBanner(null)
          }}
          onDownloadPdf={onDownloadPdf}
        />
      </main>

      <Footer />
    </div>
  )
}
