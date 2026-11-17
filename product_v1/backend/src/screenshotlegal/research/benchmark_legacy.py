"""Frozen legacy association IoU; imported pure helpers only, no entrypoint execution.
Source SHA: bbb34af7225b3bbcc0cdf4abe8c1845930fcb59fbfe2cf84c8630412bda8385e. New validation lives separately.
"""
import json,os,re,hashlib,mimetypes,base64
from pathlib import Path
from typing import Any,Dict,List,Optional,Tuple
from urllib.parse import unquote
def _safe_filename(s: str, maxlen: int = 200) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:maxlen] or "image"

def _tail_from_image_ref(image_ref: str) -> str:
    """
    与 run_infer.py 的 image_tail_from_source 一致：
      - data:… 且带 name= → 用 name（URL 解码后再 sanitize）
      - 普通 URL/本地路径 → basename
      - data:… 无 name= → dataurl_<sha1前16位>.<ext>
    """
    if not isinstance(image_ref, str) or not image_ref:
        return ""
    ref = image_ref.strip()

    if ref.startswith("data:"):  # data URL
        m = re.match(r"data:[^;]+;name=([^;]+);base64,", ref)
        if m:
            try:
                return _safe_filename(unquote(m.group(1)), 200)
            except Exception:
                return _safe_filename(m.group(1), 200)
        # 无 name= → hash 回退
        digest = hashlib.sha1(ref.encode("utf-8")).hexdigest()[:16]
        m2 = re.match(r"data:([\w/+.-]+);base64,", ref)
        subtype = (m2.group(1).split("/")[-1].lower() if m2 else "bin")
        ext = {"jpeg":"jpg","jpg":"jpg","png":"png","webp":"webp","gif":"gif","bmp":"bmp","heic":"heic"}.get(subtype, subtype)
        return f"dataurl_{digest}.{ext}"

    # 普通 URL 或本地路径
    try:
        name = os.path.basename(ref.split("?", 1)[0])
        return _safe_filename(name, 200)
    except Exception:
        return "image"

def _file_to_data_url_str(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    mime = mime or "application/octet-stream"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def _legacy_tail_for_file(path: str) -> str:
    """计算该文件对应的 dataurl_<sha1>.<ext>（与 run_infer 保持一致）"""
    data_url = _file_to_data_url_str(path)
    digest = hashlib.sha1(data_url.encode("utf-8")).hexdigest()[:16]
    mime, _ = mimetypes.guess_type(path)
    subtype = (mime or "application/octet-stream").split("/")[-1].lower()
    ext = {"jpeg":"jpg","jpg":"jpg","png":"png","webp":"webp","gif":"gif","bmp":"bmp","heic":"heic"}.get(subtype, subtype)
    return f"dataurl_{digest}.{ext}"

def parse_structured_info(si: Any) -> Optional[Dict[str, Any]]:
    """
    structured_info 可能是字符串或字典；尽力解析成 dict。
    """
    if si is None:
        return None
    if isinstance(si, dict):
        return si
    if isinstance(si, str):
        text = si.strip().strip("`").strip()
        if "{" in text and "}" in text:
            text = text[text.find("{"): text.rfind("}")+1]
        try:
            return json.loads(text)
        except Exception:
            return None
    return None

def to_box_from_msg(b: Dict[str, Any]) -> Optional[Tuple[float,float,float,float]]:
    """
    将 message_bbox 的 {min_x, max_x, min_y, max_y} 转为 (x1,y1,x2,y2)
    """
    need = ("min_x","max_x","min_y","max_y")
    if not all(k in b for k in need):
        return None
    try:
        x1 = float(b["min_x"])
        x2 = float(b["max_x"])
        y1 = float(b["min_y"])
        y2 = float(b["max_y"])
    except Exception:
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)

def to_box_from_rect(x: Any, y: Any, w: Any, h: Any) -> Optional[Tuple[float,float,float,float]]:
    """
    将 rectTool 的 (x,y,width,height) 转为 (x1,y1,x2,y2)，假设 x,y 为左上角。
    """
    try:
        x = float(x); y = float(y); w = float(w); h = float(h)
    except Exception:
        return None
    if w <= 0 or h <= 0:
        return None
    return (x, y, x + w, y + h)

def iou_xyxy(a: Tuple[float,float,float,float], b: Tuple[float,float,float,float]) -> float:
    """
    (x1,y1,x2,y2) 盒子的 IoU
    """
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1); iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2); iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    if area_a <= 0 or area_b <= 0:
        return 0.0
    return inter / (area_a + area_b - inter + 1e-9)

def load_structured(struct_json: str, alias_map: Optional[Dict[str, str]] = None) -> Dict[str, List[Dict[str, Any]]]:

    """
    读取 structured_json（兼容两种输入）并构建：
      msgs_by_image[<basename>] = [ { idx, timestamp, speaker, content, bbox: (x1,y1,x2,y2) }, ... ]

    兼容的两类输入：
    A) 旧格式：list，每项包含 image_url/image_path + structured_info（str或dict）
       [
         {"image_url": ".../xxx.jpg", "structured_info": "{...}"},
         ...
       ]

    B) 新格式：dict，含 items[]，每项包含 image_tail + response（```json 包裹）
       {
         "timestamp": "...",
         "task_ids": [...],
         "model": "...",
         "items": [
           { "image_tail": "dataurl_xxx.jpg", "response": "```json\n{...}\n```" },
           ...
         ]
       ]
    """
    alias_map = alias_map or {}
    p = Path(struct_json)
    if not p.exists():
        raise SystemExit(f"找不到 structured_json：{struct_json}")

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"读取/解析 structured_json 失败：{e}")

    msgs_by_image: Dict[str, List[Dict[str, Any]]] = {}

    def _push(tail: str, si: Optional[Dict[str, Any]]):

        if not tail or not si:
            return
        # 短尾 → 原始文件名
        key = alias_map.get(tail, tail)
        conv = si.get("conversation")
        if not isinstance(conv, list):
            return

        lst: List[Dict[str, Any]] = []
        for i, msg in enumerate(conv):
            if not isinstance(msg, dict):
                continue
            bbox = msg.get("message_bbox")
            if not isinstance(bbox, dict):
                continue
            box = to_box_from_msg(bbox)
            if not box:
                continue
            lst.append({
                "idx": i,
                "timestamp": msg.get("timestamp"),
                "speaker": msg.get("speaker"),
                "content": msg.get("content"),
                "bbox": box,
                "raw_bbox": bbox,
            })
        if lst:
            # 关键点：这里用 basename 作为 key，便于与 rect 的 image_tail_norm 匹配
            # msgs_by_image[os.path.basename(fname)] = lst
            msgs_by_image[key] = lst

    # --- 分支 A：旧格式（list） ---
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            tail = item.get("image_tail") or _tail_from_image_ref(item.get("image_url") or item.get("image_path") or "")
            si = parse_structured_info(item.get("structured_info") or item.get("response") or item.get("output"))
            _push(tail, si)
        return msgs_by_image
        #     # 兼容 image_url / image_path / image_tail
        #     image_ref = (item.get("image_url") or
        #                  item.get("image_path") or
        #                  item.get("image_tail") or "")
        #     # 兼容 structured_info / response / output
        #     si = parse_structured_info(item.get("structured_info") or
        #                                item.get("response") or
        #                                item.get("output"))
        #     _push(image_ref, si)
        # return msgs_by_image

    # --- 分支 B：新格式（dict + items[]） ---
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        for it in data["items"]:
            if not isinstance(it, dict):
                continue
            # 新格式里图片标识主要来自 image_tail；也兜底 image_url/image_path
            # image_ref = (it.get("image_tail") or
            #              it.get("image_url") or
            #              it.get("image_path") or "")
            tail = it.get("image_tail")
            if not tail:  # 兜底尝试从 image_url/image_path 反推
                tail = _tail_from_image_ref(it.get("image_url") or it.get("image_path") or "")
            si = parse_structured_info(it.get("structured_info") or it.get("response") or it.get("output"))
            _push(tail, si)
        return msgs_by_image

    raise SystemExit("structured_json 的顶层结构不被支持（既不是 list，也不是含 items[] 的 dict）。")

def load_rects(rect_json: str) -> List[Dict[str, Any]]:
    """
    读取 extracted_all_rect_attrs.json 并返回仅 rectTool 的条目：
      {
        "image_tail_norm": "<basename>",  # 取 split("-",1)[1]；若没有 '-' 则原值
        "orig_image_tail": "<原始 image_tail>",
        "label": "...",
        "answer": "...",
        "bbox": (x1,y1,x2,y2),
        "raw": <原始字典>
      }
    """
    p = Path(rect_json)
    if not p.exists():
        raise SystemExit(f"找不到 rect_json：{rect_json}")

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"读取/解析 rect_json 失败：{e}")

    if not isinstance(data, list):
        raise SystemExit("rect_json 不是 list。")

    out: List[Dict[str, Any]] = []
    for rec in data:
        if (rec or {}).get("tool") != "rectTool":
            continue
        img_tail = (rec or {}).get("image_tail", "")
        if not img_tail:
            continue
        if "-" in img_tail:
            tail_norm = img_tail.split("-", 1)[1]
        else:
            tail_norm = img_tail

        box = to_box_from_rect(rec.get("x"), rec.get("y"), rec.get("width"), rec.get("height"))
        if not box:
            continue

        out.append({
            "image_tail_norm": tail_norm,
            "orig_image_tail": img_tail,
            "label": rec.get("label"),
            "answer": rec.get("answer"),
            "bbox": box,
            "raw": rec
        })
    return out

def compute_best_matches(
    rects: List[Dict[str, Any]],
    msgs_by_image: Dict[str, List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    对每个 rectTool，在同一图片里与所有消息 bbox 计算 IoU，拿到最佳匹配。
    返回每条 rect 的明细：
      {
        "image": "<basename>",
        "label": "...",
        "answer": "...",
        "rect_bbox": (x1,y1,x2,y2),
        "best_iou": float,
        "best_msg": { idx, timestamp, speaker, content, bbox, raw_bbox } 或 None,
        "no_message": True/False  # 该图像是否没有任何消息框
      }
    """
    details: List[Dict[str, Any]] = []
    for r in rects:
        img = r["image_tail_norm"]
        rect_box = r["bbox"]
        label = r.get("label")
        answer = r.get("answer")

        msgs = msgs_by_image.get(img, [])
        if msgs==[]:
            details.append({
                "image": img,
                "label": label,
                "answer": answer,
                "rect_bbox": rect_box,
                "best_iou": 0.0,
                "best_msg": None,
                "no_message": True,
                "orig_image_tail": r.get("orig_image_tail")
            })
            continue

        best_iou = 0.0
        best_msg = None
        for m in msgs:
            i = iou_xyxy(rect_box, m["bbox"])
            if i > best_iou:
                best_iou = i
                best_msg = m

        details.append({
            "image": img,
            "label": label,
            "answer": answer,
            "rect_bbox": rect_box,
            "best_iou": float(best_iou),
            "best_msg": best_msg,
            "no_message": False,
            "orig_image_tail": r.get("orig_image_tail")
        })
    return details
