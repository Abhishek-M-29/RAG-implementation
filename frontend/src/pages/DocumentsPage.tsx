import { useEffect, useCallback } from 'react'
import { Trash, FileX, CheckCircle, Clock, Upload } from 'phosphor-react'
import { useDocuments } from '../context/DocumentContext'
import {
  listDocuments,
  uploadDocument as apiUpload,
  getDocumentStatus,
  deleteDocument as apiDelete,
  ApiError,
} from '../api/client'
import UploadDropzone from '../components/UploadDropzone'
import ErrorState from '../components/ErrorState'
import ScrollReveal from '../components/ScrollReveal'

export default function DocumentsPage() {
  const docs = useDocuments()

  const fetchDocs = useCallback(async () => {
    docs.setLoading(true)
    docs.setError(null)
    try {
      const res = await listDocuments()
      docs.setDocuments(res.documents)
    } catch (err) {
      if (err instanceof ApiError) {
        docs.setError(err.message)
      } else {
        docs.setError('Unable to reach the backend server.')
      }
    }
  }, [docs])

  useEffect(() => {
    fetchDocs()
  }, [fetchDocs])

  useEffect(() => {
    const active = docs.state.uploads.filter(
      (u) => u.status !== 'done' && u.status !== 'failed',
    )
    if (active.length === 0) return

    const timers: ReturnType<typeof setInterval>[] = []

    for (const upload of active) {
      const poll = async () => {
        try {
          const res = await getDocumentStatus(upload.jobId)
          docs.updateUpload(upload.jobId, { status: res.status, error: res.error })
          if (res.status === 'done' || res.status === 'failed') {
            fetchDocs()
          }
        } catch {
          docs.updateUpload(upload.jobId, { status: 'failed', error: 'Status check failed' })
        }
      }
      poll()
      const timer = setInterval(poll, 2000)
      timers.push(timer)
    }

    return () => timers.forEach(clearInterval)
  }, [docs.state.uploads, docs, fetchDocs])

  async function handleUpload(file: File) {
    try {
      const res = await apiUpload(file)
      docs.addUpload({
        jobId: res.job_id,
        filename: file.name,
        status: 'queued',
        error: null,
      })
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401 || err.status === 403) {
          return
        }
        docs.setError(err.message)
      } else {
        docs.setError('Upload failed.')
      }
    }
  }

  async function handleDelete(id: string) {
    try {
      await apiDelete(id)
      docs.removeDocument(id)
    } catch (err) {
      if (err instanceof ApiError) {
        docs.setError(err.message)
      } else {
        docs.setError('Delete failed.')
      }
    }
  }

  const statusIcon = (status: string) => {
    switch (status) {
      case 'done':
        return <CheckCircle size={14} className="text-pale-green-text" weight="bold" />
      case 'failed':
        return <FileX size={14} className="text-pale-red-text" weight="bold" />
      case 'processing':
        return <Clock size={14} className="text-pale-yellow-text" weight="bold" />
      default:
        return <Clock size={14} className="text-muted" weight="bold" />
    }
  }

  const statusBadge = (status: string) => {
    const styles: Record<string, string> = {
      done: 'bg-pale-green-bg text-pale-green-text',
      failed: 'bg-pale-red-bg text-pale-red-text',
      processing: 'bg-pale-yellow-bg text-pale-yellow-text',
      queued: 'bg-warm-bone text-muted',
    }
    return (
      <span
        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.05em] ${styles[status] ?? styles.queued}`}
      >
        {statusIcon(status)}
        {status}
      </span>
    )
  }

  return (
    <ScrollReveal>
      <div className="max-w-4xl mx-auto">
        <div className="mb-10">
          <h1 className="font-serif text-3xl tracking-[-0.03em] text-charcoal mb-2">
            Document Management
          </h1>
          <p className="text-sm text-muted">
            Upload PDFs to index them for question answering.
          </p>
        </div>

        <div className="mb-10">
          <UploadDropzone onUpload={handleUpload} disabled={docs.state.uploads.some((u) => u.status === 'queued' || u.status === 'processing')} />
        </div>

        {docs.state.error && (
          <div className="mb-6">
            <ErrorState message="Error" detail={docs.state.error} onRetry={fetchDocs} />
          </div>
        )}

        {docs.state.uploads.length > 0 && (
          <div className="mb-8">
            <h2 className="font-serif text-lg tracking-[-0.02em] text-charcoal mb-4">
              Recent Uploads
            </h2>
            <div className="space-y-2">
              {docs.state.uploads.map((upload) => (
                <div
                  key={upload.jobId}
                  className="flex items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3"
                >
                  <Upload size={16} className="text-muted shrink-0" weight="bold" />
                  <span className="flex-1 text-sm text-charcoal truncate">
                    {upload.filename}
                  </span>
                  {statusBadge(upload.status)}
                  {upload.error && (
                    <span className="text-xs text-pale-red-text font-mono max-w-[200px] truncate">
                      {upload.error}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div>
          <h2 className="font-serif text-lg tracking-[-0.02em] text-charcoal mb-4">
            Indexed Documents
          </h2>
          {docs.state.documents.length === 0 && !docs.state.loading ? (
            <div className="rounded-lg border border-border bg-surface p-12 text-center">
              <p className="text-sm text-muted">
                No documents indexed yet. Upload a PDF to get started.
              </p>
            </div>
          ) : (
            <div className="rounded-lg border border-border overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-warm-bone">
                    <th className="px-4 py-3 text-left text-xs text-muted font-mono uppercase tracking-[0.05em]">Filename</th>
                    <th className="px-4 py-3 text-left text-xs text-muted font-mono uppercase tracking-[0.05em]">Chunks</th>
                    <th className="px-4 py-3 text-right text-xs text-muted font-mono uppercase tracking-[0.05em]">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.state.documents.map((doc, i) => (
                    <tr
                      key={doc.id}
                      className="border-b border-border last:border-0 transition-colors hover:bg-warm-bone/50"
                      style={{ animationDelay: `${i * 80}ms` }}
                    >
                      <td className="px-4 py-3 text-charcoal">{doc.filename}</td>
                      <td className="px-4 py-3 text-muted font-mono text-xs">{doc.chunk_count}</td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-muted transition-colors hover:text-pale-red-text hover:bg-pale-red-bg cursor-pointer"
                        >
                          <Trash size={12} weight="bold" />
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </ScrollReveal>
  )
}
