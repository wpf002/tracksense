import { NavLink as RouterNavLink } from 'react-router-dom'

export default function NavLink({ to, children }) {
  return (
    <RouterNavLink
      to={to}
      className={({ isActive }) =>
        [
          'flex items-center gap-2 px-3 py-2 text-sm font-medium tracking-wide uppercase transition-colors',
          isActive
            ? 'text-accent border-l-2 border-accent bg-surface-2 pl-[10px]'
            : 'text-text-muted hover:text-text-primary border-l-2 border-transparent pl-[10px]',
        ].join(' ')
      }
    >
      {children}
    </RouterNavLink>
  )
}