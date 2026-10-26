from fastapi import APIRouter, Request, Response

from backend.controllers import auth_controller
from backend.models.auth import LoginRequest
from backend.router.json_route import ExactJSONRoute
from backend.services.sessions import COOKIE_NAME, SESSION_LIFETIME

router = APIRouter(prefix="/auth", tags=["Autenticación"], route_class=ExactJSONRoute)


@router.post("/login")
def login(input: LoginRequest, request: Request, response: Response):
    result = auth_controller.login(
        request.app.state.auth, input, request.cookies.get(COOKIE_NAME, "")
    )
    response.set_cookie(
        COOKIE_NAME,
        result.token,
        max_age=SESSION_LIFETIME,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return {"estado": "sesión iniciada"}
