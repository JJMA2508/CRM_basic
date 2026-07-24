import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    SECRET_KEY = 'antojitos-crm-2024-heladeria-colombiana-super-secret'
    DATABASE = os.path.join(BASE_DIR, 'antojitos.db')
    API_KEY = 'antojitos-n8n-key-2024'
    DEBUG = True
    HOST = '0.0.0.0'
    PORT = 5000
