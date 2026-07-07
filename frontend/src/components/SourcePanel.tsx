import { useState } from 'react'
import { CaretDown, CaretRight, FileText } from 'phosphor-react'
import type { SourceChunk } from '../api/client'

interface Props {
  sources: SourceChunk[]
  cached?: boolean
}

export default function SourcePanel({ sources, cached }: Props) {
  const [open, setOpen] = useState(false)

  if (!sources || sources.length === 0) return null

  return (
    <div className="mt-4 border-t border-border pt-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-xs text-muted uppercase tracking-[0.05em] transition-colors hover:text-charcoal cursor-pointer"
      >
        {open ? <CaretDown size={12} weight="bold" /> : <CaretRight size={12} weight="bold" />}
        {sources.length} source{sources.length > 1 ? 's' : ''}
        {cached && (
          <span className="ml-1 rounded-full bg-pale-yellow-bg px-2 py-0.5 text-[10px] font-mono text-pale-yellow-text uppercase tracking-[0.05em]">
            cached
          </span>
        )}
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {sources.map((source, i) => (
            <div
              key={i}
              className="rounded border border-border bg-surface p-3"
              style={{ animationDelay: `${i * 80}ms` }}
            >
              <div className="flex items-center gap-2 mb-2">
                <FileText size={14} className="text-muted shrink-0" weight="bold" />
                <span className="font-mono text-xs text-charcoal truncate">
                  {source.source}
                </span>
                {source.page != null && (
                  <span className="font-mono text-[10px] text-muted ml-auto">
                    p. {source.page}
                  </span>
                )}
              </div>
              <p className="font-mono text-xs text-muted leading-relaxed line-clamp-3">
                {source.text}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
