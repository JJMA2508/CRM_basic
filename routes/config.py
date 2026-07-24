from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db
from utils import login_required, admin_required

config_bp = Blueprint('config', __name__)


@config_bp.route('/configuracion', methods=['GET', 'POST'])
@admin_required
def index():
    db = get_db()
    comercio_id = session['comercio_id']

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        nit_rut = request.form.get('nit_rut', '').strip()
        direccion = request.form.get('direccion', '').strip()
        telefono = request.form.get('telefono', '').strip()
        logo_emoji = request.form.get('logo_emoji', '🏪').strip()
        logo_url = request.form.get('logo_url', '').strip()
        moneda_simbolo = request.form.get('moneda_simbolo', '$').strip()
        moneda_formato = request.form.get('moneda_formato', 'es-CO').strip()
        control_mesas = 1 if request.form.get('control_mesas') else 0

        if not nombre:
            flash('El nombre del negocio es obligatorio', 'warning')
            return redirect(url_for('config.index'))

        db.execute('''
            UPDATE comercios 
            SET nombre = ?, nit_rut = ?, direccion = ?, telefono = ?, logo_emoji = ?, logo_url = ?, moneda_simbolo = ?, moneda_formato = ?, control_mesas = ?
            WHERE id = ?
        ''', (nombre, nit_rut or None, direccion or None, telefono or None, logo_emoji, logo_url or None, moneda_simbolo, moneda_formato, control_mesas, comercio_id))
        db.commit()

        # Actualizar sesión
        session['comercio_nombre'] = nombre
        session['comercio_logo_emoji'] = logo_emoji
        session['comercio_logo_url'] = logo_url or None
        session['comercio_moneda_simbolo'] = moneda_simbolo
        session['control_mesas'] = control_mesas

        flash('✅ Configuración del local actualizada correctamente', 'success')
        return redirect(url_for('config.index'))

    comercio = db.execute('SELECT * FROM comercios WHERE id = ?', (comercio_id,)).fetchone()
    # Listar mesas actuales (para pizzerías)
    mesas = db.execute('SELECT * FROM mesas WHERE comercio_id = ? ORDER BY numero', (comercio_id,)).fetchall()
    return render_template('configuracion.html', comercio=comercio, mesas=mesas)


@config_bp.route('/configuracion/mesas/agregar', methods=['POST'])
@admin_required
def agregar_mesa():
    db = get_db()
    comercio_id = session['comercio_id']
    numero = request.form.get('numero', '').strip()

    if not numero:
        flash('El número o nombre de la mesa es obligatorio', 'warning')
        return redirect(url_for('config.index'))

    # Evitar duplicados
    existente = db.execute('SELECT id FROM mesas WHERE numero = ? AND comercio_id = ?', (numero, comercio_id)).fetchone()
    if existente:
        flash(f'Ya existe la mesa "{numero}"', 'warning')
        return redirect(url_for('config.index'))

    db.execute('INSERT INTO mesas (comercio_id, numero, estado) VALUES (?, ?, "Libre")', (comercio_id, numero))
    db.commit()
    flash(f'✅ Mesa "{numero}" agregada correctamente', 'success')
    return redirect(url_for('config.index'))


@config_bp.route('/configuracion/mesas/<int:mid>/eliminar', methods=['POST'])
@admin_required
def eliminar_mesa(mid):
    db = get_db()
    comercio_id = session['comercio_id']
    db.execute('DELETE FROM mesas WHERE id = ? AND comercio_id = ?', (mid, comercio_id))
    db.commit()
    flash('🗑️ Mesa eliminada correctamente', 'success')
    return redirect(url_for('config.index'))
