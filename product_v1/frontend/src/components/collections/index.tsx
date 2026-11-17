import { Children, cloneElement, isValidElement, useId, useMemo, useState, type ReactElement, type ReactNode, type SelectHTMLAttributes } from "react";
import { useI18n } from "../../i18n";
import { Button, Input } from "../ui";

function searchableText(value: unknown, depth = 0): string {
  if (value == null) return "";
  if (typeof value !== "object") return String(value);
  if (Array.isArray(value)) return depth < 3 ? value.map(v => searchableText(v, depth + 1)).join(" ") : "";
  const row = value as Record<string, unknown>;
  const fields = ["title", "name", "label", "filename", "body", "text", "findings", "suggestions", "reason", "status", "username", "display_name", "id", "question", "image_name", "category", "tags", "model_name", "kind", "method", "verdict", "task_id", "sample_id", "batch_id", "protocol_id", "citation"];
  const own = fields.map(key => typeof row[key] === "string" ? row[key] : Array.isArray(row[key]) ? row[key].filter(v => typeof v === "string").join(" ") : "").join(" ");
  return own + (depth < 2 ? ["evidence", "claim", "element", "fact", "model"].map(key => searchableText(row[key], depth + 1)).join(" ") : "");
}
export function usePagination<T>(items: readonly T[], { pageSize = 20, resetKey = "", anchorIndex = -1 }: { pageSize?: number; resetKey?: string; anchorIndex?: number } = {}) {
  const [state, setState] = useState({ page: anchorIndex < 0 ? 1 : Math.floor(anchorIndex / pageSize) + 1, size: pageSize, scope: resetKey, anchorResolved: anchorIndex >= 0 });
  const size = state.size;
  const pages = Math.max(1, Math.ceil(items.length / size));
  const initialPage = anchorIndex < 0 ? 1 : Math.floor(anchorIndex / size) + 1;
  const resolveAnchor = state.scope !== resetKey || (!state.anchorResolved && anchorIndex >= 0);
  if (resolveAnchor) setState({ ...state, page: Math.min(pages, initialPage), scope: resetKey, anchorResolved: anchorIndex >= 0 });
  else if (state.page > pages) setState({ ...state, page: pages });
  const page = Math.max(1, Math.min(pages, resolveAnchor ? initialPage : state.page));
  const offset = (page - 1) * size;
  const go = (next: number) => setState({ page: Math.max(1, Math.min(pages, next)), size, scope: resetKey, anchorResolved: state.anchorResolved || anchorIndex >= 0 });
  return { items: items.slice(offset, offset + size), total: items.length, page, pages, size, offset, go, resize: (next: number) => setState({ page: Math.floor(offset / next) + 1, size: next, scope: resetKey, anchorResolved: state.anchorResolved || anchorIndex >= 0 }) };
}
type PaginationState = Omit<ReturnType<typeof usePagination>, "items">;
export function Pagination({ paging, label, search, onSearch, allTotal }: { paging: PaginationState; label: string; search?: string; onSearch?: (value: string) => void; allTotal?: number }) {
  const { locale } = useI18n();
  const en = locale === "en";
  const id = useId();
  const [jump, setJump] = useState("");
  const total = paging.total;
  return <div className="collection-controls" role="group" aria-label={label + (en ? " pagination" : "分页")}>
    {onSearch && <label className="collection-search" htmlFor={id + "-search"}>{en ? "Search " : "搜索"}{label}<Input id={id + "-search"} type="search" value={search || ""} onChange={e => onSearch(e.target.value)} onKeyDown={e => { if (e.key === "Enter") e.preventDefault(); }} /></label>}
    <span className="collection-count" aria-live="polite" aria-atomic="true">{en ? "Showing " : "显示 "}{total ? paging.offset + 1 : 0}–{Math.min(paging.offset + paging.size, total)} / {total}{allTotal != null && allTotal !== total ? (en ? " matches of " : " 条匹配 / 总计 ") + allTotal : en ? " items" : " 条"}</span>
    <div className="collection-page-actions">
      <Button type="button" disabled={paging.page <= 1} onClick={() => { paging.go(paging.page - 1); setJump(""); }} aria-label={(en ? "Previous page: " : "上一页：") + label}>{en ? "Previous" : "上一页"}</Button>
      <span className="collection-page-number">{paging.page} / {paging.pages}</span>
      <Button type="button" disabled={paging.page >= paging.pages} onClick={() => { paging.go(paging.page + 1); setJump(""); }} aria-label={(en ? "Next page: " : "下一页：") + label}>{en ? "Next" : "下一页"}</Button>
    </div>
    <label className="collection-page-size" htmlFor={id + "-size"}>{en ? "Per page" : "每页"}<select id={id + "-size"} value={paging.size} onChange={e => paging.resize(Number(e.target.value))}>{[...new Set([paging.size, 10, 20, 50])].sort((a,b) => a-b).map(size => <option key={size} value={size}>{size}</option>)}</select></label>
    {paging.pages > 5 && <div className="collection-jump"><label htmlFor={id + "-jump"}>{en ? "Page" : "跳至页"}<Input id={id + "-jump"} type="number" min={1} max={paging.pages} value={jump} onChange={e => setJump(e.target.value)} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); const page = Number(jump); if (Number.isInteger(page) && page >= 1 && page <= paging.pages) paging.go(page); } }} /></label><Button type="button" disabled={!Number.isInteger(Number(jump)) || Number(jump) < 1 || Number(jump) > paging.pages} onClick={() => paging.go(Number(jump))}>{en ? "Go" : "前往"}</Button></div>}
  </div>;
}
export function Paged<T>({ items: supplied, label, children, pageSize = 20, resetKey = "", anchorIndex = -1, searchable = true, searchText = searchableText, layout = "block" }: { items: readonly T[] | null | undefined; label: string; children: (items: T[], offset: number) => ReactNode; pageSize?: number; resetKey?: string; anchorIndex?: number; searchable?: boolean; searchText?: (item: T) => string; layout?: "block" | "list" | "table" }) {
  const { locale } = useI18n();
  const [query, setQuery] = useState({ value: "", scope: resetKey });
  const search = query.scope === resetKey ? query.value : "";
  const items = supplied || [];
  const filtered = useMemo(() => search.trim() ? items.filter(item => searchText(item).toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())) : items, [items, search, searchText]);
  const paging = usePagination(filtered, { pageSize, resetKey: resetKey + "\u0000" + search, anchorIndex: search ? -1 : anchorIndex });
  const controls = items.length > pageSize || paging.pages > 1 || search ? <Pagination label={label} paging={paging} search={search} onSearch={searchable ? value => setQuery({ value, scope: resetKey }) : undefined} allTotal={items.length} /> : null;
  const empty = search && !filtered.length ? <p className="collection-empty">{locale === "en" ? "No matches. Try another keyword." : "没有匹配项，请调整关键词。"}<Button type="button" onClick={() => setQuery({ value: "", scope: resetKey })}>{locale === "en" ? "Clear search" : "清除搜索"}</Button></p> : null;
  const toolbar = <>{controls}{empty}</>;
  const rendered = children(paging.items, paging.offset);
  if (layout === "table") return <>{rendered}{(controls || empty) && <tr className="collection-control-row"><td colSpan={99}>{toolbar}</td></tr>}</>;
  if (layout === "list") return <>{(controls || empty) && <li className="collection-control-item" role="presentation">{toolbar}</li>}{rendered}</>;
  return <>{toolbar}{rendered}</>;
}
type OptionProps = { value?: string | number; children?: ReactNode; disabled?: boolean; label?: string };
type Option = { value: string; node: ReactElement<OptionProps>; text: string; group?: string };
function nodeText(node: ReactNode): string { return Children.toArray(node).map(child => isValidElement<{ children?: ReactNode }>(child) ? nodeText(child.props.children) : typeof child === "string" || typeof child === "number" ? String(child) : "").join(""); }
export function SearchableSelect({ label, children, searchable = true, filterKey = "", pinnedValue, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { label: ReactNode; searchable?: boolean; filterKey?: string; pinnedValue?: string }) {
  const { locale } = useI18n();
  const en = locale === "en";
  const id = useId();
  const name = nodeText(label).trim();
  const [search, setSearch] = useState("");
  const options: Option[] = [];
  function collect(nodes: ReactNode, group?: string) {
    Children.forEach(nodes, node => {
      if (!isValidElement<OptionProps>(node)) return;
      if (node.type === "option") options.push({ value: String(node.props.value ?? nodeText(node.props.children)), node, text: nodeText(node.props.children), group });
      else collect(node.props.children, node.type === "optgroup" ? node.props.label : group);
    });
  }
  collect(children);
  const placeholders = options.filter(o => o.value === "");
  const available = options.filter(o => o.value !== "" && o.value !== pinnedValue);
  const filtered = available.filter(o => !search.trim() || o.text.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()));
  const paging = usePagination(filtered, { pageSize: 50, resetKey: filterKey + "\u0000" + search });
  const selected = options.find(o => o.value === String(props.value ?? ""));
  const pin = selected && selected.value !== "" && !paging.items.includes(selected);
  const shown = [...placeholders, ...paging.items];
  const groups = new Map<string | undefined, Option[]>();
  shown.forEach(o => groups.set(o.group, [...(groups.get(o.group) || []), o]));
  return <div className="collection-select">
    <label htmlFor={props.id || id}>{label}<select {...props} title={props.title || selected?.text} id={props.id || id}>
      {available.length <= 50 && !search ? children : <>{pin && <optgroup label={en ? "Current selection" : "当前选中（不在本页）"}>{selected.node}</optgroup>}{[...groups].map(([group, rows]) => group ? <optgroup key={group} label={group}>{rows.map((o, i) => cloneElement(o.node, { key: o.node.key ?? o.value + ":" + i }))}</optgroup> : rows.map(o => o.node))}</>}
    </select></label>
    {(available.length > 50 || search) && <Pagination label={name} paging={paging} search={search} onSearch={searchable ? setSearch : undefined} allTotal={available.length} />}
  </div>;
}
