from flask import Blueprint, render_template, redirect, url_for, session
from database import get_db
from utils import login_required
from datetime import datetime, timedelta

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def index():
    if session.get('rol') == 'superadmin':
        return redirect(url_for('superadmin.index'))
    db = get_db()
    hoy = datetime.now().strftime('%Y-%m-%d')
    hace_7 = (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d')
    comercio_id = session['comercio_id']

    # ── Métricas del día ──────────────────────────────────────────────
    ventas_hoy = db.execute('''
        SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
        FROM ventas WHERE DATE(fecha) = ? AND anulada = 0 AND comercio_id = ?
    ''', (hoy, comercio_id)).fetchone()

    ventas_semana = db.execute('''
        SELECT COALESCE(SUM(total), 0) as total
        FROM ventas WHERE DATE(fecha) >= ? AND anulada = 0 AND comercio_id = ?
    ''', (hace_7, comercio_id)).fetchone()

    creditos = db.execute('''
        SELECT COUNT(*) as count, COALESCE(SUM(saldo_credito), 0) as total
        FROM clientes WHERE saldo_credito > 0 AND comercio_id = ?
    ''', (comercio_id,)).fetchone()

    # ── Ventas por día (últimos 7 días) ───────────────────────────────
    ventas_por_dia = db.execute('''
        SELECT DATE(fecha) as dia, COALESCE(SUM(total), 0) as total, COUNT(*) as count
        FROM ventas WHERE DATE(fecha) >= ? AND anulada = 0 AND comercio_id = ?
        GROUP BY DATE(fecha) ORDER BY dia
    ''', (hace_7, comercio_id)).fetchall()

    # Rellenar días vacíos
    dias_dict = {row['dia']: row['total'] for row in ventas_por_dia}
    labels_dias = []
    valores_dias = []
    for i in range(7):
        d = (datetime.now() - timedelta(days=6-i)).strftime('%Y-%m-%d')
        labels_dias.append(d[5:])   # MM-DD
        valores_dias.append(dias_dict.get(d, 0))

    # ── Métodos de pago hoy ───────────────────────────────────────────
    pagos_hoy = db.execute('''
        SELECT tipo_pago, COUNT(*) as count, COALESCE(SUM(total), 0) as total
        FROM ventas WHERE DATE(fecha) = ? AND anulada = 0 AND comercio_id = ?
        GROUP BY tipo_pago
    ''', (hoy, comercio_id)).fetchall()

    # ── Productos más vendidos hoy ────────────────────────────────────
    top_productos = db.execute('''
        SELECT p.nombre, p.variante, SUM(dv.cantidad) as cantidad, SUM(dv.subtotal) as total
        FROM detalle_ventas dv
        JOIN productos p ON dv.producto_id = p.id
        JOIN ventas v ON dv.venta_id = v.id
        WHERE DATE(v.fecha) = ? AND v.anulada = 0 AND v.comercio_id = ?
        GROUP BY p.id ORDER BY cantidad DESC LIMIT 5
    ''', (hoy, comercio_id)).fetchall()

    # ── Últimas ventas ────────────────────────────────────────────────
    ultimas_ventas = db.execute('''
        SELECT v.*, u.nombre as vendedor,
               COALESCE(c.nombre, '') as cliente_nombre
        FROM ventas v
        JOIN usuarios u ON v.usuario_id = u.id
        LEFT JOIN clientes c ON v.cliente_id = c.id
        WHERE v.anulada = 0 AND v.comercio_id = ?
        ORDER BY v.fecha DESC LIMIT 8
    ''', (comercio_id,)).fetchall()

    # ── Clientes con crédito pendiente ────────────────────────────────
    clientes_credito = db.execute('''
        SELECT * FROM clientes WHERE saldo_credito > 0 AND comercio_id = ?
        ORDER BY saldo_credito DESC LIMIT 5
    ''', (comercio_id,)).fetchall()

    # ── Productos con bajo stock (para todos los comercios que controlen stock)
    bajo_stock = db.execute('''
        SELECT * FROM productos
        WHERE activo = 1 AND stock IS NOT NULL AND stock_minimo IS NOT NULL 
          AND stock <= stock_minimo AND comercio_id = ?
        ORDER BY stock ASC LIMIT 5
    ''', (comercio_id,)).fetchall()

    return render_template('dashboard.html',
        ventas_hoy=ventas_hoy,
        ventas_semana=ventas_semana,
        creditos=creditos,
        labels_dias=labels_dias,
        valores_dias=valores_dias,
        pagos_hoy=[dict(p) for p in pagos_hoy],
        top_productos=top_productos,
        ultimas_ventas=ultimas_ventas,
        clientes_credito=clientes_credito,
        bajo_stock=bajo_stock,
    )
