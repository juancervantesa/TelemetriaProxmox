"""Pydantic schemas and strict validators for telemetry window inputs."""
import math
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.settings import FEATURES, TELEMETRY_FEATURES


class WindowInput(BaseModel):
    """Represents an aggregated 10-minute telemetry window for a resource."""
    model_config = ConfigDict(extra="forbid")

    resource_id: Optional[str] = Field(default="node:dl380-01", description="Identifier of node, VM or sensor")
    cpu_mean: float = Field(ge=0.0, le=100.0, allow_inf_nan=False, description="Average CPU usage in percentage")
    cpu_max: float = Field(ge=0.0, le=100.0, allow_inf_nan=False, description="Peak CPU usage in percentage")
    cpu_std: float = Field(ge=0.0, le=50.0, allow_inf_nan=False, description="Standard deviation of CPU usage")
    cpu_trend: float = Field(ge=-50.0, le=50.0, allow_inf_nan=False, description="Slope / trend of CPU over window")
    memory_pct_mean: float = Field(ge=0.0, le=100.0, allow_inf_nan=False, description="Average RAM usage in percentage")
    memory_pct_max: float = Field(ge=0.0, le=100.0, allow_inf_nan=False, description="Peak RAM usage in percentage")
    memory_pct_trend: float = Field(ge=-50.0, le=50.0, allow_inf_nan=False, description="Memory accumulation trend")
    iowait_mean: float = Field(ge=0.0, le=100.0, allow_inf_nan=False, description="Average I/O wait percentage")
    iowait_max: float = Field(ge=0.0, le=100.0, allow_inf_nan=False, description="Peak I/O wait percentage")
    net_io_mb_s: float = Field(ge=0.0, le=500.0, allow_inf_nan=False, description="Network throughput in MB/s")
    temp_max_c: float = Field(ge=15.0, le=120.0, allow_inf_nan=False, description="Maximum sensor temperature in °C")

    @field_validator(*FEATURES, mode="before")
    @classmethod
    def require_finite_numeric(cls, value, info):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Feature '{info.field_name}' must be a finite numeric value.")
        return float(value)

    @model_validator(mode="after")
    def validate_logical_consistency(self):
        if self.cpu_max < self.cpu_mean:
            raise ValueError(f"cpu_max ({self.cpu_max}) cannot be lower than cpu_mean ({self.cpu_mean}).")
        if self.memory_pct_max < self.memory_pct_mean:
            raise ValueError(f"memory_pct_max ({self.memory_pct_max}) cannot be lower than memory_pct_mean ({self.memory_pct_mean}).")
        if self.iowait_max < self.iowait_mean:
            raise ValueError(f"iowait_max ({self.iowait_max}) cannot be lower than iowait_mean ({self.iowait_mean}).")
        return self


class ScenarioResponse(BaseModel):
    id: str
    name: str
    description: str
    expected_alert: bool
    values: dict[str, float]
