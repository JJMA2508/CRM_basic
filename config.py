import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'kajita-crm-secret-key-prod-2026-kajita-online')
    
    # En Vercel el disco de la aplicación es de SOLO LECTURA, la única carpeta escribible es /tmp
    if os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV'):
        DATABASE = '/tmp/antojitos.db'
    else:
        DATABASE = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'antojitos.db'))
        
    API_KEY = os.environ.get('API_KEY', 'kajita-n8n-global-key-2026')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
