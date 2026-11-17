import type { Content, Render, PageLayout } from "./client";
export interface LocalDraft { draft_id: string; base_revision: number; content: { content: Content; note: string; render: Render; layout?: PageLayout[]; layout_manifest_id?: string | null; coordinates_unlocked?: boolean; comment_drafts?: Record<string, string>; text_dirty?: boolean }; updated_at: string }
const database = () => new Promise<IDBDatabase>((resolve, reject) => {
  if (!globalThis.indexedDB) { reject(new Error("本浏览器不支持 IndexedDB")); return; }
  const request = indexedDB.open("screenshotlegal-review-v1", 1);
  request.onupgradeneeded = () => request.result.createObjectStore("drafts");
  request.onsuccess = () => resolve(request.result);
  request.onerror = () => reject(request.error);
});
async function transact<T>(mode: IDBTransactionMode, action: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("drafts", mode);
    const request = action(tx.objectStore("drafts"));
    tx.oncomplete = () => { db.close(); resolve(request.result); };
    tx.onerror = () => { db.close(); reject(tx.error); };
    tx.onabort = () => { db.close(); reject(tx.error); };
  });
}
export const draftKey = (user: string, dataset: string, sample: string) => JSON.stringify([user, dataset, sample]);
export const readDraft = (id: string) => transact<LocalDraft | undefined>("readonly", s => s.get(id));
let pending: Promise<unknown> = Promise.resolve();
function enqueue<T>(operation: () => Promise<T>): Promise<T> {
  const next = pending.catch(() => undefined).then(operation);
  pending = next;
  return next;
}
export const writeDraft = (id: string, value: LocalDraft) => enqueue(() => transact("readwrite", s => s.put(value, id)));
export const clearDraft = (id: string) => enqueue(() => transact("readwrite", s => s.delete(id)));
