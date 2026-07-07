import SourcePanel from './SourcePanel'

interface Props {
  role: 'user' | 'assistant'
  content: string
  sources?: import('../api/client').SourceChunk[]
  cached?: boolean
  error?: string
  isStreaming?: boolean
}

export default function MessageBubble({ role, content, sources, cached, error, isStreaming }: Props) {
  if (role === 'user') {
    return (
      <div className="flex justify-end mb-6">
        <div className="max-w-[75%] rounded-lg bg-charcoal px-4 py-3">
          <p className="text-white text-sm leading-relaxed">{content}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex mb-6">
      <div className="max-w-[80%]">
        {error ? (
          <div className="rounded-lg border border-pale-red-bg bg-pale-red-bg/30 px-4 py-3">
            <p className="text-sm text-pale-red-text">{error}</p>
          </div>
        ) : (
          <div className="rounded-lg border border-border bg-surface px-4 py-3">
            <p className="text-sm text-charcoal leading-relaxed whitespace-pre-wrap">
              {content}
              {isStreaming && <span className="inline-block w-1.5 h-4 bg-charcoal/40 ml-0.5 animate-pulse" />}
            </p>
            {sources && sources.length > 0 && <SourcePanel sources={sources} cached={cached} />}
          </div>
        )}
      </div>
    </div>
  )
}
