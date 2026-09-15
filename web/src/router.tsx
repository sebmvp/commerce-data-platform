import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
} from "@tanstack/react-router";
import { App } from "@/App";
import { OverviewPage } from "@/pages/Overview";
import { InventoryPage } from "@/pages/Inventory";
import { ItemDetailPage } from "@/pages/ItemDetail";
import { LibrarianPage } from "@/pages/Librarian";
import { EvaluationPage } from "@/pages/Evaluation";
import { DataHealthPage } from "@/pages/DataHealth";

const rootRoute = createRootRoute({
  component: () => (
    <App>
      <Outlet />
    </App>
  ),
});

const overviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: OverviewPage,
});

const inventoryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/inventory",
  component: InventoryPage,
});

const itemRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/inventory/$sku",
  component: ItemDetailPage,
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
  overviewRoute,
  inventoryRoute,
  itemRoute,
  librarianRoute,
  librarianBoundRoute,
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
