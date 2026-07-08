import { useEffect, useCallback } from 'react'
import { Database, Robot, ArrowClockwise } from 'phosphor-react'
import { useStatus } from '../context/StatusContext'
import { fetchReadyStatus, getConfig } from '../api/client'
import StatusDot from '../components/StatusDot'
import ScrollReveal from '../components/ScrollReveal'
import ErrorState from '../components/ErrorState'

export default function SettingsPage() {
  const { state, setLoading, setConfig, setComponentHealth, setBothError } = useStatus()

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [config, ready] = await Promise.all([getConfig(), fetchReadyStatus()])
      setConfig(config)
      setComponentHealth(ready.response)
    } catch {
      setBothError('Unable to reach the backend server.')
    } finally {
      setLoading(false)
    }
  }, [setLoading, setConfig, setComponentHealth, setBothError])

  useEffect(() => {
    refresh()
  }, [refresh])

  return (
    <ScrollReveal>
      <div className="max-w-3xl mx-auto">
        <div className="mb-10">
          <h1 className="font-serif text-3xl tracking-[-0.03em] text-charcoal mb-2">
            Settings
          </h1>
          <p className="text-sm text-muted">
            System configuration and health status.
          </p>
        </div>

        {state.loading ? (
          <div className="space-y-4">
            {[0, 1].map((i) => (
              <div
                key={i}
                className="rounded-lg border border-border bg-surface p-6 animate-pulse"
              >
                <div className="h-4 bg-warm-bone rounded w-1/3 mb-4" />
                <div className="h-3 bg-warm-bone rounded w-1/2" />
              </div>
            ))}
          </div>
        ) : state.vectorStore.status === 'error' && !state.config ? (
          <ErrorState
            message="Unable to load settings"
            detail="Check that the backend server is running."
            onRetry={refresh}
          />
        ) : (
          <div className="grid gap-6">
            <div className="card-hover rounded-lg border border-border bg-surface p-6">
              <div className="flex items-center gap-3 mb-5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-warm-bone">
                  <Database size={18} className="text-charcoal" weight="bold" />
                </div>
                <h2 className="font-serif text-lg tracking-[-0.02em] text-charcoal">
                  Connectors
                </h2>
              </div>
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <span className="text-sm text-muted">Vector Store</span>
                  <span className="font-mono text-sm text-charcoal bg-warm-bone rounded px-2 py-0.5">
                    {state.config?.vector_store ?? '—'}
                  </span>
                </div>
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <span className="text-sm text-muted">LLM Provider</span>
                  <span className="font-mono text-sm text-charcoal bg-warm-bone rounded px-2 py-0.5">
                    {state.config?.llm_provider ?? '—'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted">Authentication</span>
                  <span className="font-mono text-sm text-charcoal bg-warm-bone rounded px-2 py-0.5">
                    {state.config?.auth_enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
              </div>
            </div>

            <div className="card-hover rounded-lg border border-border bg-surface p-6">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-warm-bone">
                    <Robot size={18} className="text-charcoal" weight="bold" />
                  </div>
                  <h2 className="font-serif text-lg tracking-[-0.02em] text-charcoal">
                    System Health
                  </h2>
                </div>
                <button
                  onClick={refresh}
                  className="flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs text-muted transition-colors hover:text-charcoal hover:bg-warm-bone cursor-pointer"
                >
                  <ArrowClockwise size={14} weight="bold" />
                  Refresh
                </button>
              </div>
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <span className="text-sm text-muted">Vector Store</span>
                  <StatusDot
                    status={state.vectorStore.status}
                    label={state.vectorStore.status === 'ok' ? 'Healthy' : (state.vectorStore.detail ?? 'Unknown')}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted">LLM</span>
                  <StatusDot
                    status={state.llm.status}
                    label={state.llm.status === 'ok' ? 'Reachable' : (state.llm.detail ?? 'Unknown')}
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </ScrollReveal>
  )
}
