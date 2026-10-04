"""Evidence-linked legal review content assembled by the primary agent.

Mechanical source resolution never asserts semantic truth. Root-authored review
notes identify the limits of actual originals; all items await the user's review.
"""
import copy
import hashlib
import json
from legalhub.case_presentation import localized
from legalhub.casework import DEFAULT_CASE

CONTENT_VERSION = "root-legal-review-v1"
CLOTHING_CASES = {DEFAULT_CASE, "case-4028cd97e61b40a7"}

def text(value):
    if isinstance(value, dict):
        return str(value.get("zh", value.get("en", "")))
    return str(value or "")

def paragraphs(*values):
    return "\n\n".join(text(x).strip() for x in values if text(x).strip())

def review_note(kind, key, proposed, quotes, is_clothing):
    """Root-authored verification prompts, not automatic legal determinations."""
    body = text(proposed)
    if kind == "contract_term":
        notes = {
            "parties": ("截图中的昵称与左右气泡不能直接证明原告、被告或付款人的真实身份。请确认当前判断是否保留这一身份缺口。",
                        "A nickname or bubble side does not authenticate the claimant, defendant or payer. Check that the identity gap remains explicit."),
            "goods": ("请核对具体选款是否已经确定，还是展示、推荐或评价；不能把喜欢某款直接写成成交标的。",
                      "Check whether the goods were actually agreed or merely displayed, recommended or liked."),
            "quantity": ("请区分展示顺序与成交数量；“最后一件”不能直接推出只买一件。数量应结合双方完整表示核对。",
                         "Distinguish display order from agreed quantity. “The last item” does not establish a one-item purchase."),
            "specification": ("原文中的材质、规格介绍是发言者陈述。请核对是否对应成交物品及是否需要其他证据佐证。",
                              "A material or specification description is a speaker's statement. Check its link to the agreed goods and need for corroboration."),
            "price": ("请核对报价是否完整可读、双方是否确认；转款2000或“不够再说”不能直接等同于完整合同价款。",
                      "Check that pricing is readable and mutually agreed. A reported 2,000 transfer or possible shortfall does not establish the total price."),
            "payment": ("请把付款方式、称已转款、回复收款、实际到账、付款人身份和是否付清分别核对。",
                        "Distinguish payment method, reported transfer, acknowledgement, settlement, payer identity and full discharge."),
            "delivery": ("请核对是否明确取货或交付。“有人找你”“来找你”不当然是商品交接；付款方式也不是交付方式。",
                         "Check for an explicit collection or delivery arrangement. Contact or a visit does not establish delivery, and payment method is separate."),
            "variation": ("请核对变更或解除是否有明确表示及对应内容；“不够再说”不自动形成确定的追加付款义务。",
                          "Check explicit variation or termination and its scope. Discussing a shortfall does not by itself fix an additional-payment obligation.")
        }
        if is_clothing and key in notes:
            return localized(*notes[key])
        return localized("请将该合同要素逐项对照原文；区分讨论、单方陈述、双方约定和证据缺口。",
                         "Check this term against the originals. Distinguish discussion, unilateral statements, mutual agreement and missing evidence.")
    if any(word in body for word in ("要约", "承诺", "合同成立")):
        return localized("请定位对应的交易内容、受约束意图及回应对象；询价、付款账户或简短回复不能单独证明合同成立。法律适用日期和版本仍需核对。",
                         "Identify the transaction terms, intention to be bound and the proposition being answered. An enquiry, payment account or short reply alone does not establish formation. Check the applicable date and law.")
    if any(word in body for word in ("转账", "转款", "收款", "受领", "给付")):
        return localized("原文可证明发言者作过相应陈述；是否实际到账、款项性质和履行程度，需要分别核对。不要将“收到了”直接扩大为全部清偿。",
                         "The originals support what was said. Settlement, purpose and extent of performance need separate verification. Do not expand an acknowledgement into full discharge.")
    if "授权" in body:
        return localized("请核对授权对象、范围和是否仍保留确认步骤；推荐选款、代付款和代理订约是不同问题。",
                         "Check the authorized person, scope and retained approval. Recommendations, payment assistance and authority to contract are distinct.")
    return localized("请核对判断是否得到引用原文及前后文支持；没有显示不等于现实中没有发生，不能补出缺失的身份、日期或金额。",
                     "Check the assertion against the quoted evidence and context. Absence from the available record does not prove non-occurrence; do not invent identity, dates or amounts.")

def build_review_items(workspace, chat_rows=None):
    material = workspace.material
    if hasattr(workspace,"analysis_snapshot"):
        from legalhub.case_presentation import build_presentation
        analysis = workspace.analysis_snapshot()
        graph = build_presentation(material,analysis,workspace.home/'presentation.json')
    else:
        analysis = workspace.state().get("analysis")
        graph = workspace.timeline()
    cid = material["metadata"]["case_id"]
    name = material["metadata"].get("case_name", cid)
    if cid == DEFAULT_CASE:
        name = "服装选购与转款沟通"
    messages = {r["id"]:r for r in material["records"] if r["kind"] == "message"}
    images = {i["image_id"]:i for i in material["images"]}
    coverage = {
        "images_total":len(images),
        "images_with_messages":len({m["image_id"] for m in messages.values()}),
        "scope":"available_transcripts"
    }
    result = []
    def append(kind, key, title, original, proposed, refs, priority="medium",
               rationale=None, laws=None, origin="model_draft", fallback_ids=None):
        resolved = []
        seen = set()
        for ref in refs or []:
            mid = ref.get("message_id")
            image_id = ref.get("image_id")
            row = messages.get(mid)
            if not row or row.get("case_id") != cid or image_id not in images:
                raise ValueError("Review source outside current case")
            quote = ref.get("quote") or row["text"]
            if not isinstance(quote, str) or quote not in row["text"]:
                raise ValueError("Review quote differs from recorded transcript")
            # Always resolve the actual pixel box from the recorded source.
            actual = next((r for r in row["source_refs"] if r["image_id"] == image_id), None)
            if not actual:
                raise ValueError("Review original reference missing")
            sig = (mid, image_id, quote)
            if sig in seen:
                continue
            seen.add(sig)
            resolved.append({
                "image_id":image_id,"message_id":mid,"quote":quote,
                "bbox":copy.deepcopy(actual.get("bbox")),
                "evidence_page":images[image_id].get("display_page"),
                "speaker_side":row.get("speaker_local_id","unknown"),
                "transcript_status":row.get("review_status","unreviewed")
            })
        source_ids = list(dict.fromkeys(r["image_id"] for r in resolved))
        if not source_ids:
            source_ids = list(fallback_ids or images)
        sources = []
        for image_id in source_ids:
            if image_id not in images:
                raise ValueError("Review image outside case")
            image = images[image_id]
            chat_id = graph.get("image_conversations",{}).get(image_id)
            chat = next((c for c in graph.get("conversations",[]) if c["id"]==chat_id),{})
            sources.append({
                "image_id":image_id,"sha256":image["sha256"],
                "size":copy.deepcopy(image["size"]),"page":image.get("display_page"),
                "conversation_name":copy.deepcopy(chat.get("name") or image.get("conversation_name") or localized("会话未核实","Conversation unverified")),
                "context_only":not bool(resolved)
            })
        item = {
            "id":kind+":"+str(key),"case_id":cid,"case_name":name,"kind":kind,
            "title":copy.deepcopy(title),"original_text":text(original),
            "proposed_text":text(proposed),"rationale":rationale or review_note(kind,key,proposed,[r["quote"] for r in resolved],cid in CLOTHING_CASES),
            "priority":priority,"source_refs":resolved,"sources":sources,
            "source_coverage":dict(coverage,direct_reference=bool(resolved)),
            "content_origin":origin,"law_refs":[{k:law.get(k) for k in ("id","article","title","text","effective_from","version_status")} for law in laws or []],
            "content_version":CONTENT_VERSION
        }
        fingerprint = {
            "version":CONTENT_VERSION,"case":cid,
            "corpus":material["metadata"].get("source_corpus_sha256"),
            "user_context_unverified":material["metadata"].get("user_context",""),
            "item":item
        }
        item["source_fingerprint"] = hashlib.sha256(json.dumps(fingerprint,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        result.append(item)

    if analysis:
        for n,event in enumerate(graph.get("legal_events",[])):
            proposed = paragraphs(event.get("description"),event.get("legal_test"))
            append("legal_event",f"{n:03d}",event["title"],proposed,proposed,event.get("source_refs"),
                   "high" if event.get("status") in ("undetermined","uncertain") or event["type"] in ("formation","offer","acceptance","authorization") else "medium",
                   laws=event.get("law_refs"),origin=event.get("provenance","model_draft"))
        projected = {e["id"].removeprefix("legal:") for e in graph.get("legal_events",[])}
        for n,row in enumerate(analysis.get("meanings",[])):
            if row["id"] in projected:
                continue
            detail = row.get("interpretation",{})
            body = paragraphs(detail.get("expression_meaning"),detail.get("legal_significance"),detail.get("possible_effect"))
            missing = "\n".join(text(s) for s in detail.get("conditions_missing",[]))
            rationale = review_note("meaning",str(n),body,[],cid in CLOTHING_CASES)
            if missing:
                rationale = localized(
                    text(rationale)+"\n\n原分析列出的待核实条件：\n"+missing,
                    rationale["en"]+"\n\nUnverified conditions listed in the original analysis:\n"+missing)
            append("meaning",f"{n:03d}",row["title"],body,body,row.get("source_refs"),
                   "high" if missing or detail.get("is_declaration")=="uncertain" else "medium",
                   rationale=rationale,laws=detail.get("law_refs"),origin="assistant_source_review" if analysis.get("review") else "model_draft")
        originals = {t["key"]:t for t in analysis.get("contract_terms",[])}
        for term in graph.get("contract_terms",[]):
            raw = originals.get(term["key"],term)
            original = paragraphs(raw.get("value"),raw.get("assessment"))
            proposed = paragraphs(term.get("value"),term.get("assessment"))
            append("contract_term",term["key"],term["label"],original,proposed,term.get("source_refs"),
                   "high" if term["key"] in ("parties","price","payment","quantity","delivery") else "medium",
                   origin=term.get("provenance","assistant_source_review" if not originals else "model_draft"))
        for n,row in enumerate(analysis.get("facts",[])):
            detail=row.get("interpretation",{})
            body=paragraphs(detail.get("description") or row.get("text"))
            append("fact",f"{n:03d}",row["title"],body,body,row.get("source_refs"),
                   "medium",origin="assistant_source_review" if analysis.get("review") else "model_draft")

    for row in chat_rows or []:
        if row.get("case_id") != cid or row.get("status") != "completed":
            continue
        citations = {c["id"]:c for c in row.get("citations",[])}
        for n,claim in enumerate(row.get("claims",[])):
            refs = []
            for key in claim.get("citation_ids",[]):
                if key not in citations:
                    raise ValueError("Chat review citation missing")
                refs.extend(citations[key].get("source_refs",[]))
            append("qa_claim",row["id"]+":"+str(n),
                   localized("问答判断 · "+row["question"],"Answer assertion · "+row["question"]),
                   claim["text"],claim["text"],refs,"high",
                   rationale=localized("请核对回答是否只表达引用原文支持的内容。尤其注意身份、实际转账和“没有发生”的否定判断；之前的模型回答不能代替证据。",
                                       "Check that the answer says only what its cited originals support, especially identity, actual payment and non-occurrence. A previous model answer is not evidence."))

    missing_ids = set(images)-{m["image_id"] for m in messages.values()}
    if missing_ids:
        append("transcription_gap","coverage",localized("原图转录覆盖待核对","Original transcription coverage requires review"),
               "部分原图尚无可用转录。","现有转录不覆盖全部原图，相关事实与法律解释应保留不确定性。",[],"high",
               rationale=localized("请直接核对这些原图；未成功识别的图片不等于没有相关事实。可补充材料或重新生成识别后再复核。",
                                   "Inspect these originals. An untranscribed image does not imply absence of relevant facts. Add evidence or retry extraction before reviewing."),
               origin="code_coverage_check",fallback_ids=sorted(missing_ids))

    return sorted(result,key=lambda i:({"high":0,"medium":1,"low":2}.get(i["priority"],2),
                                      {"contract_term":0,"legal_event":1,"meaning":2,"qa_claim":3,"transcription_gap":4,"fact":5}.get(i["kind"],6),i["id"]))
