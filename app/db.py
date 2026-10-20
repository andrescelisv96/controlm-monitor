import sqlite3, json
from datetime import datetime

RUTA = "data/historico.db"

def conectar():
    con = sqlite3.connect(RUTA)
    con.execute("""CREATE TABLE IF NOT EXISTS diagnosticos (
        id INTEGER PRIMARY KEY, fecha TEXT, salud TEXT, resumen TEXT, json TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS problemas (
        diag_id INTEGER, job TEXT, tipo TEXT, severidad TEXT)""")
    return con

def guardar(diag) -> int:
    con = conectar()
    cur = con.execute("INSERT INTO diagnosticos (fecha, salud, resumen, json) VALUES (?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), diag.salud_general,
         diag.resumen, diag.model_dump_json()))
    for p in diag.problemas:
        con.execute("INSERT INTO problemas VALUES (?,?,?,?)",
                    (cur.lastrowid, p.job, p.tipo, p.severidad))
    con.commit()
    row_id = cur.lastrowid
    if row_id is None:
        raise RuntimeError("El INSERT no devolvió lastrowid")
    return row_id

def top_jobs(limite=10):
    con = conectar()
    filas = con.execute("""SELECT job, COUNT(*) AS veces,
        SUM(severidad='alta') AS altas FROM problemas
        GROUP BY job ORDER BY veces DESC LIMIT ?""", (limite,)).fetchall()
    return [{"job": j, "veces": v, "altas": a} for j, v, a in filas]

def ultimos(limite=20):
    con = conectar()
    filas = con.execute("SELECT id, fecha, salud, resumen FROM diagnosticos ORDER BY id DESC LIMIT ?",
                        (limite,)).fetchall()
    return [{"id": i, "fecha": f, "salud": s, "resumen": r} for i, f, s, r in filas]