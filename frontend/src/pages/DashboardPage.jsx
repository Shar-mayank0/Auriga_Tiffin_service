import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import * as subscriptionsApi from '../api/subscriptions.js'
import StatusBadge from '../components/StatusBadge.jsx'
import { formatDate } from '../utils/dateHelpers.js'

export default function DashboardPage() {
  const [subscription, setSubscription] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    subscriptionsApi.getMySubscription().then(({ data }) => setSubscription(data)).catch((requestError) => {
      if (requestError.response?.status !== 404) setError('Unable to load your subscription.')
    }).finally(() => setLoading(false))
  }, [])
  if (loading) return <p>Loading...</p>
  if (error) return <p className="error">{error}</p>
  if (!subscription) return <section className="empty-state"><h1>No active plan yet</h1><p>Choose a plan to start receiving your tiffin.</p><Link className="button" to="/subscribe">View plans</Link></section>
  return (
    <section>
      <div className="page-heading"><div><p className="eyebrow">Your service</p><h1>Dashboard</h1></div><StatusBadge status={subscription.status} /></div>
      <div className="summary-grid">
        <div className="summary"><span>Current plan</span><strong>{subscription.plan?.name}</strong><p>₹{subscription.plan?.monthly_price} per month</p></div>
        <div className="summary"><span>Started</span><strong>{formatDate(subscription.start_date)}</strong><p>Pause or resume any time</p></div>
      </div>
      <div className="actions"><Link className="button" to="/pause">Manage pause</Link><Link className="button secondary" to="/billing">View billing</Link></div>
    </section>
  )
}