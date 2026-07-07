import { createContext, useContext, useReducer, useCallback, type ReactNode } from 'react'
import type { SourceChunk } from '../api/client'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceChunk[]
  cached?: boolean
  error?: string
}

interface ChatState {
  sessionId: string
  messages: Message[]
  isStreaming: boolean
}

type ChatAction =
  | { type: 'ADD_MESSAGE'; message: Message }
  | { type: 'APPEND_TOKEN'; messageId: string; token: string }
  | { type: 'SET_SOURCES'; messageId: string; sources: SourceChunk[]; cached: boolean }
  | { type: 'SET_ERROR'; messageId: string; error: string }
  | { type: 'SET_STREAMING'; isStreaming: boolean }
  | { type: 'CLEAR_SESSION'; sessionId: string }

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'ADD_MESSAGE':
      return { ...state, messages: [...state.messages, action.message] }
    case 'APPEND_TOKEN':
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.id === action.messageId ? { ...m, content: m.content + action.token } : m,
        ),
      }
    case 'SET_SOURCES':
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.id === action.messageId ? { ...m, sources: action.sources, cached: action.cached } : m,
        ),
      }
    case 'SET_ERROR':
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.id === action.messageId ? { ...m, error: action.error } : m,
        ),
      }
    case 'SET_STREAMING':
      return { ...state, isStreaming: action.isStreaming }
    case 'CLEAR_SESSION':
      return { sessionId: action.sessionId, messages: [], isStreaming: false }
    default:
      return state
  }
}

function newSessionId(): string {
  return crypto.randomUUID()
}

interface ChatContextType {
  state: ChatState
  addUserMessage: (content: string) => string
  addAssistantMessage: (id: string) => void
  appendToken: (messageId: string, token: string) => void
  setSources: (messageId: string, sources: SourceChunk[], cached: boolean) => void
  setError: (messageId: string, error: string) => void
  setStreaming: (isStreaming: boolean) => void
  clearSession: () => void
}

const ChatContext = createContext<ChatContextType | null>(null)

export function ChatProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(chatReducer, {
    sessionId: newSessionId(),
    messages: [],
    isStreaming: false,
  })

  const addUserMessage = useCallback((content: string): string => {
    const id = crypto.randomUUID()
    dispatch({ type: 'ADD_MESSAGE', message: { id, role: 'user', content } })
    return id
  }, [])

  const addAssistantMessage = useCallback((id: string) => {
    dispatch({ type: 'ADD_MESSAGE', message: { id, role: 'assistant', content: '' } })
  }, [])

  const appendToken = useCallback((messageId: string, token: string) => {
    dispatch({ type: 'APPEND_TOKEN', messageId, token })
  }, [])

  const setSources = useCallback((messageId: string, sources: SourceChunk[], cached: boolean) => {
    dispatch({ type: 'SET_SOURCES', messageId, sources, cached })
  }, [])

  const setError = useCallback((messageId: string, error: string) => {
    dispatch({ type: 'SET_ERROR', messageId, error })
  }, [])

  const setStreaming = useCallback((isStreaming: boolean) => {
    dispatch({ type: 'SET_STREAMING', isStreaming })
  }, [])

  const clearSession = useCallback(() => {
    dispatch({ type: 'CLEAR_SESSION', sessionId: newSessionId() })
  }, [])

  return (
    <ChatContext.Provider
      value={{
        state,
        addUserMessage,
        addAssistantMessage,
        appendToken,
        setSources,
        setError,
        setStreaming,
        clearSession,
      }}
    >
      {children}
    </ChatContext.Provider>
  )
}

export function useChat(): ChatContextType {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChat must be used within ChatProvider')
  return ctx
}
