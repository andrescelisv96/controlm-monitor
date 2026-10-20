from collections import Counter

def parsear(texto: str) -> list[dict[str, str]]:
    filas = []
    for linea in texto.splitlines():
        if not linea.startswith("000"):
            continue
        filas.append({
            "orderid": linea[0:8].strip(),
            "job": linea[9:26].strip(),
            "tipo": linea[27:31].strip(),
            "odate": linea[33:41].strip(),
            "estado": linea[42:51].strip(),
            "status": linea[52:58].strip(),
            "extra": linea[76:].strip(),
        })
    return filas

def construir_prompt(filas: list[dict[str, str]], hoy: str) -> str:
    conteo = Counter(f"{f['estado']}|{f['status']}" for f in filas)
    relevantes = [f for f in filas if f["status"] == "NOTOK" or f["extra"]]
    return (
        f"Eres operador de Control-M. Hoy es {hoy}.\n"
        f"Total de órdenes: {len(filas)}\nConteo por estado: {dict(conteo)}\n"
        f"Órdenes con fallo o marcas especiales:\n{relevantes}\n"
        "Agrupa por job, detecta fallos que se repiten en varios días y prioriza. además extrae los not ok"
    )