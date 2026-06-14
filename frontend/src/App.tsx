import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Layout } from './components/Layout'
import { Library } from './pages/Library'
import { Settings } from './pages/Settings'
import { Login } from './pages/Login'

const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

function AuthGuard({ children }: { children: React.ReactNode }) {
  const [checked, setChecked] = useState(false)
  const [authed, setAuthed] = useState(false)

  useEffect(() => {
    fetch(`${BASE}/auth/me`, { credentials: 'include' })
      .then(r => {
        setAuthed(r.ok)
        setChecked(true)
      })
      .catch(() => {
        setAuthed(false)
        setChecked(true)
      })
  }, [])

  if (!checked) return null
  if (!authed) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<AuthGuard><Layout /></AuthGuard>}>
          <Route path="/" element={<Navigate to="/library" replace />} />
          <Route path="/library" element={<Library />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
