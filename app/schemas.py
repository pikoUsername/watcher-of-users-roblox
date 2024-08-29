from enum import IntEnum
from typing import List, Optional

from pydantic import BaseModel, validator


class SearchData(BaseModel):
    # anemic model
    name: str


class StatusCodes(IntEnum):
    success = 200
    fail = 500
    already_bought = 401
    no_tokens_available = 402
    invalid_data = 400
    invalid_price = 403


class SendError(BaseModel):
    name: str
    info: str


class SearchResponse(BaseModel):
    login: str
    nickname: str


class ReturnSignal(BaseModel):
    errors: Optional[List[SendError]] = []
    status_code: StatusCodes
    info: Optional[str] = ""
    data: list[SearchResponse] = []

    @validator("errors")
    def validate_error(cls, value: List[Exception]):
        result = []
        for v in value:
            result.append(SendError(
                name=v.__class__.__name__,
                info=v.__str__()
            ))
        return result
