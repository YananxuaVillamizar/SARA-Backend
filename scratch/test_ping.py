import sys
import os

# Agregar la raíz del proyecto al path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app

def test_ping_endpoint_route():
    print("Iniciando prueba de ruta de app.main...")
    
    # Buscar el handler del path '/ping' en la app
    ping_route = None
    for route in app.routes:
        if route.path == "/ping":
            ping_route = route
            break
            
    if not ping_route:
        print("Error: Ruta /ping no encontrada en la aplicacion FastAPI.")
        sys.exit(1)
        
    print(f"Ruta encontrada: {ping_route.path}")
    print(f"Metodos permitidos: {ping_route.methods}")
    
    # Ejecutar el endpoint handler directamente
    response = ping_route.endpoint()
    print(f"Resultado devuelto: {response}")
    
    assert response == {"status": "alive", "message": "pong"}
    print("Prueba de la ruta /ping completada con exito!")

if __name__ == "__main__":
    try:
        test_ping_endpoint_route()
    except Exception as e:
        print(f"Error en la prueba: {e}")
        sys.exit(1)
