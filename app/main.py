from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, usuarios, asistencias, admin, contingencias, matriculas

# Esto crea la aplicación FastAPI — es el restaurante
app = FastAPI(
    title="SARA API",
    description="Sistema Automatizado de Registro de Asistencia",
    version="1.0.0"
)

# CORS: permite que el dashboard web (que corre en otro puerto)
# pueda hablar con esta API. Sin esto, el navegador bloquea las peticiones.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción esto se limita al dominio real
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar los routers — son como las secciones del menú del restaurante
# Cada router agrupa endpoints relacionados
app.include_router(auth.router,        prefix="/auth",        tags=["Autenticación"])
app.include_router(usuarios.router,    prefix="/usuarios",    tags=["Usuarios"])
app.include_router(asistencias.router, prefix="/asistencias", tags=["Asistencias"])
app.include_router(admin.router, prefix="/admin", tags=["Administración"])
app.include_router(contingencias.router, prefix="/contingencias", tags=["Contingencias y Sesiones"])
app.include_router(matriculas.router, prefix="/matriculas", tags=["Matrículas"])

# Endpoint raíz — solo para verificar que la API está viva
@app.get("/")
def root():
    return {
        "sistema": "SARA",
        "version": "1.0.0",
        "estado": "funcionando ✅"
    }