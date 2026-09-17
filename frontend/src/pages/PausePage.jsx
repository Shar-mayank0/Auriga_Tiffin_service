import { useEffect, useState } from 'react'
import * as pausesApi from '../api/pauses.js'
import PauseForm from '../components/PauseForm.jsx'
import { formatDate, today } from '../utils/dateHelpers.js'

export default function PausePage() {
  const [pauses, setPauses] = useState([]); const [error, setError] = useState(''); const [loading, setLoading] = useState(true)
  const load = () => pausesApi.getMyPauses().then(({ data }) => setPauses(data)).catch((requestError) => { if (requestError.response?.status !== 404) setError('Unable to load pause history.') }).finally(() => setLoading(false))
  useEffect(load, [])
  const activePause = pauses.find((pause) => !pause.end_date)
  const create = async (data) => { setError(''); try { await pausesApi.createPause({ ...data, end_date: data.end_date || null }); await load() } catch (requestError) { setError(Object.values(requestError.response?.data || {}).flat().join(' ') || 'Unable to pause service.') } }
  const resume = async () => { setError(''); try { await pausesApi.resumePause(activePause.id, today()); await load() } catch { setError('Unable to resume service.') } }
  if (loading) return <p>Loading...</p>
  return <section className="narrow"><p className="eyebrow">Flexible service</p><h1>{activePause ? 'Your service is paused' : 'Pause your service'}</h1>{error && <p className="error">{error}</p>}{activePause ? <><p>Paused from {formatDate(activePause.start_date)}{activePause.end_date ? ` until ${formatDate(activePause.end_date)}` : ' with no end date'}.</p><button className="button" onClick={resume}>Resume service</button></> : <PauseForm onSubmit={create} />}{pauses.length > 0 && <div className="history"><h2>Pause history</h2>{pauses.map((pause) => <p key={pause.id}>{formatDate(pause.start_date)} to {pause.end_date ? formatDate(pause.end_date) : 'ongoing'}</p>)}</div>}</section>
}