import { useState, useRef, useEffect, type FormEvent } from 'react'
import { PaperPlaneRight } from 'phosphor-react'
import { useChat } from '../context/ChatContext'
import { postQuery, ApiError } from '../api/client'
import MessageBubble from '../components/MessageBubble'
import ErrorState from '../components/ErrorState'
import ScrollReveal from '../components/ScrollReveal'

export default function ChatPage() {
  const chat = useChat()
  const [input, setInput] = useState('')
  const [apiError, setApiError] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [chat.state.messages])

  async function handleSubmit(e?: FormEvent) {
    e?.preventDefault()
    const text = input.trim()
    if (!text || chat.state.isStreaming) return

    setInput('')
    setApiError(null)

    chat.addUserMessage(text)
    const assistantId = crypto.randomUUID()
    chat.addAssistantMessage(assistantId)
    chat.setStreaming(true)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      await postQuery(
        { query: text, session_id: chat.state.sessionId },
        (event) => {
          switch (event.type) {
            case 'token':
              chat.appendToken(assistantId, event.content)
              break
            case 'metadata':
              chat.setSources(assistantId, event.sources, event.cached)
              break
            case 'error':
              chat.setError(assistantId, event.detail)
              break
          }
        },
        controller.signal,
      )
    } catch (err) {
      if (err instanceof ApiError) {
        chat.setError(assistantId, err.message)
      } else if (err instanceof Error && err.name !== 'AbortError') {
        chat.setError(assistantId, 'Unable to reach the backend server.')
        setApiError('Unable to reach the backend server. Check that the API is running.')
      }
    } finally {
      chat.setStreaming(false)
      abortRef.current = null
    }
  }

  function handleRetry() {
    setApiError(null)
    chat.clearSession()
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      {apiError ? (
        <ErrorState
          message="Connection error"
          detail="Unable to reach the backend server. Check that the API is running and accessible."
          onRetry={handleRetry}
        />
      ) : chat.state.messages.length === 0 ? (
        <div className="flex flex-1 items-center justify-center">
          <ScrollReveal>
            <div className="text-center max-w-md">
              <h1 className="font-serif text-3xl tracking-[-0.03em] text-charcoal mb-3">
                Ask about your documents
              </h1>
              <p className="text-muted text-sm leading-relaxed">
                Connected to your RAG pipeline. Type a question to retrieve and generate answers from your indexed documents.
              </p>
            </div>
          </ScrollReveal>
        </div>
      ) : (
        <div ref={listRef} className="flex-1 overflow-y-auto px-1">
          <div className="max-w-3xl mx-auto pt-4">
            {chat.state.messages.map((msg, i) => (
              <ScrollReveal key={msg.id} delay={i * 40}>
                <MessageBubble
                  role={msg.role}
                  content={msg.content}
                  sources={msg.sources}
                  cached={msg.cached}
                  error={msg.error}
                  isStreaming={
                    msg.role === 'assistant' &&
                    i === chat.state.messages.length - 1 &&
                    chat.state.isStreaming
                  }
                />
              </ScrollReveal>
            ))}
          </div>
        </div>
      )}

      <div className="border-t border-border bg-canvas pt-4 pb-2">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question..."
            disabled={chat.state.isStreaming}
            className="flex-1 rounded-lg border border-border bg-surface px-4 py-2.5 text-sm text-charcoal placeholder:text-muted/50 outline-none transition-colors focus:border-charcoal disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || chat.state.isStreaming}
            className="flex items-center gap-2 rounded-lg bg-charcoal px-4 py-2.5 text-sm text-white transition-all duration-200 hover:bg-[#333333] active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            <PaperPlaneRight size={16} weight="bold" />
          </button>
        </form>
      </div>
    </div>
  )
}
