import { NavLink } from 'react-router-dom'
import { ChatDots, Folder, Gear } from 'phosphor-react'
import type { ReactNode } from 'react'

interface Props {
  children: ReactNode
}

const links = [
  { to: '/', label: 'Chat', icon: ChatDots },
  { to: '/documents', label: 'Documents', icon: Folder },
  { to: '/settings', label: 'Settings', icon: Gear },
]

export default function AppShell({ children }: Props) {
  return (
    <div className="min-h-screen bg-canvas">
      <div className="ambient-blob top-[-200px] right-[-200px]" />
      <nav className="sticky top-0 z-50 border-b border-border bg-canvas/80 backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
          <span className="font-serif text-lg tracking-[-0.03em] text-charcoal">
            RAG Framework
          </span>
          <div className="flex items-center gap-1">
            {links.map((link) => {
              const Icon = link.icon
              return (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-all duration-200 ${
                      isActive
                        ? 'bg-charcoal text-white'
                        : 'text-muted hover:text-charcoal hover:bg-warm-bone'
                    }`
                  }
                >
                  <Icon size={16} weight="bold" />
                  {link.label}
                </NavLink>
              )
            })}
          </div>
        </div>
      </nav>
      <main className="mx-auto max-w-5xl px-6 py-8">
        {children}
      </main>
    </div>
  )
}
