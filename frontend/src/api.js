async function request(path, options = {}) {
  const response = await fetch(path, { credentials: 'same-origin', ...options })
  if (!response.ok) {
    let detail
    try {
      const body = await response.json()
      detail = Array.isArray(body.detail)
        ? body.detail.map((item) => item.msg).join(', ')
        : body.detail
    } catch {
      detail = null
    }
    const error = new Error(detail || `Request failed (${response.status})`)
    error.status = response.status
    throw error
  }
  return response.status === 204 ? null : response.json()
}

export const api = {
  config: () => request('/api/config'),
  checkSession: () => request('/api/uploads?limit=1'),
  authenticate: (mode, credentials) => request(`/api/auth/${mode}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  uploads: () => request('/api/uploads'),
  upload: (file) => {
    const data = new FormData()
    data.append('file', file)
    return request('/api/upload', { method: 'POST', body: data })
  },
  uploadStatus: (id) => request(`/api/uploads/${id}/status`),
  subscriptions: (uploadId = '') => request(`/api/subscriptions${uploadId ? `?upload_id=${uploadId}` : ''}`),
  savings: () => request('/api/subscriptions/savings'),
  updateDecision: (id, decision) => request(`/api/subscriptions/${id}/decision`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision }),
  }),
}
