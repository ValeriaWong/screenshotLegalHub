import re
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from screenshotlegal.application.services.auth import AuthError, COOKIE


def install_access(app, auth, repo):
    origins=auth.settings.trusted_origins
    public={'/health','/v1/health','/version','/v1/version','/v1/auth/status','/v1/auth/login','/v1/auth/setup'}

    @app.middleware('http')
    async def authenticated(request, call_next):
        path=request.url.path
        try:
            if request.method not in ['GET','HEAD','OPTIONS'] and request.headers.get('origin') and request.headers['origin'] not in origins:
                raise AuthError(403,'Request origin is not allowed')
            if path.startswith('/v1/') and path not in public and request.method!='OPTIONS':
                user=auth.current(request.cookies.get(COOKIE))
                request.state.user=user
                case=re.match(r'^/v1/cases/([^/]+)(?:/|$)',path)
                run=re.match(r'^/v1/runs/([^/]+)(?:/|$)',path)
                if case:
                    auth.access(user,case[1],write=request.method not in ['GET','HEAD'],owner=path.endswith('/members') and request.method!='GET')
                if run:
                    auth.access(user,repo.get('analysis_runs',run[1])['case_id'],write=request.method not in ['GET','HEAD'])
            return await call_next(request)
        except AuthError as error:
            return JSONResponse(status_code=error.status,content={'detail':error.message})
        except KeyError:
            return JSONResponse(status_code=404,content={'detail':'Resource not found'})

    app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=['GET','POST','PUT','DELETE'],allow_headers=['Content-Type'])
