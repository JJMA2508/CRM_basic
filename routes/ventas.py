import json
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from database import get_db
from utils import login_required, admin_required, get_comercio_fecha
from datetime import datetime, timezone, timedelta

ventas_bp = Blueprint('ventas', __name__)


@ventas_bp.route('/ventas/nueva')
@login_required
def nueva():
    db = get_db()
    comercio_id = session['comercio_id']
    comercio_tipo = session['comercio_tipo']

    # Cargar productos del comercio
    productos = db.execute(
        'SELECT * FROM productos WHERE comercio_id = ? AND activo = 1 ORDER BY categoria, nombre',
        (comercio_id,)
    ).fetchall()

    # Agrupar por categoría
    categorias = {}
    for p in productos:
        cat = p['categoria']
        if cat not in categorias:
            categorias[cat] = []
        categorias[cat].append(dict(p))

    # Cargar clientes del comercio
    clientes_existentes = db.execute(
        'SELECT * FROM clientes WHERE comercio_id = ? ORDER BY nombre',
        (comercio_id,)
    ).fetchall()

    # Cargar mesas si está habilitado
    mesas_existentes = []
    control_mesas = session.get('control_mesas') == 1
    if control_mesas:
        mesas_existentes = db.execute(
            'SELECT * FROM mesas WHERE comercio_id = ? ORDER BY numero',
            (comercio_id,)
        ).fetchall()

    # Cargar carrito activo de mesa si viene por query parameter
    mesa_id = request.args.get('mesa_id')
    mesa_carrito = None
    mesa_numero = None
    if mesa_id and control_mesas:
        m = db.execute('SELECT * FROM mesas WHERE id = ? AND comercio_id = ?', (mesa_id, comercio_id)).fetchone()
        if m:
            mesa_carrito = m['carrito_json']
            mesa_numero = m['numero']

    return render_template(
        'nueva_venta.html',
        categorias=categorias,
        clientes_existentes=clientes_existentes,
        mesas_existentes=mesas_existentes,
        mesa_id=mesa_id,
        mesa_carrito=mesa_carrito,
        mesa_numero=mesa_numero
    )


@ventas_bp.route('/ventas/registrar', methods=['POST'])
@login_required
def registrar():
    db = get_db()
    comercio_id = session['comercio_id']
    comercio_tipo = session['comercio_tipo']
    
    tipo_pago = request.form.get('tipo_pago')
    notas = request.form.get('notas', '').strip()
    items_json = request.form.get('items_json', '[]')
    nombre_cliente = request.form.get('nombre_cliente', '').strip()
    
    # Parámetros especiales de pizzería
    mesa_id = request.form.get('mesa_id')
    tipo_pedido = request.form.get('tipo_pedido', 'Para Llevar')
    
    # Si viene comanda guardar de pizzería
    guardar_comanda = request.form.get('guardar_comanda') == 'true'

    try:
        items = json.loads(items_json)
    except Exception:
        flash('Error al procesar los productos', 'danger')
        return redirect(url_for('ventas.nueva'))

    if not items:
        flash('Agrega al menos un producto a la venta', 'warning')
        return redirect(url_for('ventas.nueva'))

    # Si es sólo guardar comanda en mesa (pizzería)
    if guardar_comanda and comercio_tipo == 'pizzeria' and mesa_id:
        db.execute('''
            UPDATE mesas 
            SET estado = 'Ocupada', carrito_json = ? 
            WHERE id = ? AND comercio_id = ?
        ''', (items_json, mesa_id, comercio_id))
        db.commit()
        flash('Comanda de la mesa guardada temporalmente', 'success')
        return redirect(url_for('ventas.mesas'))

    if tipo_pago not in ('Efectivo', 'Tarjeta', 'Transferencia', 'Crédito'):
        flash('Tipo de pago inválido', 'danger')
        return redirect(url_for('ventas.nueva'))

    if tipo_pago == 'Crédito' and not nombre_cliente:
        flash('Para ventas a crédito debes ingresar el nombre del cliente', 'warning')
        return redirect(url_for('ventas.nueva'))

    # Calcular total y validar stock
    total = 0
    items_validados = []
    for item in items:
        prod = db.execute(
            'SELECT * FROM productos WHERE id = ? AND activo = 1 AND comercio_id = ?',
            (item['id'], comercio_id)
        ).fetchone()
        if not prod:
            continue
        qty = max(0.01, float(item.get('qty', 1)))
        
        # Validar stock físico en ferreterías o general si tienen stock definido
        if prod['stock'] is not None:
            if prod['stock'] < qty:
                # Alerta pero permitimos o bloqueamos? Vamos a descontar pero advertir. O bloquear si queda negativo.
                # Bloqueemos para ser rigurosos con ferretería
                flash(f'Stock insuficiente para "{prod["nombre"]}". Stock actual: {prod["stock"]}', 'danger')
                return redirect(url_for('ventas.nueva'))

        subtotal = prod['precio'] * qty
        total += subtotal
        items_validados.append({'producto': prod, 'qty': qty, 'subtotal': subtotal, 'notas_item': item.get('notas_item', '')})

    if not items_validados:
        flash('No se encontraron productos válidos', 'danger')
        return redirect(url_for('ventas.nueva'))

    # Manejar cliente (para crédito o registro)
    cliente_id = None
    if nombre_cliente:
        cliente = db.execute(
            'SELECT * FROM clientes WHERE nombre = ? AND comercio_id = ?',
            (nombre_cliente, comercio_id)
        ).fetchone()
        if not cliente:
            db.execute(
                'INSERT INTO clientes (comercio_id, nombre) VALUES (?, ?)',
                (comercio_id, nombre_cliente)
            )
            db.commit()
            cliente = db.execute(
                'SELECT * FROM clientes WHERE nombre = ? AND comercio_id = ?',
                (nombre_cliente, comercio_id)
            ).fetchone()
        cliente_id = cliente['id']

    # Obtener fecha y hora actual según zona horaria del comercio
    fecha_local = get_comercio_fecha(db, comercio_id)
 
    # Insertar venta
    cursor = db.execute('''
        INSERT INTO ventas (comercio_id, fecha, total, tipo_pago, cliente_id, usuario_id, notas, tipo_pedido, mesa_id, estado_pedido)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Entregado')
    ''', (comercio_id, fecha_local, total, tipo_pago, cliente_id, session['user_id'], notas, tipo_pedido, mesa_id or None))
    venta_id = cursor.lastrowid

    # Insertar detalles y descontar inventario
    for item in items_validados:
        db.execute('''
            INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, precio_unitario, subtotal, notas_item)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (venta_id, item['producto']['id'], item['qty'], item['producto']['precio'], item['subtotal'], item['notas_item']))

        # Descontar stock si está habilitado
        if item['producto']['stock'] is not None:
            db.execute('''
                UPDATE productos 
                SET stock = MAX(0, stock - ?) 
                WHERE id = ? AND comercio_id = ?
            ''', (item['qty'], item['producto']['id'], comercio_id))

            # Registrar movimiento de inventario
            db.execute('''
                INSERT INTO movimientos_inventario (comercio_id, producto_id, tipo, cantidad, motivo, usuario_id)
                VALUES (?, ?, 'salida', ?, 'Venta', ?)
            ''', (comercio_id, item['producto']['id'], item['qty'], session['user_id']))

    # Si es crédito, actualizar saldo del cliente
    if tipo_pago == 'Crédito' and cliente_id:
        db.execute(
            'UPDATE clientes SET saldo_credito = saldo_credito + ? WHERE id = ? AND comercio_id = ?',
            (total, cliente_id, comercio_id)
        )

    # Si se vendió desde una mesa, liberarla
    if session.get('control_mesas') == 1 and mesa_id:
        db.execute('''
            UPDATE mesas 
            SET estado = 'Libre', carrito_json = NULL 
            WHERE id = ? AND comercio_id = ?
        ''', (mesa_id, comercio_id))

    db.commit()
    flash(f'✅ Venta #{venta_id} registrada por ${total:,.0f}'.replace(',', '.'), 'success')
    return redirect(url_for('ventas.recibo', venta_id=venta_id))


@ventas_bp.route('/ventas/historial')
@login_required
def historial():
    db = get_db()
    comercio_id = session['comercio_id']
    
    fecha_desde = request.args.get('desde', '')
    fecha_hasta = request.args.get('hasta', '')
    tipo_pago = request.args.get('tipo_pago', '')
    buscar = request.args.get('buscar', '').strip()

    query = '''
        SELECT v.*, u.nombre as vendedor,
               COALESCE(c.nombre, '') as cliente_nombre,
               COALESCE(m.numero, '') as mesa_numero
        FROM ventas v
        JOIN usuarios u ON v.usuario_id = u.id
        LEFT JOIN clientes c ON v.cliente_id = c.id
        LEFT JOIN mesas m ON v.mesa_id = m.id
        WHERE v.anulada = 0 AND v.comercio_id = ?
    '''
    params = [comercio_id]

    if fecha_desde:
        query += ' AND DATE(v.fecha) >= ?'
        params.append(fecha_desde)
    if fecha_hasta:
        query += ' AND DATE(v.fecha) <= ?'
        params.append(fecha_hasta)
    if tipo_pago:
        query += ' AND v.tipo_pago = ?'
        params.append(tipo_pago)
    if buscar:
        query += ' AND (c.nombre LIKE ? OR u.nombre LIKE ?)'
        params.extend([f'%{buscar}%', f'%{buscar}%'])

    query += ' ORDER BY v.fecha DESC LIMIT 200'
    ventas = db.execute(query, params).fetchall()

    total_general = sum(v['total'] for v in ventas)

    return render_template('historial.html',
        ventas=ventas,
        total_general=total_general,
        filtros={
            'desde': fecha_desde, 'hasta': fecha_hasta,
            'tipo_pago': tipo_pago, 'buscar': buscar
        }
    )


@ventas_bp.route('/ventas/<int:venta_id>/recibo')
@login_required
def recibo(venta_id):
    db = get_db()
    comercio_id = session['comercio_id']
    
    venta = db.execute('''
        SELECT v.*, u.nombre as vendedor, COALESCE(c.nombre, '') as cliente_nombre,
               COALESCE(m.numero, '') as mesa_numero
        FROM ventas v
        JOIN usuarios u ON v.usuario_id = u.id
        LEFT JOIN clientes c ON v.cliente_id = c.id
        LEFT JOIN mesas m ON v.mesa_id = m.id
        WHERE v.id = ? AND v.comercio_id = ?
    ''', (venta_id, comercio_id)).fetchone()

    if not venta:
        flash('Venta no encontrada', 'danger')
        return redirect(url_for('ventas.historial'))

    detalles = db.execute('''
        SELECT dv.*, p.nombre as producto_nombre, p.variante
        FROM detalle_ventas dv
        JOIN productos p ON dv.producto_id = p.id
        WHERE dv.venta_id = ?
    ''', (venta_id,)).fetchall()

    return render_template('recibo.html', venta=venta, detalles=detalles)


@ventas_bp.route('/ventas/<int:venta_id>/anular', methods=['POST'])
@admin_required
def anular(venta_id):
    db = get_db()
    comercio_id = session['comercio_id']
    
    venta = db.execute('SELECT * FROM ventas WHERE id = ? AND comercio_id = ?', (venta_id, comercio_id)).fetchone()

    if not venta:
        flash('Venta no encontrada', 'danger')
        return redirect(url_for('ventas.historial'))

    if venta['anulada']:
        flash('Esta venta ya está anulada', 'warning')
        return redirect(url_for('ventas.historial'))

    # Si era crédito, revertir saldo
    if venta['tipo_pago'] == 'Crédito' and venta['cliente_id']:
        db.execute(
            'UPDATE clientes SET saldo_credito = MAX(0, saldo_credito - ?) WHERE id = ? AND comercio_id = ?',
            (venta['total'], venta['cliente_id'], comercio_id)
        )

    # Revertir stock si estaba habilitado
    detalles = db.execute('SELECT * FROM detalle_ventas WHERE venta_id = ?', (venta_id,)).fetchall()
    for item in detalles:
        prod = db.execute('SELECT * FROM productos WHERE id = ?', (item['producto_id'],)).fetchone()
        if prod and prod['stock'] is not None:
            db.execute('''
                UPDATE productos 
                SET stock = stock + ? 
                WHERE id = ? AND comercio_id = ?
            ''', (item['cantidad'], item['producto_id'], comercio_id))
            
            # Registrar entrada de inventario por devolución/anulación
            db.execute('''
                INSERT INTO movimientos_inventario (comercio_id, producto_id, tipo, cantidad, motivo, usuario_id)
                VALUES (?, ?, 'entrada', ?, 'Anulación de Venta', ?)
            ''', (comercio_id, item['producto_id'], item['cantidad'], session['user_id']))

    db.execute('UPDATE ventas SET anulada = 1 WHERE id = ? AND comercio_id = ?', (venta_id, comercio_id))
    db.commit()
    flash(f'Venta #{venta_id} anulada correctamente', 'info')
    return redirect(url_for('ventas.historial'))


# ── RUTAS EXCLUSIVAS PIZZERÍA: MESAS ──────────────────────────────────────────
@ventas_bp.route('/ventas/mesas')
@login_required
def mesas():
    if session.get('control_mesas') != 1:
        flash('El módulo de mesas no está activo para su comercio.', 'warning')
        return redirect(url_for('dashboard.index'))
        
    db = get_db()
    comercio_id = session['comercio_id']
    rows = db.execute('SELECT * FROM mesas WHERE comercio_id = ? ORDER BY numero', (comercio_id,)).fetchall()
    
    mesas_list = []
    for r in rows:
        m = dict(r)
        total = 0
        cant_items = 0
        if m['carrito_json']:
            try:
                cart = json.loads(m['carrito_json'])
                if isinstance(cart, dict):
                    for item in cart.values():
                        total += item['price'] * item['qty']
                        cant_items += item['qty']
                elif isinstance(cart, list):
                    for item in cart:
                        total += item['price'] * item['qty']
                        cant_items += item['qty']
            except Exception:
                pass
        m['total'] = total
        m['cant_items'] = cant_items
        mesas_list.append(m)
        
    return render_template('mesas.html', mesas=mesas_list)


@ventas_bp.route('/ventas/mesas/<int:mid>/liberar', methods=['POST'])
@login_required
def liberar_mesa(mid):
    if session.get('control_mesas') != 1:
        flash('El módulo de mesas no está activo para su comercio.', 'warning')
        return redirect(url_for('dashboard.index'))
        
    db = get_db()
    comercio_id = session['comercio_id']
    db.execute('''
        UPDATE mesas 
        SET estado = 'Libre', carrito_json = NULL 
        WHERE id = ? AND comercio_id = ?
    ''', (mid, comercio_id))
    db.commit()
    flash('Mesa liberada correctamente', 'info')
    return redirect(url_for('ventas.mesas'))


@ventas_bp.route('/ventas/mesas/agregar', methods=['POST'])
@admin_required
def agregar_mesa():
    if session.get('control_mesas') != 1:
        flash('El módulo de mesas no está activo para su comercio.', 'warning')
        return redirect(url_for('dashboard.index'))
        
    db = get_db()
    comercio_id = session['comercio_id']
    numero = request.form.get('numero', '').strip()
    
    if not numero:
        flash('El número o nombre de la mesa es obligatorio', 'warning')
        return redirect(url_for('ventas.mesas'))
        
    # Verificar duplicado
    existe = db.execute('SELECT id FROM mesas WHERE comercio_id = ? AND numero = ?', (comercio_id, numero)).fetchone()
    if existe:
        flash(f'⚠️ Ya existe una mesa con el nombre "{numero}"', 'danger')
        return redirect(url_for('ventas.mesas'))
        
    db.execute('INSERT INTO mesas (comercio_id, numero, estado) VALUES (?, ?, "Libre")', (comercio_id, numero))
    db.commit()
    flash(f'✅ {numero} agregada con éxito.', 'success')
    return redirect(url_for('ventas.mesas'))


@ventas_bp.route('/ventas/mesas/<int:mid>/eliminar', methods=['POST'])
@admin_required
def eliminar_mesa(mid):
    if session.get('control_mesas') != 1:
        flash('El módulo de mesas no está activo para su comercio.', 'warning')
        return redirect(url_for('dashboard.index'))
        
    db = get_db()
    comercio_id = session['comercio_id']
    
    # Verificar si está ocupada
    mesa = db.execute('SELECT * FROM mesas WHERE id = ? AND comercio_id = ?', (mid, comercio_id)).fetchone()
    if not mesa:
        flash('Mesa no encontrada', 'danger')
        return redirect(url_for('ventas.mesas'))
        
    if mesa['estado'] == 'Ocupada':
        flash('⚠️ No se puede eliminar una mesa que está Ocupada', 'danger')
        return redirect(url_for('ventas.mesas'))
        
    db.execute('DELETE FROM mesas WHERE id = ? AND comercio_id = ?', (mid, comercio_id))
    db.commit()
    flash(f'🗑️ {mesa["numero"]} eliminada con éxito.', 'success')
    return redirect(url_for('ventas.mesas'))
