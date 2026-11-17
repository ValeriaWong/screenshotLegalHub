import { connectionState, modelChecks, orderModels, type ConnectionState, type TestOverrides } from "./modelConnectivity";
import { Paged } from "../../components/collections";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ModelConfig, type ConnectivityResult, type ConnectivityImage } from "../../api/client";
import { Button, Card, Input, Badge } from "../../components/ui";
import { Feedback } from "../../components/feedback";
import { useI18n } from "../../i18n";

const stateTone = { connected: "success", partial: "success", untested: "neutral", failed: "danger", disabled: "warning" } as const;
const stateLabel = { connected: "connectionAllPassed", partial: "connectionPartPassed", untested: "connectionUntested", failed: "connectionTestFailed", disabled: "connectionNotEnabled" } as const satisfies Record<ConnectionState, string>;
const empty = { request_timeout_seconds: "90", request_total_timeout_seconds: "", max_output_tokens: "", input_token_price: "", output_token_price: "", price_currency: "CNY" as "CNY" | "USD", name: "", base_url: "", model_name: "", api_key: "", supports_vision: true, allow_external_egress: false };
export function ModelSettings() {
  const { t } = useI18n();
  const client = useQueryClient();
  const q = useQuery({ queryKey: ["models"], queryFn: () => api<ModelConfig[]>("/settings/models") });
  const sample = useQuery({ queryKey: ["connectivity-image"], queryFn: () => api<ConnectivityImage | null>("/settings/test-image") });
  const [editing, setEditing] = useState("");
  const [form, setForm] = useState(empty);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [tests, setTests] = useState<TestOverrides>({});
  const [testing, setTesting] = useState("");
  const [testFocus, setTestFocus] = useState({ id: "", revision: 0 });
  const ordered = orderModels(q.data || [], tests, testing);
  function clearTest(id: string) {
    setTests(current => { const next = { ...current }; delete next[id + ":text"]; delete next[id + ":image"]; return next; });
  }
  async function action(fn: () => Promise<unknown>) {
    setBusy(true); setError("");
    try { await fn(); await client.invalidateQueries({ queryKey: ["models"] }); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  async function runTest(model: ModelConfig, mode: "text" | "image") {
    const key = model.id + ":" + mode;
    setTests(current => ({ ...current, [key]: null }));
    setTesting(key); setBusy(true); setError("");
    try {
      const body = mode === "image" ? { mode, case_id: sample.data?.case_id, evidence_id: sample.data?.evidence_id } : {};
      const result = await api<ConnectivityResult>("/settings/models/" + model.id + "/test", body);
      setTests(current => ({ ...current, [key]: result }));
      await client.invalidateQueries({ queryKey: ["models"] });
    } catch (e) {
      setTests(current => ({ ...current, [key]: { success: false, mode, latency_ms: 0, message: t("connectionRequestFailed") } }));
      setError(String(e));
    } finally {
      setTesting(""); setBusy(false);
      setTestFocus(current => ({ id: model.id, revision: current.revision + 1 }));
    }
  }
  return <>
    <p>这里连接模型服务。已有可用配置时，直接在生成或评测页面选择模型即可；不熟悉服务地址和密钥时，请由配置维护人员填写。</p><details><summary>连接配置说明</summary><p>{t("modelSettingsNotice")}</p></details>
    {sample.isPending ? <p>{t("loading")}</p> : sample.error ? <Feedback state="error" error={sample.error.message} /> : sample.data ?
      <p>{t("imageTestSample")}: <a href={"/v1/cases/" + sample.data.case_id + "/evidence/" + sample.data.evidence_id + "/file"} target="_blank" rel="noreferrer">{sample.data.case_title} · {sample.data.filename}</a></p>
      : <p>{t("noTestImage")}</p>}
    <Card><h2>{t(editing ? "editModel" : "addModel")}</h2>
      <form className="settings-form" onInvalidCapture={event => { const parent = (event.target as HTMLElement).closest("details"); if (parent) parent.open = true; }} onSubmit={event => {
        event.preventDefault(); void action(async () => {
          await api(editing ? `/settings/models/${editing}` : "/settings/models", { ...form, request_timeout_seconds: Number(form.request_timeout_seconds || 90), request_total_timeout_seconds: form.request_total_timeout_seconds ? Number(form.request_total_timeout_seconds) : null, max_output_tokens: form.max_output_tokens ? Number(form.max_output_tokens) : null, input_token_price: form.input_token_price === "" ? null : Number(form.input_token_price), output_token_price: form.output_token_price === "" ? null : Number(form.output_token_price), api_key: form.api_key || null }, editing ? "PUT" : "POST");
          if (editing) clearTest(editing);
          setForm(empty); setEditing("");
        });
      }}>
        <label>{t("configurationName")}<Input required maxLength={100} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></label>
        <label>{t("baseUrl")}<Input required type="url" placeholder="https://provider.example/v1" value={form.base_url} onChange={e => setForm({ ...form, base_url: e.target.value })} /></label>
        <label>{t("modelName")}<Input required value={form.model_name} onChange={e => setForm({ ...form, model_name: e.target.value })} /></label>
        <label>API Key<Input type="password" autoComplete="off" required={!editing} placeholder={editing ? t("keepKey") : ""} value={form.api_key} onChange={e => setForm({ ...form, api_key: e.target.value })} /></label>
        <details><summary>高级：等待模型的时间</summary><p>单阶段等待指连接或读写没有响应时最多等多久，不是整轮任务时长。单次总时长包含整个调用，留空不另设总时限。超时不能证明服务已停止或没有计费。</p><label>无响应等待时间（秒）<Input type="number" min={1} max={3600} step={1} value={form.request_timeout_seconds} onChange={e => setForm({ ...form, request_timeout_seconds: e.target.value })} /></label><label>单次调用总时长（秒，可选）<Input type="number" min={1} max={86400} step={1} placeholder="留空不另设总时限" value={form.request_total_timeout_seconds} onChange={e => setForm({ ...form, request_total_timeout_seconds: e.target.value })} /></label></details>
        <label>输出 token 上限（可选）<Input type="number" min={1} step={1} placeholder="留空不发送上限" value={form.max_output_tokens} onChange={e => setForm({ ...form, max_output_tokens: e.target.value })} /></label>
        <label>输入单价（每百万 token）<Input type="number" min={0} step="any" placeholder="留空为未知，0为免费" value={form.input_token_price} onChange={e => setForm({ ...form, input_token_price: e.target.value })} /></label>
        <label>输出单价（每百万 token）<Input type="number" min={0} step="any" placeholder="留空为未知，0为免费" value={form.output_token_price} onChange={e => setForm({ ...form, output_token_price: e.target.value })} /></label>
        <label>计价币种<select value={form.price_currency} onChange={e => setForm({ ...form, price_currency: e.target.value as "CNY" | "USD" })}><option value="CNY">CNY</option><option value="USD">USD</option></select></label>
        <p className="research-hint">Token 是模型处理内容的计量单位，不等同于字数。输出上限留空时沿用服务默认；不确定时可先留空。单价请按服务报价填写，未知不代表免费。修改配置不会改变已保存的调用记录。</p>
        <label><Input type="checkbox" checked={form.supports_vision} onChange={e => setForm({ ...form, supports_vision: e.target.checked })} />{t("visionCapable")}</label>
        <label><Input type="checkbox" checked={form.allow_external_egress} onChange={e => setForm({ ...form, allow_external_egress: e.target.checked })} />{t("allowModelRequests")}</label>
        <div className="toolbar"><Button disabled={busy}>{t("save")}</Button>{editing && <Button type="button" onClick={() => { setEditing(""); setForm(empty); }}>{t("cancel")}</Button>}</div>
      </form>
    </Card>
    <p className="research-hint">{t("modelConnectionOrder")}</p>
    {error && <Feedback state="error" error={error} />}
    {q.isPending ? <Feedback state="loading" /> : q.error ? <Feedback state="error" error={q.error.message} /> : !q.data.length ? <p>{t("noModels")}</p> : <Paged items={ordered} label="模型配置" layout="block" resetKey={String(testFocus.revision)} anchorIndex={ordered.findIndex(model => model.id === testFocus.id)}>{(pageItems) => pageItems.map(model => <Card key={model.id}>
      <div className="model-connection-heading" data-model-id={model.id} data-connection={testing.startsWith(model.id + ":") ? "testing" : connectionState(model, tests)}>
        <h2>{model.name} {model.is_default && <Badge>{t("defaultModel")}</Badge>}</h2>
        <Badge tone={testing.startsWith(model.id + ":") ? "info" : stateTone[connectionState(model, tests)]}>{t(testing.startsWith(model.id + ":") ? "connectionChecking" : stateLabel[connectionState(model, tests)])}</Badge>
      </div>
      <div className="model-connection-capabilities">
        {(["text", "image"] as const).filter(mode => mode === "text" || model.supports_vision).map(mode => {
          const check = modelChecks(model, tests)[mode];
          const pending = testing === model.id + ":" + mode;
          return <Badge key={mode} tone={pending ? "info" : check ? check.success ? "success" : "danger" : "neutral"}>{t(pending ? mode === "text" ? "textConnectionChecking" : "imageConnectionChecking" : check ? check.success ? mode === "text" ? "textConnectionPassed" : "imageConnectionPassed" : mode === "text" ? "textConnectionFailed" : "imageConnectionFailed" : mode === "text" ? "textConnectionUntested" : "imageConnectionUntested")}</Badge>;
        })}
      </div>
      <p>{model.base_url} · {model.model_name}</p><p>输出上限：{model.max_output_tokens ?? "未设置"} · 输入/输出单价：{model.input_token_price ?? "未知"} / {model.output_token_price ?? "未知"} {model.price_currency || "CNY"} / 百万 token</p><p>无响应等待：{model.request_timeout_seconds ?? 90} 秒 · 单次总时限：{model.request_total_timeout_seconds == null ? "未另设" : model.request_total_timeout_seconds + " 秒"}</p><p>{t(model.has_api_key ? "keySaved" : "keyMissing")} · {t(model.supports_vision ? "visionCapable" : "textModel")}</p>
      <div className="toolbar">
        <Button disabled={busy} onClick={() => { setEditing(model.id); setForm({ request_timeout_seconds: String(model.request_timeout_seconds ?? 90), request_total_timeout_seconds: model.request_total_timeout_seconds?.toString() ?? "", name: model.name, base_url: model.base_url, model_name: model.model_name, api_key: "", max_output_tokens: model.max_output_tokens?.toString() || "", input_token_price: model.input_token_price?.toString() ?? "", output_token_price: model.output_token_price?.toString() ?? "", price_currency: model.price_currency || "CNY", supports_vision: model.supports_vision, allow_external_egress: model.allow_external_egress }); }}>{t("editModel")}</Button>
        <Button disabled={busy || model.is_default} onClick={() => action(() => api("/settings/default-model", { model_id: model.id }, "PUT"))}>{t("useDefault")}</Button>
        <Button disabled={busy || !model.allow_external_egress || !model.has_api_key} onClick={() => runTest(model, "text")}>{t("testConnection")}</Button>
        <Button disabled={busy || !model.allow_external_egress || !model.has_api_key || !model.supports_vision || !sample.data?.evidence_id} onClick={() => runTest(model, "image")}>{t("testImageConnection")}</Button>
        <Button disabled={busy} onClick={() => { if (window.confirm(t("deleteModelConfirm"))) void action(async () => { await api(`/settings/models/${model.id}`, {}, "DELETE"); if (editing === model.id) { setEditing(""); setForm(empty); } }); }}>{t("deleteModel")}</Button>
      </div>
      {!model.allow_external_egress && <p>{t("requestsDisabled")}</p>}
      {(["text", "image"] as const).map(mode => {
        const key = model.id + ":" + mode;
        const result = tests[key];
        return <div key={mode}>
          {testing === key && <p role="status">{t(mode === "text" ? "textProbe" : "imageProbe")} · {t("testingConnection")}</p>}
          {result && <p role={result.success ? "status" : "alert"}>{t(mode === "text" ? "textProbe" : "imageProbe")} · {t(result.success ? "connectionOk" : "connectionFailed")} · {result.latency_ms} ms · {result.message}</p>}
        </div>;
      })}
    </Card>)}</Paged>}
  </>;
}
