import { Navigate, createBrowserRouter, type RouteObject } from "react-router";

import { ParentShell } from "./components/ParentShell";
import { RequireSession } from "./components/RequireSession";
import { CatalogReviewPage } from "./routes/CatalogReviewPage";
import { CurriculumPage } from "./routes/CurriculumPage";
import { JournalPage } from "./routes/JournalPage";
import { LibraryPage } from "./routes/LibraryPage";
import { NewCurriculumPage } from "./routes/NewCurriculumPage";
import { NotFound } from "./routes/NotFound";
import { PlannerPage } from "./routes/PlannerPage";
import { TrailPage } from "./routes/TrailPage";

export const routes: RouteObject[] = [
  {
    element: <RequireSession />,
    children: [
      { path: "/", element: <Navigate to="/trail" replace /> },
      { path: "/trail", element: <TrailPage /> },
      { path: "/journal", element: <JournalPage /> },
      {
        // Parent screens: the Library, the Curriculum planner, catalog review.
        element: <ParentShell />,
        children: [
          { path: "/library", element: <LibraryPage /> },
          { path: "/planner", element: <PlannerPage /> },
          { path: "/planner/new", element: <NewCurriculumPage /> },
          { path: "/planner/:id", element: <CurriculumPage /> },
          { path: "/admin/catalog", element: <CatalogReviewPage /> },
        ],
      },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export function createRouter() {
  return createBrowserRouter(routes, { basename: "/next" });
}
