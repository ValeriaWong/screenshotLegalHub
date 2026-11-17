import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nProvider } from "./i18n";
import { App } from "./app/App";
import { AuthGate } from "./features/auth/AuthGate";
import "./design-system/tokens.css";
import "./styles/app.css";
const client = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 1000 } },
});
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <I18nProvider>
        <AuthGate><App /></AuthGate>
      </I18nProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
