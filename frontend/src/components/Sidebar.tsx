import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

const links = [
  { to: '/library', label: 'Library' },
  { to: '/settings', label: 'Settings' },
]

export function Sidebar() {
  return (
    <aside className="w-40 shrink-0 border-r bg-sidebar min-h-screen p-3 flex flex-col">
      <div className="text-xs font-semibold mb-4 text-sidebar-foreground/50 uppercase tracking-wider px-2">
        PT Media Manager
      </div>
      <nav className="flex flex-col gap-0.5">
        {links.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'px-2 py-1.5 rounded-md text-sm transition-colors',
                isActive
                  ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                  : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
              )
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
