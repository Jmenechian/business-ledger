from typing import Annotated

from fastapi import Depends, Path, Request

from backend.database.connection import Database


def get_database(request: Request) -> Database:
    return request.app.state.database


DatabaseDependency = Annotated[Database, Depends(get_database)]
ClientID = Annotated[int, Path(gt=0)]
