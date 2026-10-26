from pydantic import BaseModel, ConfigDict, SecretStr, field_validator


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: SecretStr

    @field_validator("password")
    @classmethod
    def password_length(cls, value):
        password = value.get_secret_value()
        if not password or len(password.encode("utf-8")) > 1024:
            raise ValueError("contraseña no válida")
        return value
