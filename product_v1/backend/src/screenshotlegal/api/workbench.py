from fastapi import Request
from screenshotlegal.domain.common.models import CaseRecord
from screenshotlegal.domain.workbench import CaseEdit, WorkbenchSnapshot, PresentationPreview
from screenshotlegal.application.services.user_workbench import UserWorkbench

def register_workbench(app, workspace, auth):
    service = UserWorkbench(workspace, auth)

    @app.get("/v1/cases/{case_id}/workbench", response_model=WorkbenchSnapshot)
    def snapshot(case_id: str, request: Request):
        return service.snapshot(request.state.user, case_id)

    @app.put("/v1/cases/{case_id}/workbench", response_model=CaseRecord)
    def edit(case_id: str, payload: CaseEdit, request: Request):
        return service.edit(request.state.user, case_id, payload)

    @app.post("/v1/cases/{case_id}/presentations", response_model=PresentationPreview)
    def presentation(case_id: str, request: Request):
        return service.preview_presentation(request.state.user, case_id)
