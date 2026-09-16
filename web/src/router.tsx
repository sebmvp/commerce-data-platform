import { createRootRoute, createRoute, createRouter, Outlet } from "@tanstack/react-router";
import { App } from "@/App";
import { CommandCenterPage } from "@/pages/Overview";
import { InventoryPage } from "@/pages/Inventory";
import { LibrarianPage } from "@/pages/Librarian";
import { EvaluationPage } from "@/pages/Evaluation";
import { DataHealthPage } from "@/pages/DataHealth";
import { SourcesPage } from "@/pages/Sources";

const rootRoute = createRootRoute({
  component: () => (
    <App>
      <Outlet />
    </App>
  ),
});

const commandCenterRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: CommandCenterPage,
});

const inventoryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/inventory",
  component: InventoryPage,
});

const itemRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/inventory/$sku",
  component: InventoryPage,
});

const librarianRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/librarian",
  component: LibrarianPage,
});

const librarianBoundRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/librarian/$sku",
  component: LibrarianPage,
});

const sourcesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/sources",
  component: SourcesPage,
});

const evaluationRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/evaluation",
  component: EvaluationPage,
});

const healthRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/data-health",
  component: DataHealthPage,
});

const routeTree = rootRoute.addChildren([
  commandCenterRoute,
  inventoryRoute,
  itemRoute,
  librarianRoute,
  librarianBoundRoute,
  sourcesRoute,
  evaluationRoute,
  healthRoute,
]);

export const router = createRouter({
  routeTree,
  defaultPreload: false,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
