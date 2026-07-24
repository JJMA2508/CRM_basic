from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from database import get_db
from utils import login_required, admin_required
from datetime import datetime

compras_bp = Blueprint('compras', __name__)


# ── Proveedores ──────────────────────────────────────────────────────────────
@compras_bp.route('/proveedores')
@login_required
def proveedores():
    db = get_db()
    comercio_id = session['comercio_id']
    provs = db.execute(
        'SELECT * FROM proveedores WHERE comercio_id = ? ORDER BY nombre',
        (comercio_id,)
    ).fetchall()
    return render_template('proveedores.html', proveedores=provs)


@compras_bp.route('/proveedores/nuevo', methods=['POST'])
@login_required
def proveedor_nuevo():
    db = get_db()
    comercio_id = session['comercio_id']
    nombre = request.form.get('nombre', '').strip()
    contacto = request.form.get('contacto', '').strip()
    nit_rut = request.form.get('nit_rut', '').strip()

    if not nombre:
        flash('El nombre del proveedor es obligatorio', 'warning')
        return redirect(url_for('compras.proveedores'))

    db.execute('''
        INSERT INTO proveedores (comercio_id, nombre, contacto, nit_rut)
        VALUES (?, ?, ?, ?)
    ''', (comercio_id, nombre, contacto or None, nit_rut or None))
    db.commit()

    flash(f'✅ Proveedor "{nombre}" registrado', 'success')
    return redirect(url_for('compras.proveedores'))


@compras_bp.route('/proveedores/<int:pid>/editar', methods=['POST'])
@login_required
def proveedor_editar(pid):
    db = get_db()
    comercio_id = session['comercio_id']
    nombre = request.form.get('nombre', '').strip()
    contacto = request.form.get('contacto', '').strip()
    nit_rut = request.form.get('nit_rut', '').strip()

    if not nombre:
        flash('El nombre es obligatorio', 'warning')
        return redirect(url_for('compras.proveedores'))

    db.execute('''
        UPDATE proveedores 
        SET nombre = ?, contacto = ?, nit_rut = ? 
        WHERE id = ? AND comercio_id = ?
    ''', (nombre, contacto or None, nit_rut or None, pid, comercio_id))
    db.commit()

    flash('✅ Proveedor actualizado correctamente', 'success')
    return redirect(url_for('compras.proveedores'))


@compras_bp.route('/proveedores/<int:pid>/eliminar', methods=['POST'])
@admin_required
def proveedor_eliminar(pid):
    db = get_db()
    comercio_id = session['comercio_id']
    db.execute('DELETE FROM proveedores WHERE id = ? AND comercio_id = ?', (pid, comercio_id))
    db.commit()
    flash('🗑️ Proveedor eliminado', 'success')
    return redirect(url_for('compras.proveedores'))


# ── Órdenes de Compra / Entrada de Mercancía ─────────────────────────────────
@compras_bp.route('/compras')
@login_required
def index():
    db = get_db()
    comercio_id = session['comercio_id']
    rows = db.execute('''
        SELECT c.*, p.nombre as proveedor_nombre, u.nombre as usuario_nombre,
               (SELECT COUNT(*) FROM detalle_compras dc WHERE dc.compra_id = c.id) as items_count
        FROM compras c
        LEFT JOIN proveedores p ON c.proveedor_id = p.id
        JOIN usuarios u ON c.usuario_id = u.id
        WHERE c.comercio_id = ?
        ORDER BY c.fecha DESC
    ''', (comercio_id,)).fetchall()
    return render_template('compras.html', compras=rows)


@compras_bp.route('/compras/nueva', methods=['GET', 'POST'])
@login_required
def nueva_compra():
    db = get_db()
    comercio_id = session['comercio_id']

    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        proveedor_id = data.get('proveedor_id')
        factura_numero = data.get('factura_numero', '').strip()
        items = data.get('items', [])
        notas = data.get('notas', '').strip()

        if not items:
            return jsonify({'error': 'Debe agregar al menos un producto a la compra'}), 400

        total_compra = 0
        productos_validados = []
        for it in items:
            prod_id = it.get('producto_id')
            qty = float(it.get('cantidad', 0))
            cost_unit = float(it.get('costo_unitario', 0))

            if qty <= 0 or cost_unit < 0:
                return jsonify({'error': 'Cantidad o costo inválido'}), 400

            prod = db.execute(
                'SELECT * FROM productos WHERE id = ? AND comercio_id = ?',
                (prod_id, comercio_id)
            ).fetchone()
            if not prod:
                return jsonify({'error': f'Producto {prod_id} no encontrado'}), 404

            subtotal = qty * cost_unit
            total_compra += subtotal
            productos_validados.append({
                'id': prod_id,
                'qty': qty,
                'costo_unit': cost_unit,
                'subtotal': subtotal,
                'nombre': prod['nombre']
            })

        # Registrar compra
        from utils import get_comercio_fecha
        fecha_local = get_comercio_fecha(db, comercio_id)

        cur = db.execute('''
            INSERT INTO compras (comercio_id, proveedor_id, factura_numero, fecha, total, usuario_id, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (comercio_id, proveedor_id or None, factura_numero or None, fecha_local, total_compra, session['user_id'], notas or None))
        compra_id = cur.lastrowid

        for p in productos_validados:
            # Registrar detalles
            db.execute('''
                INSERT INTO detalle_compras (compra_id, producto_id, cantidad, costo_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?)
            ''', (compra_id, p['id'], p['qty'], p['costo_unit'], p['subtotal']))

            # Actualizar stock y costo de adquisición del producto
            db.execute('''
                UPDATE productos 
                SET stock = COALESCE(stock, 0) + ?, costo = ?
                WHERE id = ? AND comercio_id = ?
            ''', (p['qty'], p['costo_unit'], p['id'], comercio_id))

            # Movimiento de inventario
            db.execute('''
                INSERT INTO movimientos_inventario (comercio_id, producto_id, tipo, cantidad, motivo, usuario_id)
                VALUES (?, ?, 'entrada', ?, ?, ?)
            ''', (comercio_id, p['id'], p['qty'], f'Orden de Compra #{compra_id} Fact: {factura_numero or "S/N"}', session['user_id']))

        db.commit()
        return jsonify({'ok': True, 'compra_id': compra_id})

    # GET: cargar vista
    proveedores_list = db.execute('SELECT * FROM proveedores WHERE comercio_id = ? ORDER BY nombre', (comercio_id,)).fetchall()
    # Productos que admiten inventario
    productos_list = db.execute(
        'SELECT * FROM productos WHERE comercio_id = ? AND activo = 1 ORDER BY categoria, nombre',
        (comercio_id,)
    ).fetchall()

    return render_template('nueva_compra.html', proveedores=proveedores_list, productos=productos_list)
