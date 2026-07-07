import { WarningCircle } from 'phosphor-react'

interface Props {
  message: string
  detail?: string
  onRetry?: () => void
}

export default function ErrorState({ message, detail, onRetry }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-24 px-6 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-pale-red-bg">
        <WarningCircle size={24} className="text-pale-red-text" weight="bold" />
      </div>
      <h2 className="font-serif text-xl tracking-[-0.02em] text-charcoal mb-2">
        {message}
      </h2>
      {detail && (
        <p className="text-muted text-sm max-w-md mb-6 font-mono">
          {detail}
        </p>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded px-4 py-2 bg-charcoal text-white text-sm transition-all duration-200 active:scale-[0.98] hover:bg-[#333333] cursor-pointer"
        >
          Try again
        </button>
      )}
    </div>
  )
}
