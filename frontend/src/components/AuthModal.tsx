import { useState, useEffect, type FormEvent } from 'react'
import { Key, X } from 'phosphor-react'

interface Props {
  onSubmit: (key: string) => void
  onDismiss?: () => void
  error?: string
}

export default function AuthModal({ onSubmit, onDismiss, error }: Props) {
  const [value, setValue] = useState('')

  // Dismiss on ESC key press
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && onDismiss) {
        onDismiss()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onDismiss])

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (value.trim()) onSubmit(value.trim())
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-canvas/80 backdrop-blur-sm"
      onClick={(e) => {
        // Dismiss when clicking the backdrop
        if (e.target === e.currentTarget && onDismiss) onDismiss()
      }}
    >
      <div className="w-full max-w-sm rounded-lg border border-border bg-surface p-8 relative">
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Close auth modal"
            className="absolute top-4 right-4 flex items-center justify-center rounded p-1 text-muted transition-colors hover:text-charcoal hover:bg-warm-bone cursor-pointer"
          >
            <X size={16} weight="bold" />
          </button>
        )}
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-pale-yellow-bg">
            <Key size={20} className="text-pale-yellow-text" weight="bold" />
          </div>
          <div>
            <h2 className="font-serif text-lg tracking-[-0.02em] text-charcoal">
              API Key Required
            </h2>
            <p className="text-xs text-muted mt-0.5">
              Authentication is enabled on this server.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-muted uppercase tracking-[0.05em] mb-1.5">
              API Key
            </label>
            <input
              type="password"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Enter your API key"
              className="w-full rounded border border-border bg-warm-bone px-3 py-2 text-sm text-charcoal placeholder:text-muted/50 outline-none transition-colors focus:border-charcoal"
              autoFocus
            />
          </div>

          {error && (
            <p className="text-xs text-pale-red-text bg-pale-red-bg rounded px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={!value.trim()}
            className="w-full rounded bg-charcoal px-4 py-2 text-sm text-white transition-all duration-200 hover:bg-[#333333] active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            Submit
          </button>
        </form>
      </div>
    </div>
  )
}
