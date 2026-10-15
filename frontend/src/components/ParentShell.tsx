import { useEffect } from "react";
import { Navigate, NavLink, Outlet } from "react-router";

import { useMe } from "../api/queries";

/**
 * The parent screens' frame: the calm "Morning Light" look, and a nav that
 * links back to the pages still in the legacy app. Children are sent to their trail.
 */
export function ParentShell() {
  const me = useMe();

  useEffect(() => {
    // A parent who previewed a child's trail comes back to the parent look.
    const root = document.documentElement;
    delete root.dataset.persona;
    delete root.dataset.season;
  }, []);

  if (me.data?.role === "child") return <Navigate to="/trail" replace />;

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="shell-bar">
        <a className="shell-brand" href="/#/dashboard">
          <img src="/static/curiculy-logo.png" alt="" />
          Curiculy
        </a>
        <nav className="shell-nav" aria-label="Main">
          <a href="/#/dashboard">Home</a>
          <a href="/#/assignments">Calendar</a>
          <a href="/#/students">Kids</a>
          <NavLink to="/library">Library</NavLink>
          <NavLink to="/planner">Curriculum planner</NavLink>
          <NavLink to="/reading">Reading</NavLink>
          <NavLink to="/activities">Activities</NavLink>
          <a href="/#/portfolios">Portfolios</a>
          {me.data?.is_admin ? <NavLink to="/admin/catalog">Catalog review</NavLink> : null}
          <a href="/#/settings">Settings</a>
        </nav>
      </header>
      <main id="main" className="page">
        <Outlet />
      </main>
    </>
  );
}
