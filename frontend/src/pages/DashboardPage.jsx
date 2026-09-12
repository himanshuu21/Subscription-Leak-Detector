import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

const money = (value) => Number.isFinite(Number(value)) ? Number(value) : 0

function SubscriptionCard({ subscription, currency, onDecision }) {
  const confidence = Math.round(subscription.confidence_score * 100)
  return <article className="subscription-card">
    <div className="subscription-main">
      <div className="merchant-title"><div className="merchant-avatar">{subscription.merchant_name.slice(0, 1).toUpperCase()}</div><div><h3>{subscription.merchant_name}</h3><div className="tag-row"><span className="tag neutral">{subscription.cycle_label}</span>{subscription.decision === 'cancel' && <span className="tag warning">Cancellation planned</span>}{subscription.price_hike_detected && <span className="tag danger" title="Price hike detected. Check transaction history.">↑ Price hike</span>}</div></div></div>
      <div className="cost-row"><span><small>Current payment</small><strong>{currency}{money(subscription.current_amount).toFixed(2)}</strong></span><span><small>Annual cost</small><strong>{currency}{money(subscription.annual_cost).toFixed(2)}</strong></span></div>
      <div className="confidence-row"><span>Detection confidence</span><div className="confidence-track"><i className={confidence >= 80 ? 'high' : confidence >= 50 ? 'medium' : 'low'} style={{ width: `${confidence}%` }} /></div><strong>{confidence}%</strong></div>
    </div>
    <div className="card-actions"><button className={subscription.decision === 'keep' ? 'selected keep' : ''} onClick={() => onDecision(subscription, 'keep')}>Keep</button><button className={subscription.decision === 'cancel' ? 'selected cancel' : ''} title="Records a plan only; it does not contact the merchant" onClick={() => onDecision(subscription, 'cancel')}>{subscription.decision === 'cancel' ? 'Undo plan' : 'Mark to cancel'}</button></div>
  </article>
}

function SpendBreakdown({ subscriptions, currency }) {
  const rows = [...subscriptions].sort((a, b) => money(b.annual_cost) - money(a.annual_cost))
  const total = rows.reduce((sum, item) => sum + money(item.annual_cost), 0)
  return <aside className="panel breakdown" id="spend-breakdown"><h2>Annual spend</h2><div className="big-number"><span>Total projected</span><strong>{currency}{total.toFixed(2)}</strong><small>per year</small></div>{rows.length ? <div className="breakdown-list">{rows.map((item) => { const share = total ? money(item.annual_cost) / total * 100 : 0; return <div key={item.id}><div><span title={item.merchant_name}>{item.merchant_name}</span><strong>{currency}{money(item.annual_cost).toFixed(2)}</strong></div><div className="spend-track"><i style={{ width: `${Math.max(2, share)}%` }}/></div><small>{share.toFixed(1)}%</small></div> })}</div> : <p className="muted">No subscription spend to display.</p>}</aside>
}

export default function DashboardPage({ currency }) {
  const [subscriptions, setSubscriptions] = useState([])
  const [uploads, setUploads] = useState([])
  const [savings, setSavings] = useState({ annual_savings: 0, marked_for_cancellation: 0 })
  const [uploadId, setUploadId] = useState('')
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => { api.uploads().then(setUploads).catch((err) => setError(err.message)) }, [])
  useEffect(() => {
    setLoading(true)
    Promise.all([api.subscriptions(uploadId), api.savings()]).then(([items, summary]) => { setSubscriptions(items); setSavings(summary); setError('') }).catch((err) => setError(err.message)).finally(() => setLoading(false))
  }, [uploadId])

  const visible = useMemo(() => subscriptions.filter((item) => filter === 'all' || (filter === 'high' ? item.confidence_score >= .8 : item.confidence_score >= .5)), [subscriptions, filter])
  const annual = visible.reduce((sum, item) => sum + money(item.annual_cost), 0)

  async function updateDecision(subscription, decision) {
    const next = subscription.decision === decision ? 'undecided' : decision
    try {
      const updated = await api.updateDecision(subscription.id, next)
      setSubscriptions((items) => items.map((item) => item.id === updated.id ? updated : item))
      setSavings(await api.savings())
    } catch (err) { setError(err.message) }
  }

  return <div className="content-page">
    <header className="dashboard-heading"><div><span className="eyebrow">Subscription overview</span><h1>Recurring spend, made visible.</h1><p>Review what we found and plan where to cut back.</p></div><Link className="primary-button" to="/upload-page">+ Analyse another CSV</Link></header>
    <section className="metrics-grid"><div className="metric-card"><span>Detected subscriptions</span><strong>{visible.length}</strong><small>across selected uploads</small></div><div className="metric-card"><span>Projected annual spend</span><strong>{currency}{annual.toFixed(2)}</strong><small>{currency}{(annual / 12).toFixed(2)} monthly average</small></div><div className="metric-card accent"><span>Planned annual savings</span><strong>{currency}{money(savings.annual_savings).toFixed(2)}</strong><small>{savings.marked_for_cancellation ?? savings.cancelled_subscriptions ?? 0} marked to cancel</small></div></section>
    <div className="dashboard-toolbar"><div><select aria-label="Select upload" value={uploadId} onChange={(event) => setUploadId(event.target.value)}><option value="">All uploads</option>{uploads.map((upload) => <option key={upload.id} value={upload.id}>{upload.filename} ({new Date(upload.uploaded_at).toLocaleDateString()})</option>)}</select><select aria-label="Filter by confidence" value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All confidence levels</option><option value="high">High confidence (80%+)</option><option value="medium">Medium confidence (50%+)</option></select></div><p><strong>Planning only:</strong> marking a subscription does not contact the merchant.</p></div>
    {error && <div className="alert error" role="alert">{error}</div>}
    <div className="dashboard-layout"><section className="subscription-list">{loading ? <div className="panel loading-panel"><span className="button-spinner dark"/> Loading subscriptions…</div> : visible.length ? visible.map((item) => <SubscriptionCard key={item.id} subscription={item} currency={currency} onDecision={updateDecision} />) : <div className="panel empty-state"><span className="empty-icon">◎</span><h2>No subscriptions found</h2><p>Upload a transaction CSV to find your recurring payments.</p><Link className="primary-button" to="/upload-page">Upload a CSV</Link></div>}</section><SpendBreakdown subscriptions={visible} currency={currency} /></div>
  </div>
}
