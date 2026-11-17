from pathlib import Path
p=Path('paper/author_reproductions/legal_reasoning_paths/algorithm.py')
s=p.read_text(encoding='utf-8')
s=s.replace("PARAMETERS=dict(model='gpt-4o',temperature=0,max_tokens=4096)","PARAMETERS=dict(model='gpt-4o',temperature=0,max_tokens=4096,parameter_origin='project bounded trial; author generation settings not released')")
s=s.replace("nodes.append(n);provisions.append(n)","""occurrence=dict(document_id=document['id'],block_index=bi,anchors=n['anchors'],raw_citation_candidates=n['raw_citation_candidates'])
                    existing=next((p for p in nodes if p['kind']=='Provision' and p['text']==value),None)
                    if existing:
                        existing['source_occurrences'].append(occurrence)
                        existing['anchors'].extend(a for a in n['anchors'] if a not in existing['anchors'])
                        n=existing
                    else:
                        n['id']=identity('Provision',value);n['source_occurrences']=[occurrence];nodes.append(n)
                    provisions.append(n)""")
s=s.replace("if node['kind']=='Provision':record['project:canonicalTitle']=node['text']","""if node['kind']=='Provision':
            record['project:canonicalTitle']=node['text']
            record['lkg:sourceDocument']=[{'@id':identity('document',d)} for d in sorted({o['document_id'] for o in node['source_occurrences']})]""")
s=s.replace("if a['document_id']!=b['document_id']:raise ValueError('Cross-document reasoning edge not authorized')","""if edge['predicate']=='provisionToNorm':
            if not any(o['document_id']==b['document_id'] and o['block_index']==b['block_index'] for o in a['source_occurrences']):raise ValueError('Provision/Norm edge outside its local block')
        elif a['document_id']!=b['document_id']:raise ValueError('Cross-document reasoning edge not authorized')""")
p.write_text(s,encoding='utf-8')
p=Path('paper/author_reproductions/legal_reasoning_paths/prepare_native.py')
s=p.read_text(encoding='utf-8').replace("dict(id=selected[0]['document_path'],overview=''","dict(id=selected[0]['document_path'],source_status='published_judgment',overview=''")
p.write_text(s,encoding='utf-8')
