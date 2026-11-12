"""Small helpers shared by routers."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Header, Query
from pydantic import BaseModel, ValidationError

from app.core.errors import UnprocessableEntity


def validation_error_from(exc: ValidationError) -> UnprocessableEntity:
    fields: list[dict[str, Any]] = []
    for err in exc.errors():
        fields.append(
            {
                "loc": ["body", *[str(p) for p in err.get("loc", ())]],
                "msg": str(err.get("msg", "")),
                "type": str(err.get("type", "")),
            }
        )
    return UnprocessableEntity(
        "The request is invalid.", code="validation_error", details={"fields": fields}
    )


def validate_model(model: type[BaseModel], data: dict[str, Any]) -> Any:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise validation_error_from(exc) from exc


def parse_bool_field(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return value.strip().lower() in {"true", "1", "yes", "on"}


LimitQuery = Annotated[int, Query(ge=1, le=100)]
OffsetQuery = Annotated[int, Query(ge=0)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]
