import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import Flask, redirect, url_for, session
from config import Config
from database import init_db, close_db
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.ventas import ventas_bp
from routes.productos import productos_bp
from routes.clientes import clientes_bp
from routes.reportes import reportes_bp
from routes.api import api_bp
from routes.config import config_bp
from routes.compras import compras_bp
from routes.caja import caja_bp
from routes.superadmin import superadmin_bp
from routes.usuarios import usuarios_bp
from flask_wtf.csrf import CSRFProtect
from utils import limiter

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializar extensiones de seguridad
    csrf.init_app(app)
    csrf.exempt(api_bp)  # Las peticiones de la API (n8n/automatización) no necesitan CSRF token
    
    limiter.init_app(app)

    # Inicializar BD al arrancar
    with app.app_context():
        init_db()

    # Cerrar BD al finalizar cada request
    app.teardown_appcontext(close_db)

    # Registrar filtro de moneda global adaptativo
    @app.template_filter('formatear_moneda')
    def formatear_moneda(valor):
        simbolo = session.get('comercio_moneda_simbolo', '$')
        try:
            # Si tiene decimales, redondear
            val_int = int(round(float(valor)))
            return f"{simbolo}{val_int:,}".replace(',', '.')
        except Exception:
            return f"{simbolo}{valor}"

    @app.before_request
    def verificar_suscripcion_comercio():
        from flask import request, g, flash
        from database import get_db
        from datetime import datetime
        from utils import get_comercio_fecha
        
        g.suscripcion_alerta = None
        
        # No bloquear rutas de autenticación, estáticos ni API
        if 'user_id' in session and request.endpoint and not request.endpoint.startswith('auth.') and not request.endpoint.startswith('static') and not request.endpoint.startswith('api.'):
            db = get_db()
            
            # Si el rol es superadmin, no restringir!
            if session.get('rol') == 'superadmin':
                return
                
            comercio = db.execute('SELECT activo, fecha_ultimo_pago FROM comercios WHERE id = ?', (session['comercio_id'],)).fetchone()
            if not comercio:
                return
                
            # Calcular días restantes de suscripción (30 días de ciclo)
            fecha_actual_str = get_comercio_fecha(db, session['comercio_id'])
            fmt = '%Y-%m-%d %H:%M:%S'
            
            try:
                ultimo_pago_val = comercio['fecha_ultimo_pago'] if comercio['fecha_ultimo_pago'] else fecha_actual_str
                dt_ultimo_pago = datetime.strptime(ultimo_pago_val[:19], fmt)
            except Exception:
                dt_ultimo_pago = datetime.strptime(fecha_actual_str[:19], fmt)
                
            try:
                dt_actual = datetime.strptime(fecha_actual_str[:19], fmt)
            except Exception:
                dt_actual = datetime.now()
                
            dias_transcurridos = (dt_actual - dt_ultimo_pago).days
            dias_restantes = 30 - dias_transcurridos
            
            # Si ya pasaron los 30 días, suspender automáticamente
            if dias_restantes <= 0:
                if comercio['activo'] == 1:
                    db.execute('UPDATE comercios SET activo = 0 WHERE id = ?', (session['comercio_id'],))
                    db.commit()
                session.clear()
                flash('⚠️ Su suscripción mensual ha vencido. Por favor, realice su pago con el administrador para reactivar el acceso.', 'danger')
                return redirect(url_for('auth.login'))
                
            # Si el comercio fue suspendido manualmente por el superadmin
            if comercio['activo'] == 0:
                session.clear()
                flash('⚠️ Su cuenta ha sido suspendida. Por favor, comuníquese con el administrador del sistema.', 'danger')
                return redirect(url_for('auth.login'))
                
            # Si quedan 3 días o menos, alertar en la interfaz
            if 0 < dias_restantes <= 3:
                g.suscripcion_alerta = dias_restantes

    # Registrar blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(ventas_bp)
    app.register_blueprint(productos_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(reportes_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(compras_bp)
    app.register_blueprint(caja_bp)
    app.register_blueprint(superadmin_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    @app.route('/')
    def index():
        from flask import session
        if 'user_id' in session:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))

    @app.route('/precios')
    def precios():
        from flask import render_template
        return render_template('landing.html')

    @app.route('/robots.txt')
    def robots():
        from flask import Response
        content = """User-agent: *
Allow: /
Allow: /precios
Allow: /login
Disallow: /dashboard/
Disallow: /ventas/
Disallow: /superadmin/
Disallow: /api/

Sitemap: https://kajita.online/sitemap.xml
"""
        return Response(content, mimetype='text/plain')

    @app.route('/sitemap.xml')
    def sitemap():
        from flask import Response
        content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://kajita.online/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://kajita.online/precios</loc>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://kajita.online/login</loc>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>"""
        return Response(content, mimetype='application/xml')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(
        host=app.config.get('HOST', '0.0.0.0'),
        port=app.config.get('PORT', 5000),
        debug=app.config.get('DEBUG', False)
    )
