from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import get_db
from utils import normalizar_tipo_comercio
from werkzeug.security import check_password_hash, generate_password_hash
import os

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session.get('rol') == 'superadmin':
            return redirect(url_for('superadmin.index'))
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        db = get_db()
        user = db.execute(
            'SELECT * FROM usuarios WHERE email = ? AND activo = 1', (email,)
        ).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            comercio = db.execute(
                'SELECT * FROM comercios WHERE id = ?', (user['comercio_id'],)
            ).fetchone()

            if not comercio:
                flash('El comercio asociado a este usuario no existe', 'danger')
                return render_template('login.html')

            if comercio['activo'] == 0:
                flash('⚠️ Su suscripcion mensual ha vencido. Por favor, realice su pago para reactivar el acceso al sistema.', 'danger')
                return render_template('login.html')

            session.permanent = True
            session['user_id'] = user['id']
            session['nombre'] = user['nombre']
            session['rol'] = user['rol']
            session['comercio_id'] = user['comercio_id']
            session['comercio_tipo'] = comercio['tipo']
            session['comercio_nombre'] = comercio['nombre']
            session['comercio_logo_emoji'] = comercio['logo_emoji']
            session['comercio_logo_url'] = comercio['logo_url']
            session['comercio_moneda_simbolo'] = comercio['moneda_simbolo'] or '$'
            session['control_mesas'] = comercio['control_mesas'] or 0

            if user['rol'] == 'superadmin':
                flash('¡Bienvenido, Administrador de la Plataforma! 👑', 'success')
                return redirect(url_for('superadmin.index'))
            flash(f'¡Bienvenido a {comercio["nombre"]}! {comercio["logo_emoji"]}', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('Correo o contraseña incorrectos', 'danger')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        if session.get('rol') == 'superadmin':
            return redirect(url_for('superadmin.index'))
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        comercio_nombre = request.form.get('comercio_nombre', '').strip()
        comercio_tipo = request.form.get('comercio_tipo', '').strip()
        usuario_nombre = request.form.get('usuario_nombre', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
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

        if not (comercio_nombre and comercio_tipo and usuario_nombre and email and password):
            flash('Todos los campos son obligatorios', 'warning')
            return render_template('registro.html')

        # Normalizar el tipo de negocio a uno de los 4 soportados por el CRM
        comercio_tipo = normalizar_tipo_comercio(comercio_tipo)

        db = get_db()
        existente = db.execute('SELECT id FROM usuarios WHERE email = ?', (email,)).fetchone()
        if existente:
            flash('El correo electrónico ya está registrado', 'warning')
            return render_template('registro.html')

        # Determinar emoji y api_key
        emojis = {'heladeria': '🍦', 'pizzeria': '🍕', 'ferreteria': '🛠️', 'general': '🏪'}
        emoji = emojis.get(comercio_tipo, '🏪')
        api_key = f"key-{comercio_tipo}-{os.urandom(4).hex()}"

        try:
            # Activar control de mesas si se detecta pizzería / restaurante
            control_mesas_val = 1 if comercio_tipo == 'pizzeria' else 0
            cur = db.execute('''
                INSERT INTO comercios (nombre, tipo, logo_emoji, api_key, telefono, zona_horaria, control_mesas)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (comercio_nombre, comercio_tipo, emoji, api_key, telefono, zona_horaria, control_mesas_val))
            comercio_id = cur.lastrowid

            # Crear usuario
            db.execute('''
                INSERT INTO usuarios (comercio_id, nombre, email, password_hash, rol)
                VALUES (?, ?, ?, ?, 'admin')
            ''', (comercio_id, usuario_nombre, email, generate_password_hash(password)))

            # Seed inicial por tipo de comercio
            if comercio_tipo == 'heladeria':
                productos = [
                    ('Helado Maracuyá', 'Helados', 'Por bola', 4000),
                    ('Helado Oreo', 'Helados', 'Por bola', 4000),
                    ('Fresas con Crema', 'Fresas', 'Grande', 10000),
                    ('Solteritas', 'Solteritas', 'Unidad', 2000),
                ]
                for nombre, cat, var, prec in productos:
                    db.execute('''
                        INSERT INTO productos (comercio_id, nombre, categoria, variante, precio)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (comercio_id, nombre, cat, var, prec))

            elif comercio_tipo == 'pizzeria':
                # Mesas
                for num in ['Mesa 1', 'Mesa 2', 'Mesa 3', 'Mesa 4']:
                    db.execute('INSERT INTO mesas (comercio_id, numero, estado) VALUES (?, ?, ?)', (comercio_id, num, 'Libre'))
                
                productos = [
                    ('Pizza Margarita', 'Pizzas', 'Personal', 12000),
                    ('Pizza Pepperoni', 'Pizzas', 'Familiar', 35000),
                    ('Coca-Cola 350ml', 'Bebidas', 'Personal', 3000),
                ]
                for nombre, cat, var, prec in productos:
                    db.execute('''
                        INSERT INTO productos (comercio_id, nombre, categoria, variante, precio)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (comercio_id, nombre, cat, var, prec))

            elif comercio_tipo == 'ferreteria':
                productos = [
                    ('Martillo Stanley', 'Herramientas', 'Unidad', 18000, 11000, 10, 2, 'Stanley', 'Unidad'),
                    ('Destornillador', 'Herramientas', 'Unidad', 7500, 4500, 15, 3, 'Generico', 'Unidad'),
                    ('Clavos de 2"', 'Fijaciones', 'Libra', 6000, 3500, 40, 5, 'Generico', 'Libra'),
                ]
                for nombre, cat, var, prec, cost, stock, stock_min, marca, unid in productos:
                    db.execute('''
                        INSERT INTO productos (comercio_id, nombre, categoria, variante, precio, costo, stock, stock_minimo, marca, unidad_medida)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (comercio_id, nombre, cat, var, prec, cost, stock, stock_min, marca, unid))

            elif comercio_tipo == 'general':
                productos = [
                    ('Arroz Diana 1kg', 'Granos', 'Bolsa', 4200, 3100, 50, 10, 'Diana', 'Bolsa', '7702001001'),
                    ('Leche Entera 1L', 'Lácteos', 'Bolsa', 3800, 2900, 30, 5, 'Colanta', 'Bolsa', '7702001003'),
                ]
                for nombre, cat, var, prec, cost, stock, stock_min, marca, unid, sku in productos:
                    db.execute('''
                        INSERT INTO productos (comercio_id, nombre, categoria, variante, precio, costo, stock, stock_minimo, marca, unidad_medida, sku)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (comercio_id, nombre, cat, var, prec, cost, stock, stock_min, marca, unid, sku))

            db.commit()
            flash('¡Comercio registrado con éxito! Inicia sesión ahora.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.rollback()
            flash(f'Error al registrar el comercio: {str(e)}', 'danger')
            return render_template('registro.html')

    return render_template('registro.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente', 'info')
    return redirect(url_for('auth.login'))
