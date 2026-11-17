import type { components } from "./schema";
export type Entity = components["schemas"]["Entity"];
export type CaseRecord = components["schemas"]["CaseRecord"];
export type EvidenceItem = components["schemas"]["EvidenceItem"];
export type SourceRef = components["schemas"]["SourceRef"] & Partial<components["schemas"]["DocumentSourceRef"]>;
export type MatrixRow = components["schemas"]["MatrixRow"];
export type CasePlan = components["schemas"]["CasePlan"];
export type ProofGraph = components["schemas"]["ProofGraph"];
export type ReviewRequest = components["schemas"]["ReviewRequest"];
export type User = components["schemas"]["UserView"];
export type ModelConfig = components["schemas"]["ModelView"];
export type ConnectivityResult = components["schemas"]["ConnectivityResult"];
export type ConnectivityImage = components["schemas"]["ConnectivityImage"];
export type BatchResult = components["schemas"]["BatchUploadResult"];

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
function expired(path: string, status: number) {
  if (status === 401 && !path.startsWith("/auth/")) window.dispatchEvent(new Event("session-expired"));
}

export async function api<T>(
  path: string,
  body?: unknown,
  method = "POST",
): Promise<T> {
  const response = await fetch(
    "/v1" + path,
    body === undefined
      ? {}
      : {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    expired(path, response.status);
    throw new ApiError(error.detail || response.statusText, response.status);
  }
  return response.json();
}
export async function upload(caseId: string, file: File) {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`/v1/cases/${caseId}/evidence`, {
    method: "POST",
    body,
  });
  if (!response.ok) throw new Error((await response.json()).detail);
  return response.json() as Promise<EvidenceItem>;
}

export async function uploadBatch(caseId: string, files: File[]) {
  const body = new FormData();
  files.forEach((file) => body.append("files", file));
  const path = `/cases/${caseId}/evidence/batch`;
  const response = await fetch("/v1" + path, { method: "POST", body });
  if (!response.ok) {
    expired(path, response.status);
    throw new ApiError((await response.json()).detail || response.statusText, response.status);
  }
  return response.json() as Promise<BatchResult>;
}
