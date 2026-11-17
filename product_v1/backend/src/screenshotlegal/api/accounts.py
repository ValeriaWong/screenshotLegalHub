from fastapi import Request, Response
from screenshotlegal.application.services.auth import COOKIE
from screenshotlegal.domain.settings.auth import LoginRequest, CreateUserRequest, UserView, UpdateUserRequest, PasswordRequest, ShareRequest
from screenshotlegal.domain.settings.models import LocalUser, ModelConfiguration, ModelView, ModelSelection, ConnectivityResult, ConnectivityRequest, ConnectivityImage


def register_accounts(app, auth, workspace, settings):
    def set_session(response, token):
        response.set_cookie(COOKIE,token,max_age=settings.session_hours*3600,httponly=True,secure=settings.session_secure_cookie,samesite='lax',path='/')

    @app.get('/v1/auth/status')
    def auth_status():
        return {'initialized':auth.initialized()}

    @app.post('/v1/auth/setup',response_model=UserView)
    def setup(request:CreateUserRequest,response:Response):
        auth.create_user(request,bootstrap=True)
        user,token=auth.login(request,'setup')
        set_session(response,token)
        return user

    @app.post('/v1/auth/login',response_model=UserView)
    def login(request:LoginRequest,response:Response,http_request:Request):
        user,token=auth.login(request,http_request.client.host if http_request.client else 'unknown')
        set_session(response,token)
        return user

    @app.get('/v1/auth/me',response_model=UserView)
    def me(request:Request):
        return request.state.user

    @app.post('/v1/auth/logout')
    def logout(request:Request,response:Response):
        auth.logout(request.cookies[COOKIE]);response.delete_cookie(COOKIE,path='/')
        return {'ok':True}

    @app.post('/v1/auth/password')
    def change_password(request:Request,payload:PasswordRequest,response:Response):
        auth.change_password(request.state.user,payload);response.delete_cookie(COOKIE,path='/')
        return {'ok':True}

    @app.get('/v1/users',response_model=list[UserView])
    def users(request:Request):
        auth.admin(request.state.user);return auth.users()

    @app.post('/v1/users',response_model=UserView,status_code=201)
    def add_user(request:Request,payload:CreateUserRequest):
        auth.admin(request.state.user);return auth.create_user(payload)

    @app.put('/v1/users/{user_id}',response_model=UserView)
    def update_user(user_id:str,request:Request,payload:UpdateUserRequest):
        auth.admin(request.state.user);return auth.update_user(user_id,payload)

    def preferences(request):
        return workspace.preferences(request.state.user.id)

    @app.get('/v1/user',response_model=LocalUser)
    def user_profile(request:Request):
        return preferences(request).user()

    @app.put('/v1/user',response_model=LocalUser)
    def save_user_profile(request:Request,payload:LocalUser):
        return preferences(request).save_user(payload)

    @app.get('/v1/settings/models',response_model=list[ModelView])
    def models(request:Request):
        return preferences(request).models()

    @app.post('/v1/settings/models',response_model=ModelView,status_code=201)
    def add_model(request:Request,payload:ModelConfiguration):
        return preferences(request).save_model(payload)

    @app.put('/v1/settings/models/{model_id}',response_model=ModelView)
    def edit_model(model_id:str,request:Request,payload:ModelConfiguration):
        return preferences(request).save_model(payload,model_id)

    @app.delete('/v1/settings/models/{model_id}')
    def delete_model(model_id:str,request:Request):
        preferences(request).delete_model(model_id);return {'ok':True}

    @app.put('/v1/settings/default-model')
    def select_model(request:Request,payload:ModelSelection):
        return preferences(request).select(payload.model_id)

    def image_sample(user, case_id=None, evidence_id=None):
        if bool(case_id) != bool(evidence_id):
            raise ValueError('Specify both case and evidence IDs')
        if case_id:
            cases = [auth.access(user, case_id)]
        else:
            cases = [case for case in workspace.repo.list('cases') if auth.case_role(user, case)]
        cases.sort(key=lambda case: (case.get('owner_id') != user.id, case.get('created_at', ''), case['id']))
        for case in cases:
            for image in workspace.evidence(case['id']):
                if evidence_id and image['id'] != evidence_id:
                    continue
                if image.get('kind') != 'image' or image.get('mime_type') not in {'image/png', 'image/jpeg', 'image/webp'}:
                    continue
                try:
                    workspace.storage.verified_path(image)
                except (OSError, ValueError):
                    if evidence_id:
                        raise ValueError('Test image is missing or failed its integrity check') from None
                    continue
                return image, ConnectivityImage(case_id=case["id"], evidence_id=image["id"],
                                                case_title=case["title"], filename=image["filename"])
        if evidence_id:
            raise KeyError('Test image not found')
        return None, None

    @app.get('/v1/settings/test-image', response_model=ConnectivityImage | None)
    def connectivity_image(request: Request):
        return image_sample(request.state.user)[1]

    @app.post('/v1/settings/models/{model_id}/test',response_model=ConnectivityResult)
    async def test_model(model_id: str, request: Request, payload: ConnectivityRequest | None = None):
        pref = preferences(request)
        pref.owned(model_id)
        payload = payload or ConnectivityRequest()
        image = None
        if payload.mode == 'image':
            image, _ = image_sample(request.state.user, payload.case_id, payload.evidence_id)
            if image is None:
                return ConnectivityResult(success=False, latency_ms=0, mode='image',
                                          message='No readable image is available in your accessible cases')
        return await pref.test_model(model_id, image=image)

    @app.get('/v1/cases/{id}/members')
    def members(id:str,request:Request):
        return auth.members(request.state.user,id)

    @app.put('/v1/cases/{id}/members')
    def share(id:str,request:Request,payload:ShareRequest):
        return auth.share(request.state.user,id,payload)
