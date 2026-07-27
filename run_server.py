import os
import sys
from waitress import serve
from app import create_app

# Asegurar que la ruta base esté en sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    
    print(f"=====================================================")
    print(f" [SaaS] Iniciando servidor WSGI Waitress en Windows")
    print(f" Servidor disponible en: http://localhost:{port}")
    print(f"=====================================================")
    
    serve(app, host=host, port=port, threads=6)
