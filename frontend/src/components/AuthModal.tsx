import { useState, type FormEvent } from 'react'
import { Key } from 'phosphor-react'

interface Props {
  onSubmit: (key: string) => void
  error?: string
}

export default function AuthModal({ onSubmit, error }: Props) {
  const [value, setValue] = useState('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (value.trim()) onSubmit(value.trim())
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-canvas/80 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-lg border border-border bg-surface p-8">
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
