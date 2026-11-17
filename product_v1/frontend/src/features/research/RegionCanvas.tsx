import { useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { Button, Input } from "../../components/ui";
type Box = number[];
interface Props {
  detail: { asset_url: string; task: { asset: { width: number; height: number } }; regions: { id: string; bbox: number[]; label: string }[]; legacy_match: { best_msg: { bbox: number[] } | null } | null };
  bbox: Box | null; locked: boolean; change: (box: Box | null) => void; edit: () => void;
}
export function RegionCanvas({ detail, bbox, locked, change, edit }: Props) {
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef<{ x: number; y: number; box: Box; corner: number } | null>(null);
  const [zoom, setZoom] = useState(100), [showPrediction, setShowPrediction] = useState(true), [showOthers, setShowOthers] = useState(true), [failed, setFailed] = useState(false);
  const [undo, setUndo] = useState<(Box | null)[]>([]), [redo, setRedo] = useState<(Box | null)[]>([]);
  const { width, height } = detail.task.asset;
  function commit(box: Box | null) { setUndo(v => [...v.slice(-49), bbox ? [...bbox] : null]); setRedo([]); change(box); }
  const point = (e: ReactPointerEvent) => { const r = svg.current!.getBoundingClientRect(); return [(e.clientX - r.left) * width / r.width, (e.clientY - r.top) * height / r.height]; };
  function start(e: ReactPointerEvent<SVGElement>, corner: number) {
    if (locked || !bbox) return;
    e.preventDefault(); e.currentTarget.setPointerCapture(e.pointerId);
    setUndo(v => [...v.slice(-49), [...bbox]]); setRedo([]);
    const [x, y] = point(e); drag.current = { x, y, box: [...bbox], corner };
  }
  function move(e: ReactPointerEvent) {
    const d = drag.current; if (!d || locked) return;
    const [x, y] = point(e), dx = x - d.x, dy = y - d.y, b = [...d.box];
    if (d.corner < 0) { const sx = Math.max(-b[0], Math.min(width - b[2], dx)), sy = Math.max(-b[1], Math.min(height - b[3], dy)); b[0] += sx; b[2] += sx; b[1] += sy; b[3] += sy; }
    else { const xi = d.corner === 0 || d.corner === 3 ? 0 : 2, yi = d.corner < 2 ? 1 : 3; b[xi] = Math.max(0, Math.min(width, d.box[xi] + dx)); b[yi] = Math.max(0, Math.min(height, d.box[yi] + dy)); }
    if (b[2] > b[0] && b[3] > b[1]) change(b);
  }
  const pred = showPrediction ? detail.legacy_match?.best_msg?.bbox : null;
  return <section aria-label="原图标注工具">
    <div className="toolbar">
      <label>图片缩放<select value={zoom} onChange={e => setZoom(Number(e.target.value))}>{[50,100,150,200,300].map(v => <option key={v} value={v}>{v === 100 ? "适应宽度" : v + "%"}</option>)}</select></label>
      <a href={detail.asset_url} target="_blank" rel="noreferrer">打开原图</a>
      <Button disabled={locked || !undo.length} onClick={() => { const previous = undo.at(-1)!; setRedo(v => [...v, bbox]); setUndo(v => v.slice(0,-1)); change(previous); }}>撤销坐标</Button>
      <Button disabled={locked || !redo.length} onClick={() => { const next = redo.at(-1)!; setUndo(v => [...v, bbox]); setRedo(v => v.slice(0,-1)); change(next); }}>重做坐标</Button>
      {!bbox && <Button disabled={locked} onClick={() => commit([width * .1, height * .1, width * .9, height * .4])}>添加参考框</Button>}
      {bbox && <Button disabled={locked} onClick={() => commit(null)}>清除参考框</Button>}
    </div>
    <label className="research-check"><Input type="checkbox" checked={showOthers} onChange={e => setShowOthers(e.target.checked)} />显示同图旧区域（灰色）</label>
    <label className="research-check"><Input type="checkbox" checked={showPrediction} onChange={e => setShowPrediction(e.target.checked)} />显示旧模型匹配框（绿色，仅供对照）</label>
    {failed && <p role="alert">原图加载失败，请重新打开任务或检查原图链接。</p>}
    <div className="benchmark-image-scroll" tabIndex={0} aria-label="可滚动缩放的原图">
      <svg ref={svg} viewBox={"0 0 " + width + " " + height} role="img" aria-label="原始截图与参考坐标框" style={{ width: zoom + "%", maxWidth: "none", height: "auto", touchAction: locked ? "auto" : "none", display: "block" }} onPointerMove={move} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
        <image href={detail.asset_url} width={width} height={height} onError={() => setFailed(true)} />
        {showOthers && detail.regions.filter(r => r.bbox?.length === 4).map(r => <rect key={r.id} x={r.bbox[0]} y={r.bbox[1]} width={r.bbox[2]-r.bbox[0]} height={r.bbox[3]-r.bbox[1]} fill="none" stroke="var(--muted)" strokeWidth={2} />)}
        {pred && <rect x={pred[0]} y={pred[1]} width={pred[2]-pred[0]} height={pred[3]-pred[1]} fill="none" stroke="var(--success)" strokeWidth={5} strokeDasharray="12 8" />}
        {bbox && <><rect role="button" tabIndex={0} onClick={() => { if (locked) edit(); }} onKeyDown={e => { if (["Enter"," "].includes(e.key)) { e.preventDefault(); edit(); } }} aria-label="当前参考框，点击编辑目标文本" x={bbox[0]} y={bbox[1]} width={bbox[2]-bbox[0]} height={bbox[3]-bbox[1]} fill="var(--bbox-fill)" stroke="var(--warning)" strokeWidth={5} style={{ cursor: locked ? "pointer" : "move" }} onPointerDown={e => start(e,-1)} />
          {!locked && [[bbox[0],bbox[1]],[bbox[2],bbox[1]],[bbox[2],bbox[3]],[bbox[0],bbox[3]]].map(([x,y],i) => <rect aria-label={"拖动参考框角点"+(i+1)} key={i} x={x-12} y={y-12} width={24} height={24} fill="var(--warning)" onPointerDown={e => start(e,i)} />)}</>}
      </svg>
    </div>
    {bbox && <fieldset disabled={locked}><legend>参考框像素坐标（也可直接输入）</legend><div className="benchmark-coordinates">{["左","上","右","下"].map((name,i) => <label key={name}>{name}<Input type="number" min={0} max={i%2 ? height : width} step="any" value={Math.round(bbox[i]*100)/100} onChange={e => { const b=[...bbox]; b[i]=Number(e.target.value); if (b[0]>=0 && b[1]>=0 && b[2]<=width && b[3]<=height && b[2]>b[0] && b[3]>b[1]) commit(b); }} /></label>)}</div></fieldset>}
    <p>灰色：同图旧区域；橙色：当前参考；绿色：旧模型匹配。坐标以原图像素保存，缩放不改变坐标。</p>
  </section>;
}
