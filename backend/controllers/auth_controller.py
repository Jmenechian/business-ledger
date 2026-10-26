from backend.models.auth import LoginRequest
from backend.services.sessions import AuthService, Login


def login(auth: AuthService, input: LoginRequest, prior_token: str) -> Login:
    return auth.login(input.password.get_secret_value(), prior_token)
