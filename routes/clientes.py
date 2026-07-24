from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db
from utils import login_required, admin_required

clientes_bp = Blueprint('clientes', __name__)


@clientes_bp.route('/clientes')
@login_required
def index():
    db = get_db()
    comercio_id = session['comercio_id']
    clientes = db.execute(
        'SELECT * FROM clientes WHERE comercio_id = ? ORDER BY saldo_credito DESC, nombre',
        (comercio_id,)
    ).fetchall()
    return render_template('clientes.html', clientes=clientes)


@clientes_bp.route('/clientes/<int:cid>')
@login_required
def detalle(cid):
    db = get_db()
    comercio_id = session['comercio_id']
    
    cliente = db.execute('SELECT * FROM clientes WHERE id = ? AND comercio_id = ?', (cid, comercio_id)).fetchone()
    if not cliente:
        flash('Cliente no encontrado', 'danger')
        return redirect(url_for('clientes.index'))

    ventas = db.execute('''
        SELECT v.*, u.nombre as vendedor
        FROM ventas v
        JOIN usuarios u ON v.usuario_id = u.id
        WHERE v.cliente_id = ? AND v.comercio_id = ? AND v.anulada = 0
        ORDER BY v.fecha DESC
    ''', (cid, comercio_id)).fetchall()

    pagos = db.execute('''
        SELECT p.*, u.nombre as registrado_por
        FROM pagos_credito p
        JOIN usuarios u ON p.usuario_id = u.id
        WHERE p.cliente_id = ? AND p.comercio_id = ?
        ORDER BY p.fecha DESC
    ''', (cid, comercio_id)).fetchall()

    productos_frecuentes = db.execute('''
        SELECT p.nombre, p.categoria, SUM(dv.cantidad) as total_cantidad
        FROM detalle_ventas dv
        JOIN productos p ON dv.producto_id = p.id
        JOIN ventas v ON dv.venta_id = v.id
        WHERE v.cliente_id = ? AND v.comercio_id = ? AND v.anulada = 0
        GROUP BY p.id
        ORDER BY total_cantidad DESC
        LIMIT 5
    ''', (cid, comercio_id)).fetchall()

    return render_template('cliente_detalle.html',
        cliente=cliente, ventas=ventas, pagos=pagos, productos_frecuentes=productos_frecuentes
    )


@clientes_bp.route('/clientes/nuevo', methods=['POST'])
@login_required
def nuevo():
    db = get_db()
    comercio_id = session['comercio_id']
    
    nombre = request.form.get('nombre', '').strip()
    telefono = request.form.get('telefono', '').strip()
    email = request.form.get('email', '').strip()
    nit_rut = request.form.get('nit_rut', '').strip()
    direccion = request.form.get('direccion', '').strip()

    if not nombre:
        flash('El nombre es obligatorio', 'warning')
        return redirect(url_for('clientes.index'))

    existente = db.execute('SELECT id FROM clientes WHERE nombre = ? AND comercio_id = ?', (nombre, comercio_id)).fetchone()
    if existente:
        flash(f'Ya existe un cliente con el nombre "{nombre}"', 'warning')
        return redirect(url_for('clientes.index'))

    db.execute('''
        INSERT INTO clientes (comercio_id, nombre, telefono, email, nit_rut, direccion)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (comercio_id, nombre, telefono or None, email or None, nit_rut or None, direccion or None))
    
    db.commit()
    flash(f'✅ Cliente "{nombre}" registrado', 'success')
    return redirect(url_for('clientes.index'))


@clientes_bp.route('/clientes/<int:cid>/pagar', methods=['POST'])
@login_required
def pagar_credito(cid):
    db = get_db()
    comercio_id = session['comercio_id']
    
    cliente = db.execute('SELECT * FROM clientes WHERE id = ? AND comercio_id = ?', (cid, comercio_id)).fetchone()
    if not cliente:
        flash('Cliente no encontrado', 'danger')
        return redirect(url_for('clientes.index'))

    try:
        monto = float(request.form.get('monto', 0))
    except ValueError:
        flash('Monto inválido', 'danger')
        return redirect(url_for('clientes.detalle', cid=cid))

    if monto <= 0:
        flash('El monto debe ser mayor a 0', 'warning')
        return redirect(url_for('clientes.detalle', cid=cid))

    if monto > cliente['saldo_credito']:
        monto = cliente['saldo_credito']

    notas = request.form.get('notes', '').strip()

    # Obtener fecha y hora actual según zona horaria del comercio
    from utils import get_comercio_fecha
    fecha_local = get_comercio_fecha(db, comercio_id)

    db.execute('''
        INSERT INTO pagos_credito (comercio_id, cliente_id, monto, fecha, usuario_id, notas) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (comercio_id, cid, monto, fecha_local, session['user_id'], notas or None))
    
    db.execute('''
        UPDATE clientes 
        SET saldo_credito = MAX(0, saldo_credito - ?) 
        WHERE id = ? AND comercio_id = ?
    ''', (monto, cid, comercio_id))
    
    db.commit()
    flash(f'✅ Abono de ${monto:,.0f} registrado'.replace(',', '.'), 'success')
    return redirect(url_for('clientes.detalle', cid=cid))


@clientes_bp.route('/clientes/pago/<int:pago_id>/recibo')
@login_required
def recibo_pago(pago_id):
    db = get_db()
    comercio_id = session['comercio_id']
    pago = db.execute('''
        SELECT p.*, c.nombre as cliente_nombre, c.saldo_credito as cliente_saldo, u.nombre as registrado_por
        FROM pagos_credito p
        JOIN clientes c ON p.cliente_id = c.id
        JOIN usuarios u ON p.usuario_id = u.id
        WHERE p.id = ? AND p.comercio_id = ?
    ''', (pago_id, comercio_id)).fetchone()
    
    if not pago:
        flash('Comprobante de abono no encontrado', 'danger')
        return redirect(url_for('clientes.index'))
        
    return render_template('recibo_pago.html', pago=pago)
