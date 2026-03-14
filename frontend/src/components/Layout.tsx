import { Outlet, NavLink } from 'react-router-dom'
import './Layout.css'

const navItems = [
  { path: '/', label: 'Command Center' },
  { path: '/tax', label: 'Tax Brain' },
  { path: '/expenses', label: 'Expenses' },
  { path: '/email', label: 'Email Intel' },
  { path: '/scenarios', label: 'Scenario Lab' },
  { path: '/alerts', label: 'Alerts' },
]

export function Layout() {
  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="sidebar-header">
          <h1 className="logo">SENTINEL</h1>
          <span className="version">v0.1.0</span>
        </div>
        <ul className="nav-list">
          {navItems.map((item) => (
            <li key={item.path}>
              <NavLink
                to={item.path}
                className={({ isActive }) =>
                  `nav-link ${isActive ? 'active' : ''}`
                }
              >
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
        <div className="sidebar-footer">
          <div className="status-dot" />
          <span className="status-text">System Online</span>
        </div>
      </nav>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
