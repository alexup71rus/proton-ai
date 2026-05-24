import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";


export interface AppShellNavItem {
  to: string;
  label: string;
  step: string;
  description: string;
}


export interface AppShellProps {
  navItems: AppShellNavItem[];
  workspaceToolbar?: ReactNode;
  children?: ReactNode;
}


export function AppShell({ navItems, workspaceToolbar, children }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar__brand">
          <h1>Proton-X</h1>
        </div>

        <nav className="sidebar__nav" aria-label="Primary">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `nav-card${isActive ? " nav-card--active" : ""}`
              }
              end={item.to === "/"}
            >
              <span className="nav-card__label">{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="workspace">
        {workspaceToolbar ? <div className="workspace__toolbar">{workspaceToolbar}</div> : null}
        <div className="workspace__frame">{children}</div>
      </main>
    </div>
  );
}
