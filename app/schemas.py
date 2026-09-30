"""Esquemas Pydantic y validadores estrictos para ventanas de telemetría."""
import math
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.settings import FEATURES, TELEMETRY_FEATURES


class WindowInput(BaseModel):
    """Representa una ventana temporal agregada de 10 minutos para un recurso."""
    model_config = ConfigDict(extra="forbid")

    resource_id: Optional[str] = Field(default="node:dl380-01", description="Identificador del nodo, VM o sensor")
    cpu_mean: float = Field(ge=0.0, le=100.0, allow_inf_nan=False, description="Uso medio de CPU en porcentaje")
    cpu_max: float = Field(ge=0.0, le=100.0, allow_inf_nan=False, description="Uso pico de CPU en porcentaje")
    cpu_std: float = Field(ge=0.0, le=50.0, allow_inf_nan=False, description="Desviación estándar del uso de CPU")
    cpu_trend: float = Field(ge=-50.0, le=50.0, allow_inf_nan=False, description="Pendiente / tendencia de CPU en la ventana")
    memory_pct_mean: float = Field(ge=0.0, le=100.0, allow_inf_nan=False, description="Uso promedio de memoria RAM en porcentaje")
    memory_pct_max: float = Field(ge=0.0, le=100.0, allow_inf_nan=False, description="Uso pico de memoria RAM en porcentaje")
    memory_pct_trend: float = Field(ge=-50.0, le=50.0, allow_inf_nan=False, description="Tendencia de acumulación de memoria RAM")
    iowait_mean: float = Field(ge=0.0, le=100.0, allow_inf_nan=False, description="Porcentaje promedio de espera I/O")
    iowait_max: float = Field(ge=0.0, le=100.0, allow_inf_nan=False, description="Porcentaje pico de espera I/O")
    net_io_mb_s: float = Field(ge=0.0, le=500.0, allow_inf_nan=False, description="Tasa de transferencia de red en MB/s")
    temp_max_c: float = Field(ge=15.0, le=120.0, allow_inf_nan=False, description="Temperatura máxima registrada en °C")

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
