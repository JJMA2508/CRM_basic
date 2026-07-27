from functools import wraps
from flask import session, redirect, url_for, flash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["500 per day", "100 per hour"]
)



def login_required(f):
    """Decorator: requiere que el usuario esté autenticado."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator: requiere rol de administrador."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('rol') != 'admin':
            flash('Acceso restringido a administradores', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated


def get_comercio_fecha(db, comercio_id):
    from datetime import datetime, timezone, timedelta
    
    # Obtener zona horaria del comercio
    row = db.execute('SELECT zona_horaria FROM comercios WHERE id = ?', (comercio_id,)).fetchone()
    tz_name = row['zona_horaria'] if (row and row['zona_horaria']) else 'America/Bogota'
    
    # Mapa de offsets de respaldo
    offsets = {
        'America/Bogota': -5,
        'America/Lima': -5,
        'America/Guayaquil': -5,
        'America/Mexico_City': -6,
        'America/Caracas': -4,
        'America/Santiago': -4,
        'America/Buenos_Aires': -3,
        'Europe/Madrid': 1
    }
    
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name)
        return datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        offset_hours = offsets.get(tz_name, -5)
        tz = timezone(timedelta(hours=offset_hours))
        return datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')


def normalizar_tipo_comercio(texto):
    if not texto:
        return 'general'
    texto = texto.lower().strip()
    
    # Palabras clave para pizzeria (restaurantes)
    if any(kw in texto for kw in ['pizza', 'pizzeria', 'restaurante', 'comida', 'cena', 'almuerzo', 'bar', 'pub', 'bistro', 'cafe', 'cafeteria', 'panaderia', 'pasteleria', 'asadero', 'mesas']):
        return 'pizzeria'
        
    # Palabras clave para heladeria
    if any(kw in texto for kw in ['helado', 'heladeria', 'crema', 'cremas', 'paleta', 'paletas', 'postre', 'postres', 'dulce', 'yogurt']):
        return 'heladeria'
        
    # Palabras clave para ferreteria
    if any(kw in texto for kw in ['ferreteria', 'herramienta', 'herramientas', 'repuesto', 'repuestos', 'taller', 'tornillo', 'pintura', 'construccion', 'materiales']):
        return 'ferreteria'
        
    # Por defecto, cualquier otra cosa es general/retail (Zapatería, Tiendas, Ropa, etc.)
    return 'general'
