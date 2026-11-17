"""Pure reading of immutable snapshots, using Unicode code-point offsets."""
from screenshotlegal.domain.common.models import digest
def read_snapshot(snapshot, request):
    blocks=snapshot['blocks']
    start_index=next((i for i,b in enumerate(blocks) if b['id']==request.block_id),None)
    if start_index is None: raise KeyError('来源块不属于此快照')
    if request.start>len(blocks[start_index]['text']): raise ValueError('读取位置越界')
    remaining=request.max_chars;parts=[];ranges=[];next_request=None
    for index in range(start_index,len(blocks)):
        block=blocks[index];start=request.start if index==start_index else 0
        end=min(len(block['text']),start+remaining)
        if end>start:
            parts.append(block['text'][start:end])
            ranges.append(dict(block_id=block['id'],page=block['page'],start=start,end=end,text_digest=digest(block['text'])))
            remaining-=end-start
        if end<len(block['text']):
            next_request=dict(block_id=block['id'],start=end,max_chars=request.max_chars,across_blocks=request.across_blocks)
            break
        if not request.across_blocks: break
        if remaining==0:
            if index+1<len(blocks): next_request=dict(block_id=blocks[index+1]['id'],start=0,max_chars=request.max_chars,across_blocks=True)
            break
    return dict(parse_run_id=snapshot['parse_run_id'],snapshot_id=snapshot['id'],block_id=request.block_id,
                text=''.join(parts),char_unit='unicode_code_point',start=request.start,end=ranges[-1]['end'] if ranges else request.start,
                text_digest=digest(blocks[start_index]['text']),content_ranges=ranges,context_ranges=[],
                parsed_coverage=dict(pages=snapshot['pages'],complete=True),truncated=next_request is not None,
                truncation_reason='character_budget' if next_request else None,next_request=next_request)
