import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

function formatDate(value) {
  return new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function UploadPage() {
  const pollTimer = useRef(null)
  const [uploads, setUploads] = useState([])
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')

  async function loadUploads() {
    try { setUploads(await api.uploads()) } catch (err) { if (err.status !== 401) setError(err.message) }
  }

  useEffect(() => {
    loadUploads()
    return () => clearTimeout(pollTimer.current)
  }, [])

  async function pollUpload(id) {
    try {
      const result = await api.uploadStatus(id)
      if (result.status === 'processed') {
        setStatus('success')
        loadUploads()
      } else if (result.status === 'failed') {
        setStatus('error')
        setError(result.error_message || 'Processing failed')
        loadUploads()
      } else {
        pollTimer.current = setTimeout(() => pollUpload(id), 1500)
      }
    } catch (err) {
      setStatus('error')
      setError(err.message || 'Could not check upload status.')
    }
  }

  async function submit(event) {
    event.preventDefault()
    if (!file) return
    setStatus('processing')
    setError('')
    try {
      const result = await api.upload(file)
      pollUpload(result.id)
    } catch (err) {
      setStatus('error')
      setError(err.message)
    }
  }

  function selectFile(candidate) {
    if (!candidate) return
    if (!candidate.name.toLowerCase().endsWith('.csv')) {
      setError('Please choose a CSV file.')
      setStatus('error')
      return
    }
    setFile(candidate)
    setStatus('idle')
    setError('')
  }

  return <div className="content-page narrow">
    <header className="page-heading"><span className="eyebrow">New analysis</span><h1>Upload your transactions</h1><p>We’ll scan your CSV for recurring charges and suspicious price changes.</p></header>
    <div className="upload-layout">
      <section className="panel upload-panel">
        <form onSubmit={submit}>
          <label className={`drop-zone ${dragging ? 'dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); selectFile(event.dataTransfer.files[0]) }}>
            <input type="file" accept=".csv,text/csv" onChange={(event) => selectFile(event.target.files[0])} />
            <span className="upload-symbol">↑</span>
            <strong>{file ? file.name : 'Drop your CSV here'}</strong>
            <span>{file ? `${(file.size / 1024).toFixed(1)} KB · Click to replace` : 'or click to browse · maximum 5 MB'}</span>
          </label>
          <button className="primary-button full" disabled={!file || status === 'processing'}>{status === 'processing' ? <><span className="button-spinner"/> Analysing transactions…</> : 'Analyse transactions'}</button>
        </form>
        {status === 'success' && <div className="alert success">Analysis complete. <Link to="/dashboard">View your subscriptions →</Link></div>}
        {status === 'error' && <div className="alert error" role="alert">{error}</div>}
      </section>
      <aside className="format-card">
        <h2>CSV format</h2>
        <p>Include date, description and amount columns. Common alternatives like Memo, Debit, or Transaction Date work too.</p>
        <pre>Date,Description,Amount{`\n`}2026-01-05,Netflix,15.99{`\n`}2026-01-12,Spotify,9.99</pre>
        <p className="privacy-note"><strong>Your data stays yours.</strong> Files are processed only for your account.</p>
      </aside>
    </div>
    <section className="recent-section">
      <div className="section-heading"><div><h2>Recent uploads</h2><p>Your latest transaction analyses</p></div><span className="count-badge">{uploads.length}</span></div>
      {uploads.length ? <div className="upload-list">{uploads.map((upload) => <div className="upload-row" key={upload.id}><span className="file-icon">CSV</span><div><strong>{upload.filename}</strong><span>{formatDate(upload.uploaded_at)} · {upload.imported_rows ?? 0} transactions imported</span></div><span className={`status-badge ${upload.status}`}>{upload.status}</span></div>)}</div> : <div className="empty-inline">No uploads yet. Your first analysis will appear here.</div>}
    </section>
  </div>
}
