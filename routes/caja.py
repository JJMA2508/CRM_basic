from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from database import get_db
from utils import login_required, admin_required, get_comercio_fecha
from datetime import datetime

caja_bp = Blueprint('caja', __name__)


# ── Caja Diaria (Arqueo y Cierre) ────────────────────────────────────────────
@caja_bp.route('/caja')
@login_required
def index():
    db = get_db()
    comercio_id = session['comercio_id']

    # Obtener caja abierta activa
    caja_activa = db.execute('''
        SELECT * FROM caja_diaria 
        WHERE estado = 'Abierta' AND comercio_id = ? 
        ORDER BY id DESC LIMIT 1
    ''', (comercio_id,)).fetchone()

    # Si hay caja activa, calcular ingresos y gastos en tiempo real
    caja_datos = None
    if caja_activa:
        # 1. Ventas por método de pago desde la fecha_apertura
        ventas_stats = db.execute('''
            SELECT 
                COALESCE(SUM(CASE WHEN tipo_pago = 'Efectivo' THEN total ELSE 0 END), 0) as efectivo,
                COALESCE(SUM(CASE WHEN tipo_pago = 'Tarjeta' THEN total ELSE 0 END), 0) as tarjeta,
                COALESCE(SUM(CASE WHEN tipo_pago = 'Transferencia' THEN total ELSE 0 END), 0) as transferencia,
                COALESCE(SUM(CASE WHEN tipo_pago = 'Crédito' THEN total ELSE 0 END), 0) as credito
            FROM ventas
            WHERE comercio_id = ? AND anulada = 0 AND fecha >= ?
        ''', (comercio_id, caja_activa['fecha_apertura'])).fetchone()

        # 2. Abonos de créditos desde la fecha_apertura (suman a efectivo)
        abonos = db.execute('''
            SELECT COALESCE(SUM(monto), 0) as total
            FROM pagos_credito
            WHERE comercio_id = ? AND fecha >= ?
        ''', (comercio_id, caja_activa['fecha_apertura'])).fetchone()

        # 3. Gastos desde la fecha_apertura
        gastos = db.execute('''
            SELECT COALESCE(SUM(monto), 0) as total
            FROM gastos
            WHERE comercio_id = ? AND fecha >= ?
        ''', (comercio_id, caja_activa['fecha_apertura'])).fetchone()

        caja_datos = {
            'caja': caja_activa,
            'ingresos_efectivo': ventas_stats['efectivo'],
            'ingresos_tarjeta': ventas_stats['tarjeta'],
            'ingresos_transferencia': ventas_stats['transferencia'],
            'ingresos_credito': ventas_stats['credito'],
            'abonos_credito': abonos['total'],
            'gastos': gastos['total'],
            'efectivo_esperado': caja_activa['monto_inicial'] + ventas_stats['efectivo'] + abonos['total'] - gastos['total']
        }

    # Cajas anteriores
    cajas_cerradas = db.execute('''
        SELECT c.*, ua.nombre as usuario_apertura, uc.nombre as usuario_cierre
        FROM caja_diaria c
        JOIN usuarios ua ON c.usuario_apertura_id = ua.id
        LEFT JOIN usuarios uc ON c.usuario_cierre_id = uc.id
        WHERE c.comercio_id = ? AND c.estado = 'Cerrada'
        ORDER BY c.fecha_cierre DESC LIMIT 30
    ''', (comercio_id,)).fetchall()

    return render_template('caja.html', caja_datos=caja_datos, cajas_cerradas=cajas_cerradas)


@caja_bp.route('/caja/abrir', methods=['POST'])
@login_required
def abrir():
    db = get_db()
    comercio_id = session['comercio_id']

    # Validar si ya hay una abierta
    existente = db.execute('''
        SELECT id FROM caja_diaria WHERE estado = 'Abierta' AND comercio_id = ?
    ''', (comercio_id,)).fetchone()
    if existente:
        flash('⚠️ Ya tienes un turno de caja abierto.', 'warning')
        return redirect(url_for('caja.index'))

    try:
        monto_inicial = float(request.form.get('monto_inicial', 0))
    except ValueError:
        flash('Monto inicial inválido.', 'danger')
        return redirect(url_for('caja.index'))

    # Registrar apertura
    fecha_local = get_comercio_fecha(db, comercio_id)
 
    db.execute('''
        INSERT INTO caja_diaria (comercio_id, fecha_apertura, monto_inicial, estado, usuario_apertura_id)
        VALUES (?, ?, ?, 'Abierta', ?)
    ''', (comercio_id, fecha_local, monto_inicial, session['user_id']))
    db.commit()

    flash('🚀 Turno de caja abierto correctamente.', 'success')
    return redirect(url_for('caja.index'))


@caja_bp.route('/caja/cerrar', methods=['POST'])
@login_required
def cerrar():
    db = get_db()
    comercio_id = session['comercio_id']

    caja_activa = db.execute('''
        SELECT * FROM caja_diaria 
        WHERE estado = 'Abierta' AND comercio_id = ? 
        ORDER BY id DESC LIMIT 1
    ''', (comercio_id,)).fetchone()

    if not caja_activa:
        flash('No hay ninguna caja abierta para cerrar.', 'warning')
        return redirect(url_for('caja.index'))

    try:
        monto_final = float(request.form.get('monto_final', 0))
    except ValueError:
        flash('Monto final inválido.', 'danger')
        return redirect(url_for('caja.index'))

    notas = request.form.get('notas', '').strip()

    # Recalcular valores para guardar snapshot en la DB
    ventas_stats = db.execute('''
        SELECT 
            COALESCE(SUM(CASE WHEN tipo_pago = 'Efectivo' THEN total ELSE 0 END), 0) as efectivo,
            COALESCE(SUM(CASE WHEN tipo_pago = 'Tarjeta' THEN total ELSE 0 END), 0) as tarjeta,
            COALESCE(SUM(CASE WHEN tipo_pago = 'Transferencia' THEN total ELSE 0 END), 0) as transferencia,
            COALESCE(SUM(CASE WHEN tipo_pago = 'Crédito' THEN total ELSE 0 END), 0) as credito
        FROM ventas
        WHERE comercio_id = ? AND anulada = 0 AND fecha >= ?
    ''', (comercio_id, caja_activa['fecha_apertura'])).fetchone()

    abonos = db.execute('''
        SELECT COALESCE(SUM(monto), 0) as total
        FROM pagos_credito
        WHERE comercio_id = ? AND fecha >= ?
    ''', (comercio_id, caja_activa['fecha_apertura'])).fetchone()

    gastos = db.execute('''
        SELECT COALESCE(SUM(monto), 0) as total
        FROM gastos
        WHERE comercio_id = ? AND fecha >= ?
    ''', (comercio_id, caja_activa['fecha_apertura'])).fetchone()

    efectivo_esperado = caja_activa['monto_inicial'] + ventas_stats['efectivo'] + abonos['total'] - gastos['total']
    
    # Monto total en caja incluyendo Tarjeta/Transferencia (para auditoría)
    fecha_local = get_comercio_fecha(db, comercio_id)
 
    db.execute('''
        UPDATE caja_diaria
        SET estado = 'Cerrada',
            fecha_cierre = ?,
            monto_final = ?,
            ingresos_efectivo = ?,
            ingresos_tarjeta = ?,
            ingresos_transferencia = ?,
            ingresos_credito = ?,
            gastos_totales = ?,
            usuario_cierre_id = ?,
            notas = ?
        WHERE id = ?
    ''', (fecha_local, monto_final, 
          ventas_stats['efectivo'] + abonos['total'], 
          ventas_stats['tarjeta'], 
          ventas_stats['transferencia'], 
          ventas_stats['credito'], 
          gastos['total'], 
          session['user_id'], 
          notas or None, 
          caja_activa['id']))
    db.commit()

    flash(f'🔒 Caja cerrada. Efectivo esperado: ${efectivo_esperado:,.0f} | Reportado: ${monto_final:,.0f}'.replace(',', '.'), 'success')
    return redirect(url_for('caja.index'))


# ── Gastos Operativos ────────────────────────────────────────────────────────
@caja_bp.route('/gastos', methods=['GET', 'POST'])
@login_required
def gastos():
    db = get_db()
    comercio_id = session['comercio_id']

    if request.method == 'POST':
        categoria = request.form.get('categoria', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        try:
            monto = float(request.form.get('monto', 0))
        except ValueError:
            flash('Monto del gasto inválido', 'danger')
            return redirect(url_for('caja.gastos'))

        if not categoria or monto <= 0:
            flash('Categoría y monto mayor a 0 requeridos.', 'warning')
            return redirect(url_for('caja.gastos'))

        fecha_local = get_comercio_fecha(db, comercio_id)

        db.execute('''
            INSERT INTO gastos (comercio_id, categoria, descripcion, monto, fecha, usuario_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (comercio_id, categoria, descripcion or None, monto, fecha_local, session['user_id']))
        db.commit()

        flash('💸 Egresos / Gasto registrado correctamente', 'success')
        return redirect(url_for('caja.gastos'))

    # Cargar gastos del comercio
    gastos_list = db.execute('''
        SELECT g.*, u.nombre as usuario_nombre
        FROM gastos g
        JOIN usuarios u ON g.usuario_id = u.id
        WHERE g.comercio_id = ?
        ORDER BY g.fecha DESC LIMIT 100
    ''', (comercio_id,)).fetchall()

    # Verificar si hay una caja abierta
    caja_activa = db.execute('''
        SELECT id FROM caja_diaria 
        WHERE estado = 'Abierta' AND comercio_id = ? 
        ORDER BY id DESC LIMIT 1
    ''', (comercio_id,)).fetchone()

    return render_template('gastos.html', gastos=gastos_list, caja_abierta=(caja_activa is not None))
