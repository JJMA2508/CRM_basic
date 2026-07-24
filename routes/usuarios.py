from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db
from werkzeug.security import generate_password_hash
from utils import login_required
from functools import wraps

usuarios_bp = Blueprint('usuarios', __name__)


def admin_required(f):
    """Decorator: requiere rol de admin para el comercio."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if session.get('rol') != 'admin':
            flash('Acceso restringido a Administradores del Comercio', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated


@usuarios_bp.route('/colaboradores')
@admin_required
def index():
    db = get_db()
    comercio_id = session['comercio_id']
    
    # Listar colaboradores (excluyendo el usuario logueado para no operarse a sí mismo en la tabla fácilmente)
    colaboradores = db.execute('''
        SELECT * FROM usuarios 
        WHERE comercio_id = ? AND id != ?
        ORDER BY rol DESC, nombre ASC
    ''', (comercio_id, session['user_id'])).fetchall()
    
    # Obtener conteo de usuarios del comercio para validar el límite
    conteo_usuarios = db.execute('SELECT COUNT(*) FROM usuarios WHERE comercio_id = ?', (comercio_id,)).fetchone()[0]
    limite_alcanzado = (conteo_usuarios >= 5)
    
    return render_template(
        'colaboradores.html', 
        colaboradores=colaboradores, 
        conteo_usuarios=conteo_usuarios, 
        limite_alcanzado=limite_alcanzado
    )


@usuarios_bp.route('/colaboradores/nuevo', methods=['POST'])
@admin_required
def nuevo():
    db = get_db()
    comercio_id = session['comercio_id']
    
    # Verificar límite
    conteo_usuarios = db.execute('SELECT COUNT(*) FROM usuarios WHERE comercio_id = ?', (comercio_id,)).fetchone()[0]
    if conteo_usuarios >= 5:
        flash('⚠️ Límite de 5 colaboradores por comercio alcanzado. No puedes registrar más usuarios.', 'danger')
        return redirect(url_for('usuarios.index'))
        
    nombre = request.form.get('nombre', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    rol = request.form.get('rol', 'vendedor')
    
    if not nombre or not email or not password:
        flash('Todos los campos marcados con asterisco (*) son obligatorios.', 'danger')
        return redirect(url_for('usuarios.index'))
        
    # Verificar email único global
    existe = db.execute('SELECT id FROM usuarios WHERE email = ?', (email,)).fetchone()
    if existe:
        flash('⚠️ El correo electrónico ya se encuentra registrado por otro usuario.', 'danger')
        return redirect(url_for('usuarios.index'))
        
    try:
        db.execute('''
            INSERT INTO usuarios (comercio_id, nombre, email, password_hash, rol, activo)
            VALUES (?, ?, ?, ?, ?, 1)
        ''', (comercio_id, nombre, email, generate_password_hash(password), rol))
        db.commit()
        flash(f'👤 Colaborador "{nombre}" registrado con éxito.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error al registrar colaborador: {str(e)}', 'danger')
        
    return redirect(url_for('usuarios.index'))


@usuarios_bp.route('/colaboradores/<int:uid>/toggle_activo', methods=['POST'])
@admin_required
def toggle_activo(uid):
    db = get_db()
    comercio_id = session['comercio_id']
    
    # Buscar el usuario
    user = db.execute('SELECT * FROM usuarios WHERE id = ? AND comercio_id = ?', (uid, comercio_id)).fetchone()
    if not user:
        flash('Usuario no encontrado o no pertenece a tu comercio', 'danger')
        return redirect(url_for('usuarios.index'))
        
    nuevo_estado = 1 - user['activo']
    db.execute('UPDATE usuarios SET activo = ? WHERE id = ?', (nuevo_estado, uid))
    db.commit()
    
    estado_texto = "activado" if nuevo_estado == 1 else "suspendido"
    flash(f'El colaborador "{user["nombre"]}" ha sido {estado_texto}.', 'success')
    return redirect(url_for('usuarios.index'))


@usuarios_bp.route('/colaboradores/<int:uid>/cambiar_password', methods=['POST'])
@admin_required
def cambiar_password(uid):
    db = get_db()
    comercio_id = session['comercio_id']
    
    user = db.execute('SELECT * FROM usuarios WHERE id = ? AND comercio_id = ?', (uid, comercio_id)).fetchone()
    if not user:
        flash('Usuario no encontrado o no pertenece a tu comercio', 'danger')
        return redirect(url_for('usuarios.index'))
        
    nueva_pass = request.form.get('nueva_password', '').strip()
    if not nueva_pass or len(nueva_pass) < 6:
        flash('La contraseña debe tener al menos 6 caracteres', 'danger')
        return redirect(url_for('usuarios.index'))
        
    db.execute('UPDATE usuarios SET password_hash = ? WHERE id = ?', (generate_password_hash(nueva_pass), uid))
    db.commit()
    
    flash(f'🔑 Contraseña de "{user["nombre"]}" restablecida con éxito.', 'success')
    return redirect(url_for('usuarios.index'))


@usuarios_bp.route('/colaboradores/<int:uid>/eliminar', methods=['POST'])
@admin_required
def eliminar(uid):
    db = get_db()
    comercio_id = session['comercio_id']
    
    user = db.execute('SELECT * FROM usuarios WHERE id = ? AND comercio_id = ?', (uid, comercio_id)).fetchone()
    if not user:
        flash('Usuario no encontrado o no pertenece a tu comercio', 'danger')
        return redirect(url_for('usuarios.index'))
        
    db.execute('DELETE FROM usuarios WHERE id = ?', (uid,))
    db.commit()
    
    flash(f'🗑️ Colaborador "{user["nombre"]}" eliminado de forma definitiva.', 'success')
    return redirect(url_for('usuarios.index'))
