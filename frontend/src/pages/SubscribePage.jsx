import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import * as plansApi from '../api/plans.js'
import * as subscriptionsApi from '../api/subscriptions.js'
import PlanCard from '../components/PlanCard.jsx'
import { today } from '../utils/dateHelpers.js'

export default function SubscribePage() {
  const [plans, setPlans] = useState([]); const [selected, setSelected] = useState(null); const [error, setError] = useState(''); const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  useEffect(() => { plansApi.listPlans().then(({ data }) => setPlans(data)).catch(() => setError('Unable to load plans.')) }, [])
  const submit = async () => {
    if (!selected) return setError('Choose a plan first.')
    setLoading(true); setError('')
    try { await subscriptionsApi.subscribe(selected, today()); navigate('/dashboard') } catch (requestError) { setError(Object.values(requestError.response?.data || {}).flat().join(' ') || 'Unable to start your subscription.') } finally { setLoading(false) }
  }
  return <section><p className="eyebrow">Find your fit</p><h1>Choose a plan</h1>{error && <p className="error">{error}</p>}<div className="plan-list">{plans.map((plan) => <PlanCard key={plan.id} plan={plan} selected={selected === plan.id} onSelect={setSelected} />)}</div><button className="button" disabled={loading || !selected} onClick={submit}>{loading ? 'Starting...' : 'Confirm plan'}</button></section>
}