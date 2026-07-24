from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db
from utils import login_required, admin_required

productos_bp = Blueprint('productos', __name__)

EMOJI_CAT = {
    'Helados': '🍦',
    'Fresas': '🍓',
    'Solteritas': '🍬',
    'Pizzas': '🍕',
    'Entradas': '🍝',
    'Bebidas': '🥤',
    'Herramientas': '🛠️',
    'Fijaciones': '🔩',
    'Eléctricos': '⚡',
    'Herramientas Eléctricas': '🔌',
    'Granos': '🌾',
    'Aceites': '🧴',
    'Lácteos': '🥛',
    'Cafetería': '☕',
}


@productos_bp.route('/productos')
@login_required
def index():
    db = get_db()
    comercio_id = session['comercio_id']
    productos = db.execute(
        'SELECT * FROM productos WHERE comercio_id = ? ORDER BY categoria, nombre',
        (comercio_id,)
    ).fetchall()
    return render_template('productos.html', productos=productos, emoji_cat=EMOJI_CAT)


@productos_bp.route('/productos/nuevo', methods=['POST'])
@admin_required
def nuevo():
    db = get_db()
    comercio_id = session['comercio_id']

    nombre = request.form.get('nombre', '').strip()
    categoria = request.form.get('categoria', '').strip()
    variante = request.form.get('variante', '').strip()
    precio = request.form.get('precio', 0)

    # Campos de inventario
    costo = request.form.get('costo', 0)
    stock = request.form.get('stock', '')
    stock_minimo = request.form.get('stock_minimo', '')
    sku = request.form.get('sku', '').strip()
    marca = request.form.get('marca', '').strip()
    unidad_medida = request.form.get('unidad_medida', 'Unidad').strip()
    control_stock = 1 if request.form.get('control_stock') == '1' else 0

    if not nombre or not categoria or not precio:
        flash('Nombre, categoría y precio son obligatorios', 'warning')
        return redirect(url_for('productos.index'))

    try:
        precio = float(precio)
    except ValueError:
        flash('El precio debe ser un número', 'danger')
        return redirect(url_for('productos.index'))

    try:
        costo = float(costo) if costo else 0.0
    except ValueError:
        costo = 0.0

    # Procesar stock y stock_minimo según control_stock
    p_stock = None
    p_stock_min = None
    p_marca = None
    p_unidad = None
    
    if control_stock == 1:
        try:
            p_stock = float(stock) if stock != '' else 0.0
        except ValueError:
            p_stock = 0.0
            
        try:
            p_stock_min = float(stock_minimo) if stock_minimo != '' else 0.0
        except ValueError:
            p_stock_min = 0.0
        p_marca = marca or None
        p_unidad = unidad_medida or 'Unidad'

    cursor = db.execute('''
        INSERT INTO productos (comercio_id, nombre, categoria, variante, precio, costo, stock, stock_minimo, sku, marca, unidad_medida)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (comercio_id, nombre, categoria, variante or None, precio, costo, p_stock, p_stock_min, sku or None, p_marca, p_unidad))
    producto_id = cursor.lastrowid

    # Si hay stock inicial, registrar movimiento
    if p_stock is not None and p_stock > 0:
        db.execute('''
            INSERT INTO movimientos_inventario (comercio_id, producto_id, tipo, cantidad, motivo, usuario_id)
            VALUES (?, ?, 'entrada', ?, 'Inventario Inicial', ?)
        ''', (comercio_id, producto_id, p_stock, session['user_id']))

    db.commit()
    flash(f'✅ Producto "{nombre}" agregado correctamente', 'success')
    return redirect(url_for('productos.index'))


@productos_bp.route('/productos/<int:pid>/editar', methods=['POST'])
@admin_required
def editar(pid):
    db = get_db()
    comercio_id = session['comercio_id']

    nombre = request.form.get('nombre', '').strip()
    categoria = request.form.get('categoria', '').strip()
    variante = request.form.get('variante', '').strip()
    precio = request.form.get('precio', 0)

    # Campos de inventario
    costo = request.form.get('costo', 0)
    stock_minimo = request.form.get('stock_minimo', '')
    sku = request.form.get('sku', '').strip()
    marca = request.form.get('marca', '').strip()
    unidad_medida = request.form.get('unidad_medida', 'Unidad').strip()
    control_stock = 1 if request.form.get('control_stock') == '1' else 0

    try:
        precio = float(precio)
    except ValueError:
        flash('Precio inválido', 'danger')
        return redirect(url_for('productos.index'))

    try:
        costo = float(costo) if costo else 0.0
    except ValueError:
        costo = 0.0

    if control_stock == 1:
        # Si antes no controlaba stock (era None), inicializar en 0
        prod = db.execute('SELECT stock FROM productos WHERE id = ?', (pid,)).fetchone()
        p_stock = prod['stock'] if (prod and prod['stock'] is not None) else 0.0
        
        try:
            p_stock_min = float(stock_minimo) if stock_minimo != '' else 0.0
        except ValueError:
            p_stock_min = 0.0
        p_marca = marca or None
        p_unidad = unidad_medida or 'Unidad'
    else:
        p_stock = None
        p_stock_min = None
        p_marca = None
        p_unidad = None

    db.execute('''
        UPDATE productos 
        SET nombre=?, categoria=?, variante=?, precio=?, costo=?, stock=?, stock_minimo=?, sku=?, marca=?, unidad_medida=? 
        WHERE id=? AND comercio_id=?
    ''', (nombre, categoria, variante or None, precio, costo, p_stock, p_stock_min, sku or None, p_marca, p_unidad, pid, comercio_id))
    
    db.commit()
    flash('✅ Producto actualizado', 'success')
    return redirect(url_for('productos.index'))


@productos_bp.route('/productos/<int:pid>/ajustar_stock', methods=['POST'])
@admin_required
def ajustar_stock(pid):
    db = get_db()
    comercio_id = session['comercio_id']
    
    tipo_movimiento = request.form.get('tipo_movimiento')
    cantidad = request.form.get('cantidad', 0)
    motivo = request.form.get('motivo', 'Ajuste manual').strip()

    if tipo_movimiento not in ('entrada', 'salida'):
        flash('Tipo de movimiento no válido', 'danger')
        return redirect(url_for('productos.index'))

    try:
        cantidad = float(cantidad)
    except ValueError:
        flash('Cantidad inválida', 'danger')
        return redirect(url_for('productos.index'))

    if cantidad <= 0:
        flash('La cantidad debe ser mayor a cero', 'warning')
        return redirect(url_for('productos.index'))

    producto = db.execute('SELECT * FROM productos WHERE id = ? AND comercio_id = ?', (pid, comercio_id)).fetchone()
    if not producto:
        flash('Producto no encontrado', 'danger')
        return redirect(url_for('productos.index'))

    # Si no tiene stock configurado, inicializarlo a 0
    stock_actual = producto['stock'] if producto['stock'] is not None else 0.0

    if tipo_movimiento == 'entrada':
        nuevo_stock = stock_actual + cantidad
    else:
        nuevo_stock = max(0.0, stock_actual - cantidad)

    db.execute('''
        UPDATE productos 
        SET stock = ? 
        WHERE id = ? AND comercio_id = ?
    ''', (nuevo_stock, pid, comercio_id))

    db.execute('''
        INSERT INTO movimientos_inventario (comercio_id, producto_id, tipo, cantidad, motivo, usuario_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (comercio_id, pid, tipo_movimiento, cantidad, motivo or 'Ajuste manual', session['user_id']))

    db.commit()
    flash(f'✅ Ajuste de stock registrado para "{producto["nombre"]}". Nuevo stock: {nuevo_stock:.1f}', 'success')
    return redirect(url_for('productos.index'))


@productos_bp.route('/productos/<int:pid>/toggle', methods=['POST'])
@admin_required
def toggle(pid):
    db = get_db()
    comercio_id = session['comercio_id']
    
    producto = db.execute('SELECT * FROM productos WHERE id = ? AND comercio_id = ?', (pid, comercio_id)).fetchone()
    if not producto:
        flash('Producto no encontrado', 'danger')
        return redirect(url_for('productos.index'))

    nuevo_estado = 0 if producto['activo'] else 1
    db.execute('UPDATE productos SET activo = ? WHERE id = ? AND comercio_id = ?', (nuevo_estado, pid, comercio_id))
    db.commit()
    estado_txt = 'activado' if nuevo_estado else 'desactivado'
    flash(f'Producto {estado_txt}', 'info')
    return redirect(url_for('productos.index'))
