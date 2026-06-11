import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, usuarios, asistencias, admin, contingencias, matriculas, hardware, dashboard

# Esto crea la aplicación FastAPI — es el restaurante
app = FastAPI(
    title="SARA API",
    description="Sistema Automatizado de Registro de Asistencia",
    version="1.0.0"
)

# CORS: permite que el dashboard web (que corre en otro puerto)
# pueda hablar con esta API. Sin esto, el navegador bloquea las peticiones.
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.migrations import run_migrations
import asyncio
from app.database import get_connection
from app.reconciliation import conciliar_sesiones_pasadas

async def periodic_reconciliation():
    while True:
        try:
            print("[BACKGROUND TASK] Running sessions reconciliation...")
            loop = asyncio.get_running_loop()
            def run_sync():
                conn = get_connection()
                try:
                    conciliar_sesiones_pasadas(conn)
                finally:
                    conn.close()
            await loop.run_in_executor(None, run_sync)
        except Exception as e:
            print(f"[BACKGROUND TASK ERROR] Error in periodic_reconciliation: {e}")
        await asyncio.sleep(300) # Every 5 minutes

@app.on_event("startup")
def startup_event():
    run_migrations()
    asyncio.create_task(periodic_reconciliation())

# Registrar los routers — son como las secciones del menú del restaurante
# Cada router agrupa endpoints relacionados
app.include_router(auth.router,        prefix="/auth",        tags=["Autenticación"])
app.include_router(usuarios.router,    prefix="/usuarios",    tags=["Usuarios"])
app.include_router(asistencias.router, prefix="/asistencias", tags=["Asistencias"])
app.include_router(admin.router, prefix="/admin", tags=["Administración"])
app.include_router(contingencias.router, prefix="/contingencias", tags=["Contingencias y Sesiones"])
app.include_router(matriculas.router, prefix="/matriculas", tags=["Matrículas"])
app.include_router(hardware.router, prefix="/hardware", tags=["Hardware / ESP32"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Estadísticas / Dashboard"])

# Endpoint raíz — solo para verificar que la API está viva
@app.get("/")
def root():
    return {
        "sistema": "SARA",
        "version": "1.0.0",
        "estado": "funcionando ✅"
    }

# Endpoint de Keep-Alive para cron-job.org
@app.get("/ping")
def ping():
    return {
        "status": "alive",
        "message": "pong"
    }