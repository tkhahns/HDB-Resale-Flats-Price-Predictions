"""Pydantic v2 request/response schemas for the AVM prediction API."""

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class PredictionRequest(BaseModel):
    town: str = Field(..., examples=["TAMPINES"])
    flat_type: str = Field(..., examples=["4 ROOM"])
    storey_range: str = Field(..., examples=["07 TO 09"])
    floor_area_sqm: float = Field(..., gt=30, lt=250, examples=[95.0])
    flat_model: str = Field(..., examples=["Model A"])
    lease_commence_date: int = Field(..., ge=1960, le=2024, examples=[1998])
    remaining_lease: str = Field(..., examples=["65 years 06 months"])
    block: str = Field(..., examples=["123"])
    street_name: str = Field(..., examples=["TAMPINES AVE 1"])
    transaction_month: Optional[str] = Field(None, examples=["2024-01"])


class BatchPredictionRequest(BaseModel):
    instances: list[PredictionRequest]

    @model_validator(mode="after")
    def check_not_empty(self) -> "BatchPredictionRequest":
        if not self.instances:
            raise ValueError("instances must not be empty")
        return self


class PredictionResponse(BaseModel):
    predicted_price: float
    currency: str = "SGD"
    model_run_date: Optional[str] = None


class BatchPredictionResponse(BaseModel):
    predictions: list[PredictionResponse]


class HealthResponse(BaseModel):
    status: str


class ModelInfoResponse(BaseModel):
    model_prefix: str
    run_date: str
    metrics: dict
