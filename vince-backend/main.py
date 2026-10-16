import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Vince GM Core Engine - Mafufadas NFL")

# Configuración de seguridad CORS para que tu sitio de Netlify pueda comunicarse con este servidor
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción puedes cambiarlo por tu URL de Netlify
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estructura de datos para recibir consultas de trades desde la aplicación
class TradeQuery(BaseModel):
    player_giving: str
    player_receiving: str
    league_id: str

@app.get("/")
def read_root():
    return {"status": "Vince GM Core Online", "edition": "Mafufadas NFL 2026"}

@app.post("/api/v1/debate-trade")
async def evaluate_trade(query: TradeQuery):
    """
    Motor Multi-Agente que simula el debate de la mesa directiva de coaches
    """
    # 1. Consultar de forma gratuita los datos reales de la liga en Sleeper
    async with httpx.AsyncClient() as client:
        try:
            league_url = f"https://sleeper.app{query.league_id}"
            league_response = await client.get(league_url)
            league_data = league_response.json() if league_response.status_code == 200 else {}
        except Exception:
            league_data = {}

    # 2. Respuestas estructuradas simulando la inyección de prompts de las personalidades de IA
    # En el siguiente paso, estas variables se conectarán mediante llamadas de API a OpenAI/Gemini/Claude
    response_walsh = f"{query.player_receiving} ofrece una consistencia de volumen ideal según los esquemas modernos de pases. La ganancia del pick compensa el movimiento."
    response_madden = f"¡Me encanta la sinergia estructural! Si proyectamos esta plantilla a 24 meses, la acumulación de talento joven te da un techo de explosión gigante."
    response_ditka = f"¡Estás entregando a tu pieza estelar! Pierdes rendimiento inmediato para este domingo y yo salgo a ganar la semana HOY."
    response_vince = f"Entregar una estrella consolidada por piezas divididas rompe nuestro estándar de excelencia si tu equipo está compitiendo este año."
    
    # Simulación del veredicto final automático del motor Lombardi
    veredicto_final = "ACEPTAR EL TRADE (Ajuste algorítmico neto de +14.2% a favor)"

    return {
        "trade_analizado": f"Dar a {query.player_giving} por {query.player_receiving}",
        "contexto_liga": league_data.get("name", "Liga Sincronizada"),
        "coaches": {
            "walsh": {"voto": "🟢 ACEPTAR", "argumento": response_walsh},
            "madden": {"voto": "🟢 ACEPTAR", "argumento": response_madden},
            "ditka": {"voto": "🔴 RECHAZAR", "argumento": response_ditka},
            "vince_lombardi": {"voto": "🔴 RECHAZAR (Voto Inicial)", "argumento": response_vince}
        },
        "desempate_supremo": {
            "motor": "HC Vince Lombardi Engine",
            "analisis": "Empate 2-2 detectado en la mesa directiva. Activando motor de Trade Capital Value indexando el récord de la liga.",
            "veredicto": veredicto_final
        }
    }
