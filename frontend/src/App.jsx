import { useEffect, useState } from 'react'
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { api } from './api'
import AuthPage from './pages/AuthPage'
import DashboardPage from './pages/DashboardPage'
import UploadPage from './pages/UploadPage'

function Icon({ name, size = 20 }) {
  const paths = {
    upload: <><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M20 15v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-4"/></>,
    chart: <><path d="M3 3v18h18"/><path d="m7 16 4-5 4 3 4-7"/></>,
    logout: <><path d="M10 17l5-5-5-5"/><path d="M15 12H3"/><path d="M21 19V5a2 2 0 0 0-2-2h-6"/></>,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}

function Layout({ children, authenticated, onLogout }) {
  const location = useLocation()
  return <div className="app-shell">
    <header className="navbar">
      <Link to={authenticated ? '/dashboard' : '/'} className="brand">
        <span className="brand-mark">SL</span>
        <span>Subscription Leak Detector</span>
      </Link>
      {authenticated && <nav aria-label="Main navigation">
        <Link className={location.pathname === '/upload-page' ? 'active' : ''} to="/upload-page"><Icon name="upload"/> Upload</Link>
        <Link className={location.pathname === '/dashboard' ? 'active' : ''} to="/dashboard"><Icon name="chart"/> Dashboard</Link>
        <button type="button" onClick={onLogout}><Icon name="logout"/> Logout</button>
      </nav>}
    </header>
    <main>{children}</main>
  </div>
}

function ProtectedRoute({ authState, children }) {
  if (authState === 'checking') return <div className="page-loader" aria-label="Checking session"><span /></div>
  return authState === 'authenticated' ? children : <Navigate to="/" replace />
}

export default function App() {
  const navigate = useNavigate()
  const [authState, setAuthState] = useState('checking')
  const [config, setConfig] = useState({ currency: '$', google_oauth_enabled: false })

  useEffect(() => {
    Promise.allSettled([api.config(), api.checkSession()]).then(([configResult, sessionResult]) => {
      if (configResult.status === 'fulfilled') setConfig(configResult.value)
      setAuthState(sessionResult.status === 'fulfilled' ? 'authenticated' : 'anonymous')
    })
  }, [])

  async function logout() {
    try { await api.logout() } finally {
      setAuthState('anonymous')
      navigate('/')
    }
  }

  const authenticated = authState === 'authenticated'
  return <Layout authenticated={authenticated} onLogout={logout}>
    <Routes>
      <Route path="/" element={authenticated ? <Navigate to="/dashboard" replace /> : <AuthPage config={config} onAuthenticated={() => setAuthState('authenticated')} />} />
      <Route path="/upload-page" element={<ProtectedRoute authState={authState}><UploadPage /></ProtectedRoute>} />
      <Route path="/dashboard" element={<ProtectedRoute authState={authState}><DashboardPage currency={config.currency} /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to={authenticated ? '/dashboard' : '/'} replace />} />
    </Routes>
  </Layout>
}
