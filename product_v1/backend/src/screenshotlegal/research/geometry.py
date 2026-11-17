"""Canonical pixel-xyxy layout shared by review overlays and renderer."""
from .contracts import PageLayout

def canonical(pages, message_ids=None):
    result=[]
    for page in pages:
        value=dict(page=page['page'],width=page['width'],height=page['height'],
                   boxes=[dict(message_id=b['message_id'],bbox=b['bbox']) for b in page['boxes']
                          if message_ids is None or b['message_id'] in message_ids])
        result.append(PageLayout.model_validate(value).model_dump(mode='json'))
    numbers=[p['page'] for p in result]
    if len(set(numbers))!=len(numbers):
        raise ValueError('Page numbers must be unique')
    return sorted(result,key=lambda p:p['page'])

def validate(layout, content):
    ids={m['id'] for m in content['messages']}
    pages=canonical(layout)
    if any(b['message_id'] not in ids for p in pages for b in p['boxes']):
        raise ValueError('Layout refers to unknown message IDs')
    return pages
