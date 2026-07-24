from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db
from utils import login_required, normalizar_tipo_comercio
from werkzeug.security import generate_password_hash
import os
from functools import wraps

superadmin_bp = Blueprint('superadmin', __name__)


def superadmin_required(f):
    """Decorator: requiere rol de superadmin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('rol') != 'superadmin':
            flash('Acceso restringido a Superadministradores del Sistema', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated


@superadmin_bp.route('/superadmin')
@superadmin_required
def index():
    db = get_db()
    
    # Métricas Globales del SaaS
    stats = {}
    stats['total_comercios'] = db.execute('SELECT COUNT(*) FROM comercios').fetchone()[0]
    stats['total_usuarios'] = db.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0]
    stats['total_ventas'] = db.execute('SELECT COALESCE(SUM(total), 0) FROM ventas WHERE anulada = 0').fetchone()[0]
    stats['total_compras'] = db.execute('SELECT COALESCE(SUM(total), 0) FROM compras').fetchone()[0]
    stats['total_gastos'] = db.execute('SELECT COALESCE(SUM(monto), 0) FROM gastos').fetchone()[0]
    
    # Listado de Comercios
    comercios = db.execute('''
        SELECT c.*, 
               (SELECT email FROM usuarios WHERE comercio_id = c.id AND rol = 'admin' LIMIT 1) as admin_email,
               (SELECT nombre FROM usuarios WHERE comercio_id = c.id AND rol = 'admin' LIMIT 1) as admin_nombre,
               (SELECT COUNT(*) FROM usuarios WHERE comercio_id = c.id) as cant_usuarios,
               (SELECT COUNT(*) FROM productos WHERE comercio_id = c.id AND activo = 1) as cant_productos,
               (SELECT COALESCE(SUM(total), 0) FROM ventas WHERE comercio_id = c.id AND anulada = 0) as total_ventas
        FROM comercios c
        ORDER BY c.id DESC
    ''').fetchall()
    
    return render_template('superadmin.html', stats=stats, comercios=comercios)


@superadmin_bp.route('/superadmin/comercios/nuevo', methods=['POST'])
@superadmin_required
def nuevo_comercio():
    db = get_db()
    
    nombre = request.form.get('nombre', '').strip()
    tipo = request.form.get('tipo', '').strip()
    owner_nombre = request.form.get('owner_nombre', '').strip()
    owner_email = request.form.get('owner_email', '').strip().lower()
    owner_password = request.form.get('owner_password', '')
    telefono_codigo = request.form.get('telefono_codigo', '').strip()
    telefono_numero = request.form.get('telefono_numero', '').strip()
    pais = request.form.get('pais', '').strip()

    telefono = f"{telefono_codigo} {telefono_numero}".strip()
    pais_tz = {
        'CO': 'America/Bogota',
        'MX': 'America/Mexico_City',
        'PE': 'America/Lima',
        'ES': 'Europe/Madrid',
        'VE': 'America/Caracas',
        'AR': 'America/Buenos_Aires',
        'EC': 'America/Guayaquil',
        'CL': 'America/Santiago'
    }
    zona_horaria = pais_tz.get(pais, 'America/Bogota')
    
    if not (nombre and tipo and owner_nombre and owner_email and owner_password):
        flash('Todos los campos son requeridos', 'warning')
        return redirect(url_for('superadmin.index'))
        
    # Validar que el correo no esté tomado
    existente = db.execute('SELECT id FROM usuarios WHERE email = ?', (owner_email,)).fetchone()
    if existente:
        flash('El correo del administrador ya está en uso', 'danger')
        return redirect(url_for('superadmin.index'))
        
    # Normalizar el tipo de negocio
    tipo = normalizar_tipo_comercio(tipo)
    
    # Emoji por tipo
    emojis = {'heladeria': '🍦', 'pizzeria': '🍕', 'ferreteria': '🛠️', 'general': '🏪'}
    emoji = emojis.get(tipo, '🏪')
    api_key = f"key-{tipo}-{os.urandom(4).hex()}"
    
    try:
        control_mesas_val = 1 if tipo == 'pizzeria' else 0
        cur = db.execute('''
            INSERT INTO comercios (nombre, tipo, logo_emoji, api_key, telefono, zona_horaria, control_mesas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (nombre, tipo, emoji, api_key, telefono, zona_horaria, control_mesas_val))
        comercio_id = cur.lastrowid
        
        # Crear Usuario Admin
        db.execute('''
            INSERT INTO usuarios (comercio_id, nombre, email, password_hash, rol)
            VALUES (?, ?, ?, ?, 'admin')
        ''', (comercio_id, owner_nombre, owner_email, generate_password_hash(owner_password)))
        
        # Crear datos iniciales (Seed)
        if tipo == 'heladeria':
            productos = [
                ('Helado Fresa', 'Helados', 'Por bola', 4000),
                ('Helado Chocolate', 'Helados', 'Por bola', 4000),
            ]
            for prod_nombre, cat, var, prec in productos:
                db.execute('INSERT INTO productos (comercio_id, nombre, categoria, variante, precio) VALUES (?, ?, ?, ?, ?)',
                           (comercio_id, prod_nombre, cat, var, prec))
                           
        elif tipo == 'pizzeria':
            # Mesas
            for m in ['Mesa 1', 'Mesa 2', 'Mesa 3']:
                db.execute('INSERT INTO mesas (comercio_id, numero, estado) VALUES (?, ?, "Libre")', (comercio_id, m))
            # Productos
            productos = [
                ('Pizza Napolitana', 'Pizzas', 'Personal', 14000),
                ('Gaseosa 1.5L', 'Bebidas', 'Familiar', 6000),
            ]
            for prod_nombre, cat, var, prec in productos:
                db.execute('INSERT INTO productos (comercio_id, nombre, categoria, variante, precio) VALUES (?, ?, ?, ?, ?)',
                           (comercio_id, prod_nombre, cat, var, prec))
                           
        elif tipo == 'ferreteria':
            productos = [
                ('Alicate de Presion', 'Herramientas', 'Unidad', 15000, 9500, 10, 2, 'Stanley', 'Unidad'),
            ]
            for prod_nombre, cat, var, prec, cost, stock, stock_min, marca, unid in productos:
                db.execute('''
                    INSERT INTO productos (comercio_id, nombre, categoria, variante, precio, costo, stock, stock_minimo, marca, unidad_medida)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (comercio_id, prod_nombre, cat, var, prec, cost, stock, stock_min, marca, unid))
                
        db.commit()
        flash(f'✅ Comercio "{nombre}" y su administrador creados exitosamente', 'success')
    except Exception as e:
        db.rollback()
        flash(f'❌ Error al crear comercio: {e}', 'danger')
        
    return redirect(url_for('superadmin.index'))


@superadmin_bp.route('/superadmin/comercios/<int:cid>/eliminar', methods=['POST'])
@superadmin_required
def eliminar_comercio(cid):
    if cid == session.get('comercio_id'):
        flash('No puedes eliminar el comercio en el que estás logueado actualmente', 'warning')
        return redirect(url_for('superadmin.index'))
        
    db = get_db()
    db.execute('DELETE FROM comercios WHERE id = ?', (cid,))
    db.commit()
    flash('🗑️ Comercio y todos sus datos relacionados eliminados permanentemente', 'success')
    return redirect(url_for('superadmin.index'))


@superadmin_bp.route('/superadmin/comercios/<int:cid>/regenerar_key', methods=['POST'])
@superadmin_required
def regenerar_key(cid):
    db = get_db()
    comercio = db.execute('SELECT tipo FROM comercios WHERE id = ?', (cid,)).fetchone()
    if not comercio:
        flash('Comercio no encontrado', 'danger')
        return redirect(url_for('superadmin.index'))
        
    nueva_key = f"key-{comercio['tipo']}-{os.urandom(4).hex()}"
    db.execute('UPDATE comercios SET api_key = ? WHERE id = ?', (nueva_key, cid))
    db.commit()
    flash('🔑 API Key regenerada exitosamente', 'success')
    return redirect(url_for('superadmin.index'))


@superadmin_bp.route('/superadmin/comercios/<int:cid>/toggle_estado', methods=['POST'])
@superadmin_required
def toggle_estado(cid):
    db = get_db()
    comercio = db.execute('SELECT nombre, activo FROM comercios WHERE id = ?', (cid,)).fetchone()
    if not comercio:
        flash('Comercio no encontrado', 'danger')
        return redirect(url_for('superadmin.index'))
        
    nuevo_estado = 1 - comercio['activo']
    db.execute('UPDATE comercios SET activo = ? WHERE id = ?', (nuevo_estado, cid))
    db.commit()
    
    estado_texto = "reactivado" if nuevo_estado == 1 else "suspendido"
    tipo_alerta = "success" if nuevo_estado == 1 else "warning"
    
    flash(f'El comercio "{comercio["nombre"]}" ha sido {estado_texto} exitosamente.', tipo_alerta)
    return redirect(url_for('superadmin.index'))


@superadmin_bp.route('/superadmin/comercios/<int:cid>/pagar', methods=['POST'])
@superadmin_required
def registrar_pago(cid):
    db = get_db()
    comercio = db.execute('SELECT nombre FROM comercios WHERE id = ?', (cid,)).fetchone()
    if not comercio:
        flash('Comercio no encontrado', 'danger')
        return redirect(url_for('superadmin.index'))
        
    from utils import get_comercio_fecha
    fecha_local = get_comercio_fecha(db, cid)
    
    db.execute('UPDATE comercios SET fecha_ultimo_pago = ?, activo = 1 WHERE id = ?', (fecha_local, cid))
    db.commit()
    
    flash(f'✅ Se ha registrado el pago mensual para "{comercio["nombre"]}" y se ha reactivado el acceso.', 'success')
    return redirect(url_for('superadmin.index'))


@superadmin_bp.route('/superadmin/comercios/<int:cid>/cambiar_password', methods=['POST'])
@superadmin_required
def cambiar_password(cid):
    db = get_db()
    comercio = db.execute('SELECT nombre FROM comercios WHERE id = ?', (cid,)).fetchone()
    if not comercio:
        flash('Comercio no encontrado', 'danger')
        return redirect(url_for('superadmin.index'))
        
    nueva_pass = request.form.get('nueva_password', '').strip()
    if not nueva_pass:
        flash('La contraseña no puede estar vacía', 'danger')
        return redirect(url_for('superadmin.index'))
        
    # Buscar al usuario administrador del comercio
    admin_user = db.execute('SELECT id FROM usuarios WHERE comercio_id = ? AND rol = "admin" LIMIT 1', (cid,)).fetchone()
    if not admin_user:
        flash('No se encontró un usuario administrador para este comercio', 'danger')
        return redirect(url_for('superadmin.index'))
        
    hash_pass = generate_password_hash(nueva_pass)
    db.execute('UPDATE usuarios SET password_hash = ? WHERE id = ?', (hash_pass, admin_user['id']))
    db.commit()
    
    flash(f'🔑 Contraseña del administrador de "{comercio["nombre"]}" cambiada exitosamente.', 'success')
    return redirect(url_for('superadmin.index'))
