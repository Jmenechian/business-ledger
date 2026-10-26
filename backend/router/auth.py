from fastapi import APIRouter, Request, Response

from backend.controllers import auth_controller
from backend.models.auth import LoginRequest
from backend.router.json_route import ExactJSONRoute
from backend.services.sessions import SESSION_LIFETIME

router = APIRouter(prefix="/auth", tags=["Autenticación"], route_class=ExactJSONRoute)


@router.post("/login")
def login(input: LoginRequest, request: Request, response: Response):
    result = auth_controller.login(
        request.app.state.auth, input, request.cookies.get(request.app.state.cookie_name, "")
    )
    response.set_cookie(
        request.app.state.cookie_name,
        result.token,
        max_age=SESSION_LIFETIME,
        secure=request.app.state.secure_cookies,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return {"estado": "sesión iniciada"}


@router.post("/logout", status_code=204)
def logout(request: Request):
    auth_controller.logout(
        request.app.state.auth, request.cookies.get(request.app.state.cookie_name, "")
    )
    response = Response(status_code=204)
    response.delete_cookie(
        request.app.state.cookie_name,
        path="/",
        secure=request.app.state.secure_cookies,
        httponly=True,
        samesite="strict",
    )
    return response
