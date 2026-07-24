from flask import Blueprint, request, jsonify, current_app, g
from database import get_db
from datetime import datetime
from functools import wraps

api_bp = Blueprint('api', __name__)


def api_key_required(f):
    """Decorator: valida API Key dinámica contra la tabla de comercios y guarda el comercio en g."""
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if not key:
            return jsonify({'error': 'API Key no proporcionada'}), 401

        db = get_db()
        comercio = db.execute('SELECT * FROM comercios WHERE api_key = ?', (key,)).fetchone()
        if not comercio:
            return jsonify({'error': 'API Key inválida'}), 401

        # Guardar en contexto global g para uso de los endpoints
        g.comercio_id = comercio['id']
        g.comercio_tipo = comercio['tipo']
        return f(*args, **kwargs)
    return decorated


# ── Resumen del día ────────────────────────────────────────────────────────────
@api_bp.route('/resumen')
@api_key_required
def resumen():
    db = get_db()
    hoy = datetime.now().strftime('%Y-%m-%d')
    comercio_id = g.comercio_id

    stats = db.execute('''
        SELECT COUNT(*) as ventas, COALESCE(SUM(total), 0) as total,
               COALESCE(SUM(CASE WHEN tipo_pago='Efectivo' THEN total ELSE 0 END), 0) as efectivo,
               COALESCE(SUM(CASE WHEN tipo_pago='Tarjeta' THEN total ELSE 0 END), 0) as tarjeta,
               COALESCE(SUM(CASE WHEN tipo_pago='Transferencia' THEN total ELSE 0 END), 0) as transferencia,
               COALESCE(SUM(CASE WHEN tipo_pago='Crédito' THEN total ELSE 0 END), 0) as credito
        FROM ventas 
        WHERE DATE(fecha) = ? AND anulada = 0 AND comercio_id = ?
    ''', (hoy, comercio_id)).fetchone()

    creditos = db.execute('''
        SELECT COUNT(*) as clientes, COALESCE(SUM(saldo_credito), 0) as total 
        FROM clientes 
        WHERE saldo_credito > 0 AND comercio_id = ?
    ''', (comercio_id,)).fetchone()

    return jsonify({
        'fecha': hoy,
        'comercio_id': comercio_id,
        'ventas_count': stats['ventas'],
        'total_dia': stats['total'],
        'efectivo': stats['efectivo'],
        'tarjeta': stats['tarjeta'],
        'transferencia': stats['transferencia'],
        'credito': stats['credito'],
        'clientes_con_credito': creditos['clientes'],
        'total_credito_pendiente': creditos['total'],
    })


# ── Ventas ─────────────────────────────────────────────────────────────────────
@api_bp.route('/ventas')
@api_key_required
def ventas():
    db = get_db()
    comercio_id = g.comercio_id
    fecha_desde = request.args.get('desde', datetime.now().strftime('%Y-%m-%d'))
    fecha_hasta = request.args.get('hasta', datetime.now().strftime('%Y-%m-%d'))
    limit = int(request.args.get('limit', 100))

    rows = db.execute('''
        SELECT v.id, v.fecha, v.total, v.tipo_pago, v.notas,
               u.nombre as vendedor, COALESCE(c.nombre, '') as cliente
        FROM ventas v
        JOIN usuarios u ON v.usuario_id = u.id
        LEFT JOIN clientes c ON v.cliente_id = c.id
        WHERE DATE(v.fecha) BETWEEN ? AND ? AND v.anulada = 0 AND v.comercio_id = ?
        ORDER BY v.fecha DESC LIMIT ?
    ''', (fecha_desde, fecha_hasta, comercio_id, limit)).fetchall()

    return jsonify([dict(r) for r in rows])


# ── Productos ──────────────────────────────────────────────────────────────────
@api_bp.route('/productos')
@api_key_required
def productos():
    db = get_db()
    comercio_id = g.comercio_id
    activo_only = request.args.get('activo', '1') == '1'
    
    query = 'SELECT * FROM productos WHERE comercio_id = ?'
    params = [comercio_id]
    if activo_only:
        query += ' AND activo = 1'
    query += ' ORDER BY categoria, nombre'
    
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Clientes con crédito ───────────────────────────────────────────────────────
@api_bp.route('/clientes')
@api_key_required
def clientes():
    db = get_db()
    comercio_id = g.comercio_id
    solo_credito = request.args.get('credito', '0') == '1'
    
    query = 'SELECT * FROM clientes WHERE comercio_id = ?'
    params = [comercio_id]
    if solo_credito:
        query += ' AND saldo_credito > 0'
    query += ' ORDER BY saldo_credito DESC, nombre'
    
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Registrar venta desde API / Integración n8n ────────────────────────────────
@api_bp.route('/venta', methods=['POST'])
@api_key_required
def crear_venta():
    db = get_db()
    comercio_id = g.comercio_id
    comercio_tipo = g.comercio_tipo
    data = request.get_json(silent=True) or {}

    tipo_pago = data.get('tipo_pago', 'Efectivo')
    items = data.get('items', [])
    cliente_nombre = data.get('cliente', '')
    notas = data.get('notas', 'Venta registrada vía API')
    
    # Obtener el primer usuario administrador del comercio para asignarle la venta
    usr = db.execute('SELECT id FROM usuarios WHERE comercio_id = ? AND rol = "admin" LIMIT 1', (comercio_id,)).fetchone()
    if not usr:
        return jsonify({'error': 'No se encontró un usuario administrador para este comercio'}), 400
    usuario_id = usr['id']

    if not items:
        return jsonify({'error': 'Se requiere al menos un item'}), 400

    if tipo_pago not in ('Efectivo', 'Tarjeta', 'Transferencia', 'Crédito'):
        return jsonify({'error': 'Tipo de pago no válido'}), 400

    total = 0
    items_validados = []
    for item in items:
        producto_id = item.get('producto_id')
        qty = max(0.01, float(item.get('cantidad', 1)))
        
        prod = db.execute(
            'SELECT * FROM productos WHERE id = ? AND activo = 1 AND comercio_id = ?',
            (producto_id, comercio_id)
        ).fetchone()
        if not prod:
            return jsonify({'error': f'Producto {producto_id} no encontrado o inactivo'}), 404
            
        # Validar stock físico si aplica
        if prod['stock'] is not None and prod['stock'] < qty:
            return jsonify({'error': f'Stock insuficiente para "{prod["nombre"]}". Stock disponible: {prod["stock"]}'}), 400

        subtotal = prod['precio'] * qty
        total += subtotal
        items_validados.append({'prod': prod, 'qty': qty, 'subtotal': subtotal, 'notas_item': item.get('notas', '')})

    # Buscar/crear cliente
    cliente_id = None
    if cliente_nombre:
        c = db.execute('SELECT id FROM clientes WHERE nombre = ? AND comercio_id = ?', (cliente_nombre, comercio_id)).fetchone()
        if not c:
            db.execute('INSERT INTO clientes (comercio_id, nombre) VALUES (?, ?)', (comercio_id, cliente_nombre))
            db.commit()
            c = db.execute('SELECT id FROM clientes WHERE nombre = ? AND comercio_id = ?', (cliente_nombre, comercio_id)).fetchone()
        cliente_id = c['id']

    if tipo_pago == 'Crédito' and not cliente_id:
        return jsonify({'error': 'Para ventas a crédito se requiere el nombre del cliente'}), 400

    # Registrar Venta
    from datetime import datetime, timezone, timedelta
    tz_colombia = timezone(timedelta(hours=-5))
    fecha_colombia = datetime.now(tz_colombia).strftime('%Y-%m-%d %H:%M:%S')

    cur = db.execute('''
        INSERT INTO ventas (comercio_id, fecha, total, tipo_pago, cliente_id, usuario_id, notas)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (comercio_id, fecha_colombia, total, tipo_pago, cliente_id, usuario_id, notas))
    venta_id = cur.lastrowid

    # Insertar detalles y descontar stock
    for item in items_validados:
        db.execute('''
            INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, precio_unitario, subtotal, notas_item) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (venta_id, item['prod']['id'], item['qty'], item['prod']['precio'], item['subtotal'], item['notas_item']))

        # Descontar stock si está habilitado
        if item['prod']['stock'] is not None:
            db.execute('''
                UPDATE productos 
                SET stock = MAX(0, stock - ?) 
                WHERE id = ? AND comercio_id = ?
            ''', (item['qty'], item['prod']['id'], comercio_id))

            # Registrar movimiento
            db.execute('''
                INSERT INTO movimientos_inventario (comercio_id, producto_id, tipo, cantidad, motivo, usuario_id)
                VALUES (?, ?, 'salida', ?, 'Venta API', ?)
            ''', (comercio_id, item['prod']['id'], item['qty'], usuario_id))

    if tipo_pago == 'Crédito' and cliente_id:
        db.execute(
            'UPDATE clientes SET saldo_credito = saldo_credito + ? WHERE id = ? AND comercio_id = ?',
            (total, cliente_id, comercio_id)
        )

    db.commit()
    return jsonify({'ok': True, 'venta_id': venta_id, 'total': total}), 201
