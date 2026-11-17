/** Geometry bridge to LabelU-Kit RectData, not a full LabelU project backup. */
export interface LabelURect { id: string; type: "rect"; label: string; x: number; y: number; width: number; height: number; attributes: Record<string, unknown> }
export interface LabelUExchange { schema: "screenshotlegal.labelu-rect.v1"; image: { sha256: string; width: number; height: number }; annotations: LabelURect[]; question: string; target: unknown }
export function exportLabelU(image: LabelUExchange["image"], bbox: number[] | null, question: string, target: unknown, label: string): LabelUExchange {
  return { schema:"screenshotlegal.labelu-rect.v1",image,annotations:bbox ? [{id:"current-reference",type:"rect",label,x:bbox[0],y:bbox[1],width:bbox[2]-bbox[0],height:bbox[3]-bbox[1],attributes:{}}] : [],question,target };
}
export function importLabelU(raw: unknown, image: LabelUExchange["image"]) {
  if (!raw || typeof raw!=="object") throw new Error("标注文件格式无效");
  const data=raw as LabelUExchange;
  if (data.schema!=="screenshotlegal.labelu-rect.v1" || data.image?.sha256!==image.sha256 || data.image.width!==image.width || data.image.height!==image.height) throw new Error("标注与当前原图哈希或尺寸不匹配，未导入");
  if (!Array.isArray(data.annotations) || data.annotations.length>1) throw new Error("当前任务只接受一个参考框，请先按任务拆分标注");
  const r=data.annotations[0]; let bbox:number[] | null=null;
  if (r) {
    if (r.type!=="rect" || ![r.x,r.y,r.width,r.height].every(Number.isFinite) || r.x<0 || r.y<0 || r.width<=0 || r.height<=0 || r.x+r.width>image.width || r.y+r.height>image.height) throw new Error("矩形必须是原图像素范围内的有效区域");
    bbox=[r.x,r.y,r.x+r.width,r.y+r.height];
  }
  if (typeof data.question!=="string" || !Object.hasOwn(data,"target")) throw new Error("缺少任务问题或目标答案");
  return { bbox, question:data.question, target:data.target };
}
export function downloadLabelU(data: LabelUExchange) {
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"}));
  const a=document.createElement("a");a.href=url;a.download="labelu-reference.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
