import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { onAuthRequired, setApiKey } from './api/client'
import { ChatProvider } from './context/ChatContext'
import { DocumentProvider } from './context/DocumentContext'
import { StatusProvider } from './context/StatusContext'
import AppShell from './components/AppShell'
import AuthModal from './components/AuthModal'
import ChatPage from './pages/ChatPage'
import DocumentsPage from './pages/DocumentsPage'
import SettingsPage from './pages/SettingsPage'

export default function App() {
  const [authOpen, setAuthOpen] = useState(false)
  const [authError] = useState<string | null>(null)

  useEffect(() => {
    onAuthRequired(() => setAuthOpen(true))
  }, [])

  function handleAuthSubmit(key: string) {
    setApiKey(key)
    setAuthOpen(false)
  }

  return (
    <>
      {authOpen && (
        <AuthModal onSubmit={handleAuthSubmit} error={authError ?? undefined} />
      )}
      <BrowserRouter>
        <ChatProvider>
          <DocumentProvider>
            <StatusProvider>
              <AppShell>
                <Routes>
                  <Route path="/" element={<ChatPage />} />
                  <Route path="/documents" element={<DocumentsPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                </Routes>
              </AppShell>
            </StatusProvider>
          </DocumentProvider>
        </ChatProvider>
      </BrowserRouter>
    </>
  )
}
