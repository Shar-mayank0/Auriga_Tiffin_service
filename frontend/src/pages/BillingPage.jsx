import { useEffect, useState } from 'react'
import * as billingApi from '../api/billing.js'
import BillCard from '../components/BillCard.jsx'

export default function BillingPage() {
  const [bills, setBills] = useState([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('')
  useEffect(() => { billingApi.getMyBills().then(({ data }) => setBills(data)).catch(() => setError('Unable to load billing history.')).finally(() => setLoading(false)) }, [])
  if (loading) return <p>Loading...</p>
  return <section><p className="eyebrow">Your records</p><h1>Billing history</h1>{error && <p className="error">{error}</p>}{bills.length ? <div className="bill-list">{bills.map((bill) => <BillCard key={bill.id} bill={bill} />)}</div> : <p className="muted">No bills have been generated yet.</p>}</section>
}