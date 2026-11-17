import time
import hashlib
import json
from uuid import uuid4
from urllib.parse import urlsplit
import httpx
from screenshotlegal.domain.settings.models import LocalUser, ModelView, ConnectivityResult
from screenshotlegal.infrastructure.model.secrets import ModelSecrets
from screenshotlegal.infrastructure.model.providers import OpenAICompatibleProvider
from .operation_events import operation,record,pending


def model_url(value):
    value = value.strip().rstrip('/')
    parsed = urlsplit(value)
    local = parsed.hostname in {'localhost', '127.0.0.1', '::1'}
    if not parsed.hostname or (parsed.scheme != 'https' and not (parsed.scheme == 'http' and local)) or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Use an HTTPS base URL (HTTP allowed only for loopback), without embedded credentials or query parameters')
    try:
        parsed.port
    except ValueError as error:
        raise ValueError('Invalid model endpoint port') from error
    return value


class Preferences:
    def __init__(self, settings, repo, user_id='local', secrets=None):
        self.settings, self.repo = settings, repo
        self.user_id = user_id
        self.secrets = secrets or ModelSecrets(settings.data_dir)

    def user(self):
        row = self.repo.optional('auth_users', self.user_id) or self.repo.optional('local_users', self.user_id) or {}
        return LocalUser(display_name=row.get('display_name', '本地用户'), organization=row.get('organization', ''))

    def save_user(self, request):
        if not request.display_name.strip():
            raise ValueError('Display name is required')
        request = request.model_copy(update={'display_name': request.display_name.strip()})
        account = self.repo.optional('auth_users', self.user_id)
        if account:
            from screenshotlegal.infrastructure.db.models import MODELS
            with self.repo.session.begin() as session:
                session.connection().exec_driver_sql('BEGIN IMMEDIATE')
                row=session.get(MODELS['auth_users'],self.user_id)
                row.body=dict(row.body,**request.model_dump())
        else:
            self.repo.put('local_users', self.user_id, request.model_dump())
        return request

    def selected(self):
        return (self.repo.optional('user_settings', self.user_id) or {}).get('model_id')

    def view(self, row, connectivity=None):
        return ModelView(**{k: row[k] for k in ['id', 'name', 'base_url', 'model_name', 'supports_vision', 'allow_external_egress']}, **{k: row[k] for k in ['max_output_tokens','input_token_price','output_token_price','price_currency','request_timeout_seconds','request_total_timeout_seconds'] if k in row}, has_api_key=bool(row.get('encrypted_api_key')), is_default=self.selected()==row['id'], connectivity=connectivity or {})

    def connection_fingerprint(self, row):
        fields = ['base_url', 'model_name', 'supports_vision', 'allow_external_egress',
                  'request_timeout_seconds', 'request_total_timeout_seconds', 'max_output_tokens', 'encrypted_api_key']
        return hashlib.sha256(json.dumps({k: row.get(k) for k in fields}, sort_keys=True).encode()).hexdigest()

    def models(self):
        rows = [r for r in self.repo.list('model_configs') if r.get('owner_id') == self.user_id]
        by_id = {r['id']: r for r in rows}
        checks = {id: {} for id in by_id}
        connection_fields = {'base_url', 'model_name', 'supports_vision', 'allow_external_egress',
                             'request_timeout_seconds', 'request_total_timeout_seconds', 'max_output_tokens'}
        events = sorted(pending(self.repo, self.user_id), key=lambda e: e.get('occurred_at', ''))
        cutoff = {}
        for event in events:
            id = event.get('object_id')
            changes = event.get('changes', {})
            if id in by_id and event.get('object_type') == 'model' and event.get('action') == 'model.updated':
                if changes.get('credential_changed') or connection_fields.intersection(changes):
                    cutoff[id] = event.get('occurred_at', '')
        fingerprints = {id: self.connection_fingerprint(row) for id, row in by_id.items()}
        for event in events:
            id = event.get('object_id')
            if id not in by_id or event.get('object_type') != 'model' or event.get('action') != 'model.tested':
                continue
            when, changes = event.get('occurred_at', ''), event.get('changes', {})
            if not when or when <= cutoff.get(id, ''):
                continue
            if changes.get('config_fingerprint') and changes['config_fingerprint'] != fingerprints[id]:
                continue
            mode = changes.get('mode')
            if mode in {'text', 'image'} and isinstance(changes.get('success'), bool):
                checks[id][mode] = dict(success=changes['success'], checked_at=when, latency_ms=changes.get('latency_ms', 0))
        return [self.view(row, checks[row['id']]) for row in rows]

    def owned(self, id):
        row = self.repo.get('model_configs', id)
        if row.get('owner_id')!=self.user_id:
            raise KeyError('Model not found')
        return row

    def save_model(self, request, id=None):
        previous = self.owned(id) if id else {}
        key = request.api_key.get_secret_value().strip() if request.api_key else ''
        encrypted = self.secrets.encrypt(key) if key else previous.get('encrypted_api_key')
        if not encrypted:
            raise ValueError('An API key is required for a new model')
        if not request.name.strip() or not request.model_name.strip():
            raise ValueError('Configuration and model names are required')
        row = dict(previous, id=id or str(uuid4()), owner_id=self.user_id, name=request.name.strip(), base_url=model_url(request.base_url), model_name=request.model_name.strip(), supports_vision=request.supports_vision, allow_external_egress=request.allow_external_egress, encrypted_api_key=encrypted)
        usage_fields=['max_output_tokens','input_token_price','output_token_price','price_currency','request_timeout_seconds','request_total_timeout_seconds']
        row.update({k:getattr(request,k) for k in usage_fields})
        public=['name','base_url','model_name','supports_vision','allow_external_egress']+usage_fields
        changes={k:dict(before=previous.get(k),after=row[k]) for k in public if previous.get(k)!=row[k]}
        changes['credential_changed']=bool(key)
        event=operation(self.user_id,'settings','model.updated' if id else 'model.created','model',row['id'],changes)
        records=[('model_configs',row['id'],row,'','',False),record(event)]
        if not self.selected(): records.append(('user_settings',self.user_id,dict(model_id=row['id']),'','',False))
        self.repo.batch(records)
        return self.view(row)

    def select(self, id):
        if id is not None:
            self.owned(id)
        event=operation(self.user_id,'settings','model.selected','model',id or 'none',{'model_id':dict(before=self.selected(),after=id)})
        self.repo.batch([('user_settings',self.user_id,dict(model_id=id),'','',False),record(event)])
        return dict(model_id=id)

    def delete_model(self, id):
        self.owned(id)
        from screenshotlegal.infrastructure.db.models import MODELS
        with self.repo.session.begin() as session:
            session.connection().exec_driver_sql('BEGIN IMMEDIATE')
            model=session.get(MODELS['model_configs'],id)
            if not model or model.body['owner_id']!=self.user_id: raise KeyError('Model not found')
            session.delete(model)
            selected=session.get(MODELS['user_settings'],self.user_id)
            if selected and selected.body.get('model_id')==id: selected.body=dict(model_id=None)
            event=operation(self.user_id,'settings','model.deleted','model',id,{'deleted':True})
            session.add(MODELS['run_events'](id=event['id'],case_id='',run_id='operation-audit:'+self.user_id,body=event))

    def provider_settings(self, id=None, vision=False):
        id = id or self.selected()
        if id is None:
            if self.user_id=='local':
                return self.settings
            raise ValueError('Add and select a model in your settings first')
        row = self.owned(id)
        if vision and not row['supports_vision']:
            raise ValueError('Selected model is not configured for vision')
        return self.settings.model_copy(update=dict(model_base_url=row['base_url'], model_name=row['model_name'], model_api_key=self.secrets.decrypt(row['encrypted_api_key']), enable_real_model=True, allow_external_egress=row['allow_external_egress'],model_max_output_tokens=row.get('max_output_tokens'),model_request_timeout_seconds=row.get('request_timeout_seconds',90),model_request_total_timeout_seconds=row.get('request_total_timeout_seconds')))

    async def test_model(self, id, image=None):
        tested_config = self.owned(id)
        start = time.monotonic()
        try:
            settings = self.provider_settings(id, vision=image is not None)
            provider = OpenAICompatibleProvider(settings, self.repo, self.user_id)
            run_id = 'connectivity.' + str(uuid4())
            if image is None:
                await provider.probe(run_id)
            else:
                from screenshotlegal.infrastructure.storage.evidence import EvidenceStorage
                await provider.probe_image(run_id, image, EvidenceStorage(self.settings))
            success, message = True, 'Model responded successfully'
        except PermissionError:
            success, message = False, 'Enable external model requests before testing'
        except httpx.TimeoutException:
            success, message = False, '调用超时，结果及费用未知；请核对服务记录，重新调用可能再次计费。'
        except httpx.HTTPError:
            success, message = False, 'Network connection failed'
        except RuntimeError as error:
            success, message = False, str(error)
        except (ValueError, KeyError, TypeError, OSError):
            success, message = False, 'Invalid model configuration or response; check endpoint, model and credentials'
        event=operation(self.user_id,'settings','model.tested','model',id,{'mode':'image' if image else 'text','success':success,'latency_ms':round((time.monotonic()-start)*1000),'config_fingerprint':self.connection_fingerprint(tested_config)},reason=message)
        self.repo.batch([record(event)])
        return ConnectivityResult(success=success, message=message, latency_ms=round((time.monotonic()-start)*1000),
                                  mode="image" if image is not None else "text",
                                  case_id=image["case_id"] if image is not None else None,
                                  evidence_id=image["id"] if image is not None else None)
