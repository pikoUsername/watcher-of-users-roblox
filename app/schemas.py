from enum import IntEnum
from typing import List, Optional

from pydantic import BaseModel, validator


class StatusCodes(IntEnum):
    success = 200
    fail = 500
    already_bought = 401



class SendError(BaseModel):
    name: str
    info: str


class ReturnSignal(BaseModel):
    errors: Optional[List[SendError]] = []
    status: StatusCodes

    @validator("errors")
    def validate_error(cls, value: List[Exception]):
        result = []
        for v in value:
            result.append(SendError(
                name=v.__class__.__name__,
                info=v.__str__()
            ))
        return result
