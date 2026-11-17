"""Dify imports ordinary OpenAPI tools; these are not Dify App API endpoints."""
from urllib.parse import urlsplit
from .generic import GenericAdapter
from ..contracts import HarnessError

class DifyAdapter(GenericAdapter):
    def openapi(self, base_url):
        url = urlsplit(base_url)
        if not url.hostname or url.username or url.password or url.query or url.fragment or (
            url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in {'localhost','127.0.0.1','::1'})
        ):
            raise HarnessError('INVALID_URL')
        paths, schemas = {}, {}
        for definition in self.definitions():
            schema = definition['parameters'].copy()
            # Pydantic nested definitions are scoped per operation to avoid name collisions.
            prefix = definition['name'] + '_'
            def convert(value):
                if isinstance(value, dict):
                    return {k: ('#/components/schemas/'+prefix+v.rsplit('/',1)[-1] if k=='$ref' else convert(v)) for k,v in value.items()}
                if isinstance(value, list):
                    return [convert(v) for v in value]
                return value
            for name, value in schema.pop('$defs', {}).items():
                schemas[prefix+name] = convert(value)
            paths['/adapters/dify/'+definition['name']] = {'post': {
                'operationId': definition['name'], 'summary': definition['description'],
                'security': [{'HarnessBearer': []}],
                'parameters': [{'in':'header','name':'Idempotency-Key','required':True,'schema':{'type':'string'}}],
                'requestBody': {'required':True,'content':{'application/json':{'schema':convert(schema)}}},
                'responses': {'200':{'description':'Run result or operation data'},
                              '401':{'description':'Authentication required'},'403':{'description':'Permission denied'},
                              '409':{'description':'Idempotency or state conflict'},'422':{'description':'Invalid input'}}}}
        return {'openapi':'3.1.0','info':{'title':'Agentic Harness','version':'0.2.0'},
                'servers':[{'url':base_url.rstrip('/')}], 'paths':paths,
                'components':{'schemas':schemas,'securitySchemes':{'HarnessBearer':{'type':'http','scheme':'bearer'}}}}
