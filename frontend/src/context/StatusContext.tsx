import { createContext, useContext, useReducer, useCallback, type ReactNode } from 'react'
import type { ConfigResponse, ReadyResponse } from '../api/client'

interface ComponentHealth {
  status: 'ok' | 'not_ready' | 'error'
  detail: string | null
}

interface StatusState {
  config: ConfigResponse | null
  vectorStore: ComponentHealth
  llm: ComponentHealth
  loading: boolean
}

type StatusAction =
  | { type: 'SET_CONFIG'; config: ConfigResponse }
  | { type: 'SET_VS_HEALTH'; health: ComponentHealth }
  | { type: 'SET_LLM_HEALTH'; health: ComponentHealth }
  | { type: 'SET_BOTH_ERROR'; detail: string }
  | { type: 'SET_LOADING'; loading: boolean }

function statusReducer(state: StatusState, action: StatusAction): StatusState {
  switch (action.type) {
    case 'SET_CONFIG':
      return { ...state, config: action.config }
    case 'SET_VS_HEALTH':
      return { ...state, vectorStore: action.health }
    case 'SET_LLM_HEALTH':
      return { ...state, llm: action.health }
    case 'SET_BOTH_ERROR':
      return {
        ...state,
        vectorStore: { status: 'error', detail: action.detail },
        llm: { status: 'error', detail: action.detail },
      }
    case 'SET_LOADING':
      return { ...state, loading: action.loading }
    default:
      return state
  }
}

interface StatusContextType {
  state: StatusState
  setConfig: (config: ConfigResponse) => void
  setComponentHealth: (ready: ReadyResponse) => void
  setBothError: (detail: string) => void
  setLoading: (loading: boolean) => void
}

const StatusContext = createContext<StatusContextType | null>(null)

export function StatusProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(statusReducer, {
    config: null,
    vectorStore: { status: 'not_ready', detail: null },
    llm: { status: 'not_ready', detail: null },
    loading: true,
  })

  const setConfig = useCallback((config: ConfigResponse) => {
    dispatch({ type: 'SET_CONFIG', config })
  }, [])

  const setComponentHealth = useCallback((ready: ReadyResponse) => {
    if (ready.status === 'ok') {
      dispatch({ type: 'SET_VS_HEALTH', health: { status: 'ok', detail: null } })
      dispatch({ type: 'SET_LLM_HEALTH', health: { status: 'ok', detail: null } })
      return
    }

    const vectorStore = ready.vector_store ?? {
      status: 'not_ready',
      detail: ready.detail ?? null,
    }
    const llm = ready.llm ?? {
      status: 'not_ready',
      detail: ready.detail ?? null,
    }

    dispatch({
      type: 'SET_VS_HEALTH',
      health: { status: vectorStore.status, detail: vectorStore.detail ?? null },
    })
    dispatch({
      type: 'SET_LLM_HEALTH',
      health: { status: llm.status, detail: llm.detail ?? null },
    })
  }, [])

  const setBothError = useCallback((detail: string) => {
    dispatch({ type: 'SET_BOTH_ERROR', detail })
  }, [])

  const setLoading = useCallback((loading: boolean) => {
    dispatch({ type: 'SET_LOADING', loading })
  }, [])

  return (
    <StatusContext.Provider
      value={{ state, setConfig, setComponentHealth, setBothError, setLoading }}
    >
      {children}
    </StatusContext.Provider>
  )
}

export function useStatus(): StatusContextType {
  const ctx = useContext(StatusContext)
  if (!ctx) throw new Error('useStatus must be used within StatusProvider')
  return ctx
}
