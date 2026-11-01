import { render } from "solid-js/web";
import { Router, Route, Navigate } from "@solidjs/router";
import { QueryClient, QueryClientProvider } from "@tanstack/solid-query";
import { lazy } from "solid-js";
import App from "./App";
import { authStore } from "./stores/authStore";
import { initAnalytics } from "./lib/analytics";
import "./index.css";

const Home = lazy(() => import("./pages/Home"));
const MatchMyMusic = lazy(() => import("./pages/MatchMyMusic"));
const DiscoverExport = lazy(() => import("./pages/DiscoverExport"));
const Privacy = lazy(() => import("./pages/Privacy"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60,  
      retry: 1,
    },
  },
});

authStore.initAuth();

const root = document.getElementById("root");

if (!root) {
  throw new Error("Root element not found");
}

render(
  () => (
    <QueryClientProvider client={queryClient}>
      <Router root={App}>
        <Route path="/" component={Home} />
        <Route path="/match" component={MatchMyMusic} />
        <Route path="/discover" component={DiscoverExport} />
        <Route path="/privacy" component={Privacy} />
        { }
        <Route path="/spotify-to-ignition" component={() => <Navigate href="/match" />} />
        <Route path="/ignition-to-spotify" component={() => <Navigate href="/discover" />} />
      </Router>
    </QueryClientProvider>
  ),
  root
);

requestIdleCallback(() => {
  import("@sentry/browser").then((Sentry) => {
    Sentry.init({
      dsn: import.meta.env.VITE_SENTRY_DSN,
      environment: import.meta.env.MODE,
    });
  });
  initAnalytics();
});
