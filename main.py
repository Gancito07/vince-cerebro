import hmac
import os
from typing import Optional

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Vince GM Core Engine - Mafufadas NFL")

# CORS abierto para que tu sitio de Netlify pueda llamar a este servidor.
# La protección real (para que nadie gaste tu clave) es el código de acceso de abajo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variables de entorno (se configuran en Render > Environment):
#   VINCE_ACCESS_CODE  -> código que la página manda en el header X-Vince-Code (recomendado)
#   ANTHROPIC_API_KEY  -> solo si quieres la función de investigación web
#   ANTHROPIC_MODEL    -> opcional, por defecto claude-sonnet-5-5
ACCESS_CODE = os.getenv("VINCE_ACCESS_CODE", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
SLEEPER = "https://api.sleeper.app/v1"


def check_access(code: Optional[str]) -> None:
    if ACCESS_CODE and not hmac.compare_digest(code or "", ACCESS_CODE):
        raise HTTPException(status_code=401, detail="Código de acceso inválido")


@app.get("/")
def read_root():
    return {
        "status": "Vince GM Core Online",
        "edition": "Mafufadas NFL 2026",
        "investigacion_web": bool(ANTHROPIC_KEY),
        "protegido_con_codigo": bool(ACCESS_CODE),
    }


# ---------------------------------------------------------------- Mesa directiva

class TradeQuery(BaseModel):
    player_giving: str = Field(max_length=300)
    player_receiving: str = Field(max_length=300)
    league_id: str = Field(default="", max_length=40)
    give_value: Optional[float] = None   # valor ajustado de lo que das (lo calcula la página)
    get_value: Optional[float] = None    # valor ajustado de lo que recibes
    give_count: int = 1
    get_count: int = 1
    dynasty: bool = False
    avg_age_give: Optional[float] = None
    avg_age_get: Optional[float] = None


def voto(acepta: bool, texto: str) -> dict:
    return {"voto": "🟢 ACEPTAR" if acepta else "🔴 RECHAZAR", "argumento": texto}


@app.post("/api/v1/debate-trade")
async def evaluate_trade(query: TradeQuery, x_vince_code: Optional[str] = Header(default=None)):
    """Mesa directiva: 4 coaches con reglas distintas votan sobre los números reales del trade."""
    check_access(x_vince_code)

    if query.give_value is None or query.get_value is None:
        raise HTTPException(status_code=422, detail="Faltan give_value y get_value: sin números no hay debate honesto.")

    # Nombre real de la liga (si Sleeper responde)
    liga = "Liga sincronizada"
    if query.league_id:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{SLEEPER}/league/{query.league_id}")
                if r.status_code == 200:
                    liga = r.json().get("name", liga)
        except Exception:
            pass

    gv, rv = query.give_value, query.get_value
    pct = (rv - gv) / max(gv, 1) * 100
    resumen = f"valor ajustado: das {gv:.0f}, recibes {rv:.0f} ({pct:+.0f}%)"

    # Walsh: consistencia y volumen. Quiere que el valor neto no baje.
    walsh = voto(pct >= 0, f"Mi regla es no perder valor neto: {resumen}. " +
                 ("Se sostiene." if pct >= 0 else "No se sostiene."))

    # Madden: le gusta la profundidad y, en Dynasty, la juventud. Tolera una pequeña pérdida.
    umbral_madden = -8.0
    nota_edad = ""
    if query.dynasty and query.avg_age_give and query.avg_age_get and query.avg_age_get < query.avg_age_give - 1:
        umbral_madden = -15.0
        nota_edad = f" Además recibes talento más joven ({query.avg_age_get:.1f} vs {query.avg_age_give:.1f} años)."
    madden = voto(pct >= umbral_madden, f"Tolero hasta {abs(umbral_madden):.0f}% de pérdida por futuro; {resumen}.{nota_edad}")

    # Ditka: gana hoy. Solo acepta si la mejora es clara.
    ditka = voto(pct >= 12, f"Yo juego para ganar este domingo: necesito al menos +12% y aquí hay {pct:+.0f}%.")

    # Lombardi: excelencia y consolidación (regla Premium Talent).
    consolidacion = query.give_count == 1 and query.get_count >= 2
    if consolidacion and pct < 25:
        lombardi = voto(False, f"Entregar una pieza consolidada por {query.get_count} piezas divididas exige mucho más que {pct:+.0f}%. Regla Premium Talent.")
    else:
        lombardi = voto(pct >= 10, f"Exijo un margen claro de +10%: {resumen}.")

    votos = [walsh, madden, ditka, lombardi]
    a_favor = sum(1 for v in votos if "ACEPTAR" in v["voto"])

    if pct >= 12 and not (consolidacion and pct < 25):
        veredicto = "🟢 ACEPTAR"
    elif pct <= -12 or (consolidacion and pct < 25 and pct < 0):
        veredicto = "🔴 RECHAZAR"
    else:
        veredicto = "🟡 CONTRAOFERTA (pide un pick extra de 2.ª o 3.ª ronda)"

    return {
        "trade_analizado": f"Dar a {query.player_giving} por {query.player_receiving}",
        "contexto_liga": liga,
        "coaches": {"walsh": walsh, "madden": madden, "ditka": ditka, "vince_lombardi": lombardi},
        "desempate_supremo": {
            "motor": "Motor de reglas Vince (no es IA)",
            "analisis": f"Votos a favor: {a_favor} de 4. Diferencia neta: {pct:+.0f}%.",
            "veredicto": veredicto,
        },
        "aviso": "Valores aproximados a partir del ranking de Sleeper; no son precios de mercado (KTC).",
    }


# ---------------------------------------------------------------- Investigación web

class ResearchQuery(BaseModel):
    question: str = Field(min_length=3, max_length=600)
    league_context: Optional[str] = Field(default=None, max_length=600)


@app.post("/api/v1/research")
async def research(q: ResearchQuery, x_vince_code: Optional[str] = Header(default=None)):
    """Investiga en la web con Claude (requiere ANTHROPIC_API_KEY en Render)."""
    check_access(x_vince_code)
    if not ANTHROPIC_KEY:
        raise HTTPException(status_code=503, detail="La investigación web no está activada: falta ANTHROPIC_API_KEY en Render.")

    system = (
        "Eres Vince GM, analista de fantasy football de la NFL para el podcast Mafufadas NFL. "
        "Responde en español, claro y en máximo 250 palabras. Usa la búsqueda web para datos actuales "
        "(lesiones, depth chart, noticias, snaps). No inventes cifras: si no encuentras algo, dilo."
    )
    contenido = q.question + (f"\n\nContexto de mi liga: {q.league_context}" if q.league_context else "")
    body = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1200,
        "system": system,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
        "messages": [{"role": "user", "content": contenido}],
    }
    headers = {"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post("https://api.anthropic.com/v1/messages", json=body, headers=headers)
    except Exception:
        raise HTTPException(status_code=502, detail="No pude contactar a Anthropic.")
    if r.status_code != 200:
        try:
            msg = r.json().get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise HTTPException(status_code=502, detail=f"Anthropic respondió {r.status_code}. {msg}"[:300])

    data = r.json()
    texto, fuentes, vistos = [], [], set()
    for bloque in data.get("content", []):
        if bloque.get("type") == "text":
            texto.append(bloque.get("text", ""))
        elif bloque.get("type") == "web_search_tool_result" and isinstance(bloque.get("content"), list):
            for it in bloque["content"]:
                url = it.get("url")
                if url and url not in vistos:
                    vistos.add(url)
                    fuentes.append({"title": it.get("title", url), "url": url})
    return {"respuesta": "".join(texto).strip(), "fuentes": fuentes[:8]}
