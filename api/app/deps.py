"""Shared FastAPI dependencies / lookup helpers."""

from typing import Annotated, TypeVar

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from .database import Base, get_db
from .terms import TERMS, Term

DB = Annotated[Session, Depends(get_db)]

ModelT = TypeVar("ModelT", bound=Base)


def not_found_error(model: type[Base], obj_id: int) -> HTTPException:
    noun = Term(model.__name__.lower()) if model.__name__.lower() in TERMS else model.__name__
    return HTTPException(status_code=404, detail=f"{noun} {obj_id} not found")


def get_or_404(db: Session, model: type[ModelT], obj_id: int) -> ModelT:
    obj = db.get(model, obj_id)
    if obj is None:
        raise not_found_error(model, obj_id)
    return obj
