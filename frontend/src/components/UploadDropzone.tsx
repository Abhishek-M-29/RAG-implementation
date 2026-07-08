import { useState, useRef, type DragEvent } from 'react'
import { Upload } from 'phosphor-react'

interface Props {
  onUpload: (file: File) => void
  disabled?: boolean
}

export default function UploadDropzone({ onUpload, disabled }: Props) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function handleDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file && file.type === 'application/pdf') {
      onUpload(file)
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file && file.type === 'application/pdf') {
      onUpload(file)
    }
    // Reset so the same file can be selected again
    e.target.value = ''
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={`relative cursor-pointer rounded-lg border-2 border-dashed p-12 text-center transition-all duration-200 ${
        dragging
          ? 'border-charcoal bg-warm-bone'
          : 'border-border hover:border-charcoal/30 hover:bg-warm-bone/50'
      } ${disabled ? 'pointer-events-none opacity-50' : ''}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        onChange={handleChange}
        className="hidden"
      />
      <div className="flex flex-col items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-warm-bone">
          <Upload size={20} className="text-muted" weight="bold" />
        </div>
        <div>
          <p className="text-sm text-charcoal">
            Drop a PDF here or click to browse
          </p>
          <p className="text-xs text-muted mt-1">Only PDF files are accepted</p>
        </div>
      </div>
    </div>
  )
}
