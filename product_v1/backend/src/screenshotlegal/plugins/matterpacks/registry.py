from pathlib import Path
import hashlib
import yaml
from screenshotlegal.domain.legal.models import AuthoritySource,GuideIssue
from screenshotlegal.domain.legal.models import MatterManifest

class MatterRegistry:
    def __init__(self, directory: Path):
        self.packs = {}
        for path in sorted(directory.glob('**/manifest.yaml')):
            if '_template' in path.parts:
                continue
            manifest = MatterManifest.model_validate(yaml.safe_load(path.read_text(encoding='utf-8')))
            data = {'manifest': manifest.model_dump()}
            hasher = hashlib.sha256()
            for file in sorted(path.parent.glob('*.yaml')):
                hasher.update(file.name.encode() + b'\0' + file.read_bytes())
                if file.name != 'manifest.yaml':
                    data[file.stem] = yaml.safe_load(file.read_text(encoding='utf-8'))
            data['digest'] = hasher.hexdigest()
            claims = data['claims']
            ids = []
            for claim in claims:
                ids.append(claim['id'])
                for element in claim['elements']:
                    ids.append(element['id'])
                    for fact in element['facts']:
                        ids.append(fact['id'])
                        if not fact.get('question') or not fact.get('burden') or not fact.get('expected_evidence'):
                            raise ValueError('Incomplete fact question template')
            if len(ids) != len(set(ids)):
                raise ValueError('Duplicate matter template ID')
            data['authorities']=[AuthoritySource.model_validate(a).model_dump() for a in data['authorities']]
            for authority in data['authorities']:
                if authority['verification_status']=='verified':
                    text=authority.get('text');review=authority['review']
                    actual=hashlib.sha256(text.encode('utf-8')).hexdigest() if text else None
                    if not actual or authority['source_digest']!=actual or review['status']!='approved' or review['reviewed_digest']!=actual or not review['reviewer'] or not review['reviewed_at']:
                        raise ValueError('Verified authority requires reviewed exact source text and matching SHA256')
            if data.get('factor_hierarchy') is not None:
                hierarchy=[GuideIssue.model_validate(i).model_dump() for i in data['factor_hierarchy']]
                guides={a['id'] for a in data['authorities'] if a['source_role']=='legal_guide' and a.get('text')}
                factors=[f for issue in hierarchy for f in issue['factors']]
                if len({f['id'] for f in factors})!=len(factors) or any(not set(f['guide_source_ids'])<=guides for f in factors):
                    raise ValueError('Factor hierarchy requires unique factors linked to frozen independent guide text')
                data['factor_hierarchy']=hierarchy
            key = (manifest.id, manifest.version)
            if key in self.packs:
                raise ValueError('Duplicate matter version')
            self.packs[key] = data

    def get(self, id, version='1.0.0'):
        return self.packs[(id, version)]
