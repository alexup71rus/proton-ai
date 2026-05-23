import type { PropsWithChildren } from "react";
import { NavLink } from "react-router-dom";


type NavItem = {
  to: string;
  label: string;
  step: string;
  description: string;
};


type AppShellProps = PropsWithChildren<{
  navItems: NavItem[];
}>;


export function AppShell({ navItems, children }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar panel">
        <div className="sidebar__brand">
          <span className="eyebrow">Routing workbench</span>
          <h1>Proton-X</h1>
          <p>
            Operator workspace for create, train, test, and fix without the old Streamlit clutter.
          </p>
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
              <span className="nav-card__step">{item.step}</span>
              <span className="nav-card__copy">
                <span className="nav-card__label">{item.label}</span>
                <span className="nav-card__description">{item.description}</span>
              </span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="workspace">
        <div className="workspace__frame">{children}</div>
      </main>
    </div>
  );
}
