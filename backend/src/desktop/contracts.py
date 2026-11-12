"""Closed requests. No shell, arbitrary executable, absolute path or generated code."""
import re
from typing import Annotated, Literal, Union
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class NamedFile(Closed):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def safe_name(cls, value):
        # Flat workspace in v1. Reject ADS, UNC, traversal, device aliases and
        # Windows normalization tricks identically on every test platform.
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _().-]*\.(txt|md|csv|json)", value)
                or ".." in value or value.endswith((" ", "."))
                or re.match(r"^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.| )", value, re.I)):
            raise ValueError("Use a plain text filename inside the selected workspace")
        return value


class ListFiles(Closed):
    operation: Literal["list_files"]


class ReadText(NamedFile):
    operation: Literal["read_text"]


class CreateText(NamedFile):
    operation: Literal["create_text"]
    text: str = Field(max_length=16000)


class OpenApp(Closed):
    operation: Literal["open_app"]
    app: Literal["notepad", "explorer"]


Action = Annotated[Union[ListFiles, ReadText, CreateText, OpenApp], Field(discriminator="operation")]


class RequestIdentity(Closed):
    request_id: str
    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    expires_at: int

    @field_validator("request_id")
    @classmethod
    def uuid4(cls, value):
        parsed = UUID(value)
        if parsed.version != 4 or str(parsed) != value:
            raise ValueError("Canonical UUID4 required")
        return value


class ActionRequest(RequestIdentity):
    action: Action


class CommandRequest(RequestIdentity):
    text: str = Field(min_length=1, max_length=18000)
    last_file: str | None = None

    @field_validator("last_file")
    @classmethod
    def reference(cls, value):
        return NamedFile(name=value).name if value is not None else None
