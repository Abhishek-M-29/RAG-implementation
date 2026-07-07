import { createContext, useContext, useReducer, useCallback, type ReactNode } from 'react'
import type { ConfigResponse } from '../api/client'

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
  setComponentHealth: (detail: string | undefined, overallStatus: 'ok' | 'not_ready') => void
  setBothError: (detail: string) => void
  setLoading: (loading: boolean) => void
}

const StatusContext = createContext<StatusContextType | null>(null)

export function StatusProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(statusReducer, {
    config: null,
    vectorStore: { status: 'error', detail: null },
    llm: { status: 'error', detail: null },
    loading: true,
  })

  const setConfig = useCallback((config: ConfigResponse) => {
    dispatch({ type: 'SET_CONFIG', config })
  }, [])

  const setComponentHealth = useCallback((detail: string | undefined, overallStatus: 'ok' | 'not_ready') => {
    if (overallStatus === 'ok') {
      dispatch({ type: 'SET_VS_HEALTH', health: { status: 'ok', detail: null } })
      dispatch({ type: 'SET_LLM_HEALTH', health: { status: 'ok', detail: null } })
      return
    }

    const d = detail ?? ''
    const lower = d.toLowerCase()

    if (lower.includes('vector store')) {
      dispatch({ type: 'SET_VS_HEALTH', health: { status: 'not_ready', detail: d } })
      dispatch({ type: 'SET_LLM_HEALTH', health: { status: 'ok', detail: null } })
    } else if (lower.includes('llm')) {
      dispatch({ type: 'SET_VS_HEALTH', health: { status: 'ok', detail: null } })
      dispatch({ type: 'SET_LLM_HEALTH', health: { status: 'not_ready', detail: d } })
    } else {
      dispatch({ type: 'SET_VS_HEALTH', health: { status: 'not_ready', detail: d } })
      dispatch({ type: 'SET_LLM_HEALTH', health: { status: 'not_ready', detail: d } })
    }
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
