from contextlib import nullcontext
import json
import re
import unicodedata
from sqlalchemy import text

def tokenize(value):
    normalized=unicodedata.normalize('NFKC',value).casefold()
    terms=[]
    for part in re.findall(r'[a-z0-9_]+|[\u3400-\u9fff]+',normalized):
        terms.extend([part] if not re.fullmatch(r'[\u3400-\u9fff]+',part) else list(part)+[part[i:i+2] for i in range(len(part)-1)])
    return terms

class Retriever:
    def __init__(self, repo):
        self.repo=repo

    def index(self,case_id,messages,*,connection=None):
        with (nullcontext(connection) if connection is not None else self.repo.engine.begin()) as conn:
            conn.execute(text('DELETE FROM search_index WHERE case_id=:case'),{'case':case_id})
            for message in messages:
                terms=' '.join(tokenize(' '.join(str(message.get(k) or '') for k in ['text','speaker','timestamp','event_type'])))
                conn.execute(text('INSERT INTO search_index(id,case_id,terms,body) VALUES(:id,:case,:terms,:body)'),dict(id=message['id'],case=case_id,terms=terms,body=json.dumps(message,ensure_ascii=False)))

    def search(self,case_id,query):
        terms=tokenize(query)[:50]
        if not terms:
            return []
        match=' OR '.join('"'+t.replace('"','""')+'"' for t in terms)
        with self.repo.engine.connect() as conn:
            rows=conn.execute(text('SELECT body,bm25(search_index) AS score FROM search_index WHERE search_index MATCH :q AND case_id=:case ORDER BY score LIMIT 50'),{'q':match,'case':case_id})
            return [dict(**json.loads(row[0]),score=row[1]) for row in rows]
