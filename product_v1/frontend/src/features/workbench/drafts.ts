import type { components } from "../../api/schema";
export type CaseEdit = components["schemas"]["CaseEdit"];
export function draftKey(userId: string, caseId: string) { return "user-workbench:draft:v1:" + userId + ":" + caseId; }
export function readDraft(key: string): CaseEdit | null {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) || "null");
    if (!value || typeof value !== "object") return null;
    const draft = value as Record<string, unknown>;
    if (typeof draft.title !== "string" || typeof draft.summary !== "string" || typeof draft.notes !== "string" || !Number.isInteger(draft.expected_revision) || Number(draft.expected_revision) < 0) return null;
    return draft as CaseEdit;
  } catch { return null; }
}
export function saveDraft(key: string, value: CaseEdit) {
  try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; }
}
export function clearDraft(key: string) {
  try { localStorage.removeItem(key); } catch { /* The saved server revision remains authoritative. */ }
}
