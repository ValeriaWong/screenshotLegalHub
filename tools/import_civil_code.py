"""Import an official published statute version; searches remain fully local."""
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import sys
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legalhub import benchmark as b

URL = 'https://www.court.gov.cn/zixun/xiangqing/233181.html'
DEST = ROOT / 'blocks/retriever/artifacts/statutes'


class Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts = []; self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.hidden += 1
        if tag in ('p', 'div', 'br', 'h1', 'h2', 'h3') and not self.hidden: self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'div') and not self.hidden: self.parts.append('\n')
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    raw = DEST / 'civil-code-2020.html'
    if not raw.exists():
        r = requests.get(URL, timeout=(10, 60)); r.raise_for_status()
        raw.write_bytes(r.content)
    text = Text(); text.feed(raw.read_bytes().decode('utf-8'))
    content = ''.join(text.parts)
    # Article labels remain literal Chinese labels in results and citations.
    matches = list(re.finditer(r'第[一二三四五六七八九十百千零]+条[\s\u3000\u2002]+', content))
    if len(matches) != 1260: raise ValueError(f'Expected 1260 Civil Code articles, got {len(matches)}; inspect source before import')
    records = []
    for i, match in enumerate(matches):
        article = match.group().strip(); end = matches[i+1].start() if i+1 < len(matches) else len(content)
        quote = content[match.start():end].strip()
        # Final article ends at its first paragraph; footer is not statute text.
        if i == len(matches)-1: quote = quote.split('\n')[0].strip()
        # Remove subsequent chapter/section headings from the current article.
        quote = re.split(r'\n\s*第[一二三四五六七八九十百千零]+[编章节]', quote)[0].strip()
        records.append({'id': f'civil-code-2020:{i+1}', 'kind': 'statute', 'article': article,
                        'title': '中华人民共和国民法典 ' + article, 'text': quote,
                        'publication_date': '2020-05-28', 'effective_from': '2021-01-01',
                        'jurisdiction': 'CN', 'version_status': 'published_2020_text_not_case_applicability_checked',
                        'origin_type': 'official_statute_text', 'review_status': 'case_applicability_requires_review',
                        'source_refs': [{'url': URL, 'source_file': raw.relative_to(ROOT).as_posix(), 'source_sha256': b.sha(raw),
                                         'article': article, 'quote': quote}]})
    b.write(DEST / 'civil-code-2020.json', {'images': [], 'records': records, 'metadata': {
        'source_url': URL, 'source_sha256': b.sha(raw), 'retrieved_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'One published Chinese civil-code version; not a complete or case-applicable law database.'}})
    print(json.dumps({'articles': len(records), 'source': URL}), flush=True)


if __name__ == '__main__': main()
