import { Navigate, createBrowserRouter, type RouteObject } from "react-router";

import { RequireSession } from "./components/RequireSession";
import { JournalPage } from "./routes/JournalPage";
import { NotFound } from "./routes/NotFound";
import { TrailPage } from "./routes/TrailPage";

export const routes: RouteObject[] = [
  {
    element: <RequireSession />,
    children: [
      { path: "/", element: <Navigate to="/trail" replace /> },
      { path: "/trail", element: <TrailPage /> },
      { path: "/journal", element: <JournalPage /> },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export function createRouter() {
  return createBrowserRouter(routes, { basename: "/next" });
}
