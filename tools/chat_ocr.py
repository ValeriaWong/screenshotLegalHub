"""
来源https://github.com/LANG-ming217/wechat-chat-ocr/blob/master/chat_ocr.py
后进行二次修改

微信聊天截图 OCR 识别工具
========================
功能：自动识别微信聊天截图，提取文字内容，区分说话人，导出 Excel。

识别规则：
  - 右侧绿色气泡 → 角色 A（默认"我"，微信手机主人）
  - 左侧白色气泡 → 角色 B（默认"对方"）
  - 居中灰色文字 → 系统消息

用法：
  python chat_ocr.py <截图目录或文件路径> [--name-a 名字A] [--name-b 名字B]

示例：
  python chat_ocr.py ./screenshots
  python chat_ocr.py ./screenshots --name-a 博饼 --name-b 小美
  python chat_ocr.py chat1.jpg chat2.jpg
"""

import easyocr
import cv2
import numpy as np
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
import os
import sys
import argparse

# ── 颜色 / 样式定义 ──────────────────────────────────────────────

GREEN_FILL = PatternFill(start_color="C8E6C9", end_color="C8E6C9", fill_type="solid")
WHITE_FILL = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
GRAY_FILL  = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

HEADER_FONT  = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
NORMAL_FONT  = Font(name="微软雅黑", size=10)
BOLD_FONT    = Font(name="微软雅黑", size=10, bold=True)
SYSTEM_FONT  = Font(name="微软雅黑", size=9, italic=True, color="888888")

THIN_BORDER = Border(
    left=Side(style="thin", color="D0D0D0"),
    right=Side(style="thin", color="D0D0D0"),
    top=Side(style="thin", color="D0D0D0"),
    bottom=Side(style="thin", color="D0D0D0"),
)

# WeChat 绿色气泡的 HSV 范围
LOWER_GREEN = np.array([35, 30, 60])
UPPER_GREEN = np.array([90, 255, 255])

# 系统消息关键词
SYS_KEYWORDS = [
    "对方已拒绝", "已撤回", "撤回了一条消息",
    "添加", "通过了", "好友",
    "上午", "下午", "中午", "晚上",
]

# ── 检测函数 ──────────────────────────────────────────────────────

def detect_role(bbox, text, img_w, img, img_h):
    """
    判断一条消息的角色。

    策略（优先级从高到低）：
      1. 居中 + 系统关键词 → 系统消息
      2. 检测文字左侧区域的绿色像素 → 绿色气泡 → 角色 A
      3. X 坐标：右侧（>45% 图宽）→ 角色 A，左侧（<35%）→ 角色 B
      4. 模糊地带：绿色 vs 白色像素比分胜负
    """
    x1, y1 = int(bbox[0][0]), int(bbox[0][1])
    x2, y2 = int(bbox[2][0]), int(bbox[2][1])
    x_center = (x1 + x2) / 2
    rel_x = x_center / img_w

    # ── 系统消息 ──
    if 0.25 < rel_x < 0.75:
        for kw in SYS_KEYWORDS:
            if kw in text:
                return "系统"

    # ── 颜色检测：文字左侧 30~150px 范围内采样 ──
    green_score = 0.0
    white_score = 0.0

    for offset_x in [30, 60, 90, 120, 150]:
        cx1 = x1 - offset_x
        cx2 = x1 - offset_x + 20
        cy1, cy2 = max(0, y1), min(img_h, y2)
        if cx1 < 0 or cx2 <= cx1:
            continue
        roi = img[cy1:cy2, cx1:cx2]
        if roi.size == 0:
            continue
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        g_mask = cv2.inRange(hsv, LOWER_GREEN, UPPER_GREEN)
        green_score = max(green_score, np.sum(g_mask > 0) / g_mask.size)

        w_mask = cv2.inRange(hsv, np.array([0, 0, 200]), np.array([180, 30, 255]))
        white_score = max(white_score, np.sum(w_mask > 0) / w_mask.size)

    # ── 判定 ──
    if green_score > 0.08:
        return "A"

    if rel_x > 0.45:
        return "A"
    elif rel_x < 0.35:
        return "B"

    return "A" if green_score > white_score else "B"


# ── 主流程 ─────────────────────────────────────────────────────────

def process_images(image_paths, name_a="我", name_b="对方"):
    """
    处理一组截图，返回结构化的消息列表。

    参数：
      image_paths : 图片路径列表
      name_a      : 角色 A 的显示名称（右侧绿泡）
      name_b      : 角色 B 的显示名称（左侧白泡）

    返回：
      [ { "sheet_name": ..., "messages": [ { "text", "y", "role", "conf" }, ... ] }, ... ]
    """
    reader = easyocr.Reader(['ch_sim'], gpu=False)
    all_chats = []

    for img_path in image_paths:
        print(f"  OCR 识别: {os.path.basename(img_path)} ...")
        img = cv2.imread(img_path)
        if img is None:
            print(f"    ⚠ 无法读取，跳过")
            continue
        h, w = img.shape[:2]

        result = reader.readtext(img_path, detail=1)

        messages = []
        for bbox, text, conf in result:
            text = text.strip()
            if not text:
                continue

            role = detect_role(bbox, text, w, img, h)
            y_center = (bbox[0][1] + bbox[2][1]) / 2

            messages.append({
                "text": text,
                "y": y_center,
                "role": role,
                "conf": conf,
            })

        # 按 Y 坐标排序（从上到下 = 时间顺序）
        messages.sort(key=lambda m: m["y"])

        # 合并同一角色相邻的短消息（OCR 拆分补偿）
        merged = []
        for m in messages:
            if merged and merged[-1]["role"] == m["role"] and m["y"] - merged[-1]["y"] < 40:
                merged[-1]["text"] += "\n" + m["text"]
            else:
                merged.append(m)

        # 角色名映射
        role_map = {"A": name_a, "B": name_b, "系统": "系统"}
        for m in merged:
            m["role_display"] = role_map.get(m["role"], m["role"])

        # Sheet 名称：取文件名（去扩展名）
        sheet_name = os.path.splitext(os.path.basename(img_path))[0][:31]
        all_chats.append({
            "sheet_name": sheet_name,
            "messages": merged,
        })

        print(f"    ✓ {len(merged)} 条消息  |  {name_a}: {sum(1 for m in merged if m['role']=='A')}  |  {name_b}: {sum(1 for m in merged if m['role']=='B')}  |  系统: {sum(1 for m in merged if m['role']=='系统')}")

    return all_chats


def save_excel(all_chats, output_path, name_a="我", name_b="对方"):
    """将处理结果保存为 Excel 文件。"""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    for chat in all_chats:
        ws = wb.create_sheet(title=chat["sheet_name"])

        ws.column_dimensions['A'].width = 8
        ws.column_dimensions['B'].width = 14
        ws.column_dimensions['C'].width = 75
        ws.column_dimensions['D'].width = 12

        headers = ["序号", "角色", "消息内容", "备注"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = THIN_BORDER

        ws.freeze_panes = "A2"

        for i, msg in enumerate(chat["messages"], 2):
            values = [i - 1, msg["role_display"], msg["text"], ""]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=i, column=col, value=val)
                cell.border = THIN_BORDER
                cell.alignment = Alignment(
                    horizontal="center" if col in (1, 2) else "left",
                    vertical="center",
                    wrap_text=True,
                )

                if msg["role"] == "A":
                    if col in (2, 3):
                        cell.fill = GREEN_FILL
                elif msg["role"] == "系统":
                    if col in (2, 3):
                        cell.fill = GRAY_FILL
                        cell.font = SYSTEM_FONT

                if col == 2:
                    cell.font = BOLD_FONT

    wb.save(output_path)
    print(f"\n  Excel 已保存 → {output_path}")


def save_txt(all_chats, output_dir):
    """同时保存纯文本版（带角色标记）。"""
    os.makedirs(output_dir, exist_ok=True)
    for chat in all_chats:
        txt_path = os.path.join(output_dir, f"{chat['sheet_name']}.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            for m in chat["messages"]:
                f.write(f"[{m['role_display']}] {m['text']}\n")


# ── CLI ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="微信聊天截图 OCR 识别 —— 提取文字、区分说话人、导出 Excel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python chat_ocr.py ./screenshots
  python chat_ocr.py chat1.jpg chat2.jpg --name-a 博饼 --name-b 小美
  python chat_ocr.py ./screenshots -a 小明 -b 小红 -o result.xlsx
        """,
    )
    parser.add_argument("inputs", nargs="+", help="截图文件路径 或 包含截图的目录")
    parser.add_argument("--name-a", "-a", default="我",
                        help="角色 A 的名称（右侧绿色气泡，默认: '我'）")
    parser.add_argument("--name-b", "-b", default="对方",
                        help="角色 B 的名称（左侧白色气泡，默认: '对方'）")
    parser.add_argument("--output", "-o", default=None,
                        help="输出 Excel 路径（默认: 输入目录下 '聊天记录分析.xlsx'）")
    parser.add_argument("--no-txt", action="store_true",
                        help="不生成纯文本文件")
    args = parser.parse_args()

    # 收集图片路径
    image_paths = []
    for inp in args.inputs:
        if os.path.isdir(inp):
            for f in sorted(os.listdir(inp)):
                fp = os.path.join(inp, f)
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp')):
                    image_paths.append(fp)
        elif os.path.isfile(inp):
            image_paths.append(inp)
        else:
            print(f"⚠ 路径不存在，跳过: {inp}")

    if not image_paths:
        print("❌ 没有找到任何图片文件。")
        sys.exit(1)

    print("=" * 56)
    print("  微信聊天截图 OCR 识别")
    print(f"  绿泡(右) → {args.name_a}  |  白泡(左) → {args.name_b}  |  灰字 → 系统")
    print(f"  共 {len(image_paths)} 张截图")
    print("=" * 56)

    # OCR + 识别
    chats = process_images(image_paths, name_a=args.name_a, name_b=args.name_b)

    # 输出路径
    if args.output:
        xlsx_path = args.output
    else:
        # 默认放到第一张图所在目录
        base_dir = os.path.dirname(image_paths[0]) or "."
        xlsx_path = os.path.join(base_dir, "聊天记录分析.xlsx")

    save_excel(chats, xlsx_path, name_a=args.name_a, name_b=args.name_b)

    if not args.no_txt:
        txt_dir = os.path.join(os.path.dirname(xlsx_path) or ".", "ocr_output")
        save_txt(chats, txt_dir)
        print(f"  TXT 已保存 → {txt_dir}/")

    print("\n✓ 完成!")


if __name__ == "__main__":
    main()