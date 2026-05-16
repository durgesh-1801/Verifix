export type Discrepancy = {
  item: string
  field: string
  invoice_value: string
  po_value: string
  issue: string
  difference?: string
}

export type VerifySuccessResponse = {
  invoice_text: string
  po_text: string
  discrepancies: Discrepancy[]
  summary: string
}

export type VerifyErrorBody = {
  error: string
  discrepancies?: Discrepancy[]
}
