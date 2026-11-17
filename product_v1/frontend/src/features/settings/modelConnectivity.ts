import type { ConnectivityResult, ModelConfig } from "../../api/client";

export type ConnectionMode = "text" | "image";
export type ConnectionState = "connected" | "partial" | "untested" | "failed" | "disabled";
export type TestOverrides = Record<string, ConnectivityResult | null>;
export function modelChecks(model: ModelConfig, overrides: TestOverrides) {
  const get = (mode: ConnectionMode) => Object.hasOwn(overrides, model.id + ":" + mode) ? overrides[model.id + ":" + mode] : model.connectivity?.[mode];
  return { text: get("text"), image: model.supports_vision ? get("image") : undefined };
}
export function connectionState(model: ModelConfig, overrides: TestOverrides): ConnectionState {
  if (!model.allow_external_egress || !model.has_api_key) return "disabled";
  const checks = modelChecks(model, overrides);
  const relevant = model.supports_vision ? [checks.text, checks.image] : [checks.text];
  if (relevant.every(check => check?.success)) return "connected";
  if (relevant.some(check => check?.success)) return "partial";
  if (relevant.some(check => check && !check.success)) return "failed";
  return "untested";
}
const rank: Record<ConnectionState, number> = { connected: 0, partial: 1, untested: 2, failed: 3, disabled: 4 };
export function orderModels(models: ModelConfig[], overrides: TestOverrides, testing = "") {
  const state = (model: ModelConfig) => connectionState(model, testing.startsWith(model.id + ":") ? {} : overrides);
  return [...models].sort((a,b) => rank[state(a)] - rank[state(b)]);
}
