from typing import Literal
from pydantic import BaseModel, Field

class Problema(BaseModel):
    job: str
    orderids: list[str]
    tipo: Literal["fallo_repetido", "fallo_puntual", "atascado", "hold_antiguo", "otro"]
    severidad: Literal["alta", "media", "baja"]
    explicacion: str
    accion_sugerida: str

class Diagnostico(BaseModel):
    salud_general: Literal["ok", "degradado", "critico"]
    resumen: str = Field(description="2 o 3 frases para el equipo de operaciones")
    problemas: list[Problema]
