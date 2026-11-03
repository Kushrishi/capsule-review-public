"""Strict request schemas keep reference labels, predictions and reviews separate."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class ReviewUpdate(StrictModel):
    revision: int = Field(ge=0)
    bookmarked: bool
    note: str = Field(default="", max_length=8000)
    label: str = Field(default="", max_length=120)


class PositionUpdate(StrictModel):
    position: int = Field(ge=0)


class IntervalCreate(StrictModel):
    """A reviewer's interval of *imported positions*, not clinical lesion timing."""

    start_position: int = Field(ge=0)
    end_position: int = Field(ge=0)
    note: str = Field(default="", max_length=2000)


class ImportMeta(StrictModel):
    title: str = Field(min_length=1, max_length=120)
    source: str = Field(default="Local research images", max_length=300)


class ModelInfo(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=80)
    run_id: str = Field(min_length=1, max_length=120)
    weights_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    description: str = Field(default="", max_length=1000)


class Prediction(StrictModel):
    position: int = Field(ge=0)
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    label: str = Field(min_length=1, max_length=120)
    score: float = Field(ge=0, le=1)


class PredictionImport(StrictModel):
    schema_version: Literal[1]
    study_id: str
    model: ModelInfo
    # Up to five anatomy score labels per one of 200,000 imported frames.
    # The browser's user-import size cap remains 20 MiB; local inference may
    # create a larger payload in memory without posting it over HTTP.
    predictions: Annotated[list[Prediction], Field(min_length=1, max_length=1_000_000)]


class LocalPredictionRequest(StrictModel):
    model_id: str = Field(pattern=r"^[a-f0-9]{24}$")
