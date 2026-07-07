const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

let _apiKey: string | null = null
let _onAuthRequired: (() => void) | null = null

export function setApiKey(key: string | null) {
  _apiKey = key
}

export function getApiKey(): string | null {
  return _apiKey
}

export function onAuthRequired(cb: () => void) {
  _onAuthRequired = cb
}

function handleAuthError(status: number) {
  if ((status === 401 || status === 403) && _onAuthRequired) {
    _onAuthRequired()
  }
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const h: Record<string, string> = {
    'Content-Type': 'application/json',
    ...extra,
  }
  if (_apiKey) {
    h['Authorization'] = `Bearer ${_apiKey}`
  }
  return h
}

export interface SourceChunk {
  text: string
  source: string
  page: number | null
}

export interface QueryRequest {
  query: string
  session_id: string
  top_k?: number
}

export interface DocumentUploadResponse {
  job_id: string
  status: 'queued'
}

export interface DocumentListItem {
  id: string
  filename: string
  chunk_count: number
}

export interface DocumentListResponse {
  documents: DocumentListItem[]
}

export interface JobStatusResponse {
  job_id: string
  status: 'queued' | 'processing' | 'done' | 'failed'
  error: string | null
}

export interface DeleteResponse {
  status: string
  id: string
}

export interface ConfigResponse {
  vector_store: string
  llm_provider: string
  auth_enabled: boolean
}

export interface ReadyResponse {
  status: 'ok' | 'not_ready'
  detail?: string
}

export type SSEEvent =
  | { type: 'token'; content: string }
  | { type: 'metadata'; sources: SourceChunk[]; cached: boolean }
  | { type: 'error'; detail: string }

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`
  const res = await fetch(url, {
    ...init,
    headers: { ...headers(), ...init?.headers },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    handleAuthError(res.status)
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }
  return res.json() as Promise<T>
}

export async function postQuery(
  req: QueryRequest,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const url = `${BASE_URL}/v1/query`
  const resp = await fetch(url, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(req),
    signal,
  })

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    handleAuthError(resp.status)
    throw new ApiError(resp.status, body.detail ?? resp.statusText)
  }

  const reader = resp.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data: ')) continue
      try {
        const data = JSON.parse(trimmed.slice(6)) as SSEEvent
        onEvent(data)
      } catch {
      }
    }
  }
}

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const url = `${BASE_URL}/v1/documents`
  const h: Record<string, string> = {}
  if (_apiKey) h['Authorization'] = `Bearer ${_apiKey}`
  const res = await fetch(url, { method: 'POST', headers: h, body: form })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    handleAuthError(res.status)
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }
  return res.json()
}

export async function listDocuments(): Promise<DocumentListResponse> {
  return request<DocumentListResponse>('/v1/documents')
}

export async function getDocumentStatus(jobId: string): Promise<JobStatusResponse> {
  return request<JobStatusResponse>(`/v1/documents/${encodeURIComponent(jobId)}`)
}

export async function deleteDocument(id: string): Promise<DeleteResponse> {
  return request<DeleteResponse>(`/v1/documents/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export async function getReadyStatus(): Promise<ReadyResponse> {
  return request<ReadyResponse>('/v1/ready')
}

export async function getConfig(): Promise<ConfigResponse> {
  return request<ConfigResponse>('/v1/config')
}
