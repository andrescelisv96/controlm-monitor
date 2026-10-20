import time
from datetime import date
import instructor  # pyright: ignore[reportMissingImports]
from pydantic import BaseModel, Field, field_validator

# 1. La forma que debe tener la respuesta
class Item(BaseModel):
    descripcion: str
    cantidad: int = Field(gt=0)
    precio_unitario: float = Field(ge=0)

class Factura(BaseModel):
    numero: str
    fecha: date
    proveedor: str
    nit: str
    items: list[Item]
    total: float

    # 2. Regla: el total debe cuadrar con los items
    @field_validator("total")
    @classmethod
    def total_cuadra(cls, v, info):
        items = info.data.get("items", [])
        suma = sum(i.cantidad * i.precio_unitario for i in items)
        if items and abs(suma - v) > 0.01:
            raise ValueError(f"El total {v} no cuadra con la suma de los items ({suma})")
        return v
    
    


# 3. Contadores para medir
stats = {"llamadas": 0, "errores_validacion": 0}

def contar_llamada(*args, **kwargs):
    stats["llamadas"] += 1

def contar_error(error):
    stats["errores_validacion"] += 1
    print(f"  Validación falló: {error}")

# 4. Cliente (usa UNA de las dos líneas)
client = instructor.from_provider("google/gemini-3.8-flash")
# client = instructor.from_provider("bedrock/anthropic.claude-3-5-haiku-20241022-v1:0")

client.on("completion:kwargs", contar_llamada)
client.on("parse:error", contar_error)

# 5. Extraer
texto = open("factura.txt", encoding="utf-8").read()
inicio = time.time()

factura = client.chat.completions.create(
    response_model=Factura,
    max_retries=3,
    strict=False,
    messages=[{"role": "user", "content": f"Extrae los datos de esta factura:\n\n{texto}"}],
)
# 6. Resultados
print("\nFactura extraída:")
print(factura.model_dump_json(indent=2))
print(f"\nTotal como número: {factura.total}")
print(f"Llamadas al modelo: {stats['llamadas']}")
print(f"Reintentos: {stats['llamadas'] - 1}")
print(f"Errores de validación: {stats['errores_validacion']}")
print(f"Tiempo: {time.time() - inicio:.2f} s")


from collections import Counter
from typing import Literal
from pydantic import BaseModel, Field

# --- 1. Parseo determinístico (sin LLM) ---
def parsear(texto):
    filas = []
    for linea in texto.splitlines():
        if not linea.startswith("0"):   # las órdenes empiezan con 000...
            continue
        filas.append({
            "orderid": linea[0:8].strip(),
            "job": linea[9:26].strip(),
            "tipo": linea[27:31].strip(),
            "odate": linea[33:41].strip(),
            "estado": linea[42:51].strip(),
            "status": linea[52:58].strip(),
            "extra": linea[76:].strip(),   # Hold, Deleted...
        })
    return filas

# --- 2. Lo que queremos que devuelva el LLM ---
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

texto = open("activo.txt", encoding="utf-8").read()
filas = parsear(texto)

# Solo mandamos al LLM lo relevante: fallos, holds y conteos
conteo = Counter((f["estado"], f["status"]) for f in filas)
relevantes = [f for f in filas if f["status"] == "NOTOK" or f["extra"]]

client = instructor.from_provider("google/gemini-3.8-flash")
diag = client.chat.completions.create(
    response_model=Diagnostico,
    max_retries=3,
    strict=False,
    messages=[{"role": "user", "content":
        f"Eres operador de Control-M. Hoy es 2026-10-16.\n"
        f"Total órdenes: {len(filas)}\nConteo por estado: {dict(conteo)}\n"
        f"Órdenes con fallo o marcas especiales:\n{relevantes}\n"
        "Agrupa por job, detecta fallos que se repiten en varios días y prioriza."}],
)

print(f"Órdenes parseadas: {len(filas)}")
print(diag.model_dump_json(indent=2))