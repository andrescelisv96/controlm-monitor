import sys, time, statistics, json, os
sys.path.insert(0, ".")
from app.modelos import Diagnostico
from app.parser import parsear, construir_prompt

MODELO = os.getenv("MODELO", "gemini-3.8-flash").split(":")[-1].split("/")[-1]
N = 3
PAUSA_S = 10  # entre llamadas, para no chocar con el límite por minuto
prompt = construir_prompt(parsear(open("data/controlm.txt", encoding="utf-8").read()), "2026-10-16")

from google import genai
g = genai.Client()

# --- A. Instructor ---
import instructor
inst = instructor.from_provider(f"google/{MODELO}")
def con_instructor():
    intentos = {"n": 0}
    inst.on("completion:kwargs", lambda *a, **k: intentos.__setitem__("n", intentos["n"] + 1))
    try:
        obj, raw = inst.chat.completions.create_with_completion(
            response_model=Diagnostico, max_retries=3, strict=False,
            messages=[{"role": "user", "content": prompt}])
    finally:
        inst.clear("completion:kwargs")
    return obj, intentos["n"], raw.usage_metadata.total_token_count

# --- B. Structured output nativo de Gemini ---
def nativo():
    r = g.models.generate_content(
        model=MODELO, contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": Diagnostico})
    obj = Diagnostico.model_validate_json(r.text)  # sin reintentos: si falla, falla
    return obj, 1, r.usage_metadata.total_token_count

# --- C. Pydantic AI ---
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
from pydantic_ai import Agent
agente = Agent(f"google:{MODELO}", output_type=Diagnostico, retries=3)
def pydantic_ai():
    r = agente.run_sync(prompt)
    u = r.usage
    return r.output, u.requests, u.total_tokens

resultados = {}
primera = True
for nombre, fn in [("instructor", con_instructor), ("nativo", nativo), ("pydantic_ai", pydantic_ai)]:
    ok, intentos, tokens, tiempos, n_problemas = 0, [], [], [], []
    for i in range(N):
        if not primera:
            time.sleep(PAUSA_S)  # fuera de la medición de tiempo
        primera = False
        t0 = time.time()
        try:
            obj, it, tk = fn()
            ok += 1; intentos.append(it); tokens.append(tk or 0)
            n_problemas.append(len(obj.problemas))
        except Exception as e:
            print(f"{nombre} falló: {str(e)[:200]}")
        tiempos.append(time.time() - t0)
    print(nombre, statistics.mean(intentos), statistics.mean(tokens), statistics.mean(tiempos))
    resultados[nombre] = {
        "exito_%": round(100 * ok / N, 1),
        "intentos_prom": round(statistics.mean(intentos), 2) if intentos else None,
        "tokens_prom": round(statistics.mean(tokens)) if tokens else None,
        "tiempo_prom_s": round(statistics.mean(tiempos), 2),
        "problemas_detectados": n_problemas,
    }
    print(nombre, resultados[nombre])

json.dump(resultados, open("bench/resultados.json", "w"), indent=2)