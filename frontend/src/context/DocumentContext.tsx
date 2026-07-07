import { createContext, useContext, useReducer, useCallback, type ReactNode } from 'react'
import type { DocumentListItem } from '../api/client'

interface UploadJob {
  jobId: string
  filename: string
  status: 'queued' | 'processing' | 'done' | 'failed'
  error: string | null
}

interface DocumentState {
  documents: DocumentListItem[]
  uploads: UploadJob[]
  loading: boolean
  error: string | null
}

type DocumentAction =
  | { type: 'SET_DOCUMENTS'; documents: DocumentListItem[] }
  | { type: 'ADD_UPLOAD'; upload: UploadJob }
  | { type: 'UPDATE_UPLOAD'; jobId: string; updates: Partial<UploadJob> }
  | { type: 'REMOVE_UPLOAD'; jobId: string }
  | { type: 'REMOVE_DOCUMENT'; id: string }
  | { type: 'SET_LOADING'; loading: boolean }
  | { type: 'SET_ERROR'; error: string | null }

function documentReducer(state: DocumentState, action: DocumentAction): DocumentState {
  switch (action.type) {
    case 'SET_DOCUMENTS':
      return { ...state, documents: action.documents, loading: false }
    case 'ADD_UPLOAD':
      return { ...state, uploads: [...state.uploads, action.upload] }
    case 'UPDATE_UPLOAD':
      return {
        ...state,
        uploads: state.uploads.map((u) =>
          u.jobId === action.jobId ? { ...u, ...action.updates } : u,
        ),
      }
    case 'REMOVE_UPLOAD':
      return { ...state, uploads: state.uploads.filter((u) => u.jobId !== action.jobId) }
    case 'REMOVE_DOCUMENT':
      return { ...state, documents: state.documents.filter((d) => d.id !== action.id) }
    case 'SET_LOADING':
      return { ...state, loading: action.loading }
    case 'SET_ERROR':
      return { ...state, error: action.error, loading: false }
    default:
      return state
  }
}

interface DocumentContextType {
  state: DocumentState
  setDocuments: (documents: DocumentListItem[]) => void
  addUpload: (upload: UploadJob) => void
  updateUpload: (jobId: string, updates: Partial<UploadJob>) => void
  removeUpload: (jobId: string) => void
  removeDocument: (id: string) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

const DocumentContext = createContext<DocumentContextType | null>(null)

export function DocumentProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(documentReducer, {
    documents: [],
    uploads: [],
    loading: false,
    error: null,
  })

  const setDocuments = useCallback((documents: DocumentListItem[]) => {
    dispatch({ type: 'SET_DOCUMENTS', documents })
  }, [])

  const addUpload = useCallback((upload: UploadJob) => {
    dispatch({ type: 'ADD_UPLOAD', upload })
  }, [])

  const updateUpload = useCallback((jobId: string, updates: Partial<UploadJob>) => {
    dispatch({ type: 'UPDATE_UPLOAD', jobId, updates })
  }, [])

  const removeUpload = useCallback((jobId: string) => {
    dispatch({ type: 'REMOVE_UPLOAD', jobId })
  }, [])

  const removeDocument = useCallback((id: string) => {
    dispatch({ type: 'REMOVE_DOCUMENT', id })
  }, [])

  const setLoading = useCallback((loading: boolean) => {
    dispatch({ type: 'SET_LOADING', loading })
  }, [])

  const setError = useCallback((error: string | null) => {
    dispatch({ type: 'SET_ERROR', error })
  }, [])

  return (
    <DocumentContext.Provider
      value={{
        state,
        setDocuments,
        addUpload,
        updateUpload,
        removeUpload,
        removeDocument,
        setLoading,
        setError,
      }}
    >
      {children}
    </DocumentContext.Provider>
  )
}

export function useDocuments(): DocumentContextType {
  const ctx = useContext(DocumentContext)
  if (!ctx) throw new Error('useDocuments must be used within DocumentProvider')
  return ctx
}
