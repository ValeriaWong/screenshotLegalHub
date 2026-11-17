import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nProvider } from "./i18n";
import { AuthGate } from "./features/auth/AuthGate";
import { ResearchApp } from "./features/research/ResearchApp";
import { FeatureBoundary } from "./components/feedback";
import "./design-system/tokens.css";
import "./styles/app.css";
import "./styles/research.css";
import "./styles/pack3.css";
document.documentElement.dataset.workbenchTheme = "pack3";
const client = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 1000 } } });
const product = location.pathname.includes("studio") ? "studio" : location.pathname.includes("review") ? "review" : "evaluation";
createRoot(document.getElementById("root")!).render(
  <React.StrictMode><QueryClientProvider client={client}><I18nProvider><AuthGate><FeatureBoundary label="页面加载失败"><ResearchApp product={product} /></FeatureBoundary></AuthGate></I18nProvider></QueryClientProvider></React.StrictMode>,
);
