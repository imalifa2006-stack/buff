from typing import Optional
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

USERNAME_RE = re.compile(r"^[A-Za-z0-9_\u0600-\u06FF]{3,24}$")


class TgAuth(BaseModel):
    init_data: str


class RegisterIn(BaseModel):
    init_data: str
    username: str
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    invite_code: Optional[str] = None
    field: Literal["r", "t", "e"]
    grade: Literal["10", "11", "12", "grad"]

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        v = v.strip()
        if not USERNAME_RE.match(v):
            raise ValueError("username must be 3-24 letters, digits or underscore")
        return v


class LoginIn(BaseModel):
    username: str
    password: str


class EntryIn(BaseModel):
    subject_id: int
    minutes: int = Field(0, ge=0, le=1440)
    tests: int = Field(0, ge=0, le=1000)
    correct: int = Field(0, ge=0)
    wrong: int = Field(0, ge=0)

    @model_validator(mode="after")
    def _check(self):
        if self.correct + self.wrong > self.tests:
            raise ValueError("correct + wrong cannot exceed tests")
        if self.minutes == 0 and self.tests == 0:
            raise ValueError("minutes or tests required")
        return self


class ReportIn(BaseModel):
    sleep_hours: float = Field(ge=0, le=16)
    mood: int = Field(ge=0, le=4)
    focus: int = Field(ge=1, le=5)
    note: str = Field("", max_length=300)
    entries: list[EntryIn] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def _unique(self):
        ids = [e.subject_id for e in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate subject")
        return self
