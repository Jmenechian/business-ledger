from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class ClientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200, strict=True)
    ]


class Client(BaseModel):
    id: int
    nombre: str
    saldo: int | float
    created_at: str
