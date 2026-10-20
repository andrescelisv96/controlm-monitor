from datetime import date
from fastapi import FastAPI, Body
from app.parser import parsear, construir_prompt
from app.diagnostico import diagnosticar
from app.modelos import Diagnostico
from app import db
from fastapi import Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

app = FastAPI(title="Monitor Control-M")


@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    return templates.TemplateResponse(request, "index.html", {"diag": None, "top": db.top_jobs()})

@app.get("/salud")
def salud():
    return {"ok": True}

@app.post("/diagnostico", response_model=Diagnostico)
def crear_diagnostico(salida: str = Body(..., media_type="text/plain")):
    filas = parsear(salida)
    diag = diagnosticar(construir_prompt(filas, date.today().isoformat()))
    db.guardar(diag)
    return diag

@app.post("/ui/diagnostico", response_class=HTMLResponse)
def ui_diagnostico(request: Request, salida: str = Form(...)):
    diag = diagnosticar(construir_prompt(parsear(salida), date.today().isoformat()))
    db.guardar(diag)
    return templates.TemplateResponse(request, "index.html", {"diag": diag, "top": db.top_jobs()})

@app.get("/historico")
def historico():
    return db.ultimos()

@app.get("/jobs-problematicos")
def jobs_problematicos():
    return db.top_jobs()