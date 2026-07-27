import sqlite3
import os
from werkzeug.security import generate_password_hash
from flask import current_app, g


def get_db():
    """Retorna la conexión a la base de datos para el request actual."""
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    """Cierra la conexión a la base de datos."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Inicializa la base de datos y crea las tablas si no existen."""
    db_path = current_app.config['DATABASE']

    # Verificación preventiva: respaldar DB antigua si existe pero no tiene soporte multi-inquilino
    needs_fresh = False
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comercios'")
            res = cur.fetchone()
            if not res:
                needs_fresh = True
        except Exception:
            needs_fresh = True
        finally:
            conn.close()

    if needs_fresh:
        old_path = db_path.replace('.db', '_old.db')
        counter = 1
        while os.path.exists(old_path):
            old_path = db_path.replace('.db', f'_old_{counter}.db')
            counter += 1
        try:
            os.rename(db_path, old_path)
            print(f"Base de datos antigua respaldada en {old_path}")
        except Exception as e:
            print(f"Error al respaldar base de datos antigua: {e}")

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    # Habilitar soporte de llaves foráneas en SQLite
    db.execute("PRAGMA foreign_keys = ON;")

    db.executescript('''
        CREATE TABLE IF NOT EXISTS saas_config (
            clave TEXT PRIMARY KEY,
            valor TEXT
        );

        CREATE TABLE IF NOT EXISTS comercios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL,
            direccion TEXT,
            telefono TEXT,
            logo_emoji TEXT DEFAULT '🏪',
            logo_url TEXT,
            api_key TEXT UNIQUE NOT NULL,
            activo INTEGER DEFAULT 1,
            zona_horaria TEXT DEFAULT 'America/Bogota',
            control_mesas INTEGER DEFAULT 0,
            fecha_ultimo_pago TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comercio_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT DEFAULT 'vendedor',
            activo INTEGER DEFAULT 1,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (comercio_id) REFERENCES comercios(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comercio_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            categoria TEXT NOT NULL,
            variante TEXT,
            precio REAL NOT NULL,
            costo REAL DEFAULT 0,
            stock REAL DEFAULT NULL,
            stock_minimo REAL DEFAULT NULL,
            sku TEXT,
            marca TEXT,
            unidad_medida TEXT DEFAULT 'Unidad',
            activo INTEGER DEFAULT 1,
            FOREIGN KEY (comercio_id) REFERENCES comercios(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comercio_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            telefono TEXT,
            email TEXT,
            nit_rut TEXT,
            direccion TEXT,
            saldo_credito REAL DEFAULT 0,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (comercio_id) REFERENCES comercios(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS mesas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comercio_id INTEGER NOT NULL,
            numero TEXT NOT NULL,
            estado TEXT DEFAULT 'Libre' CHECK(estado IN ('Libre', 'Ocupada', 'Por Servir')),
            carrito_json TEXT DEFAULT NULL,
            FOREIGN KEY (comercio_id) REFERENCES comercios(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comercio_id INTEGER NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total REAL NOT NULL,
            tipo_pago TEXT NOT NULL,
            cliente_id INTEGER,
            usuario_id INTEGER NOT NULL,
            notas TEXT,
            anulada INTEGER DEFAULT 0,
            tipo_pedido TEXT DEFAULT 'Para Llevar' CHECK(tipo_pedido IN ('Mesa', 'Para Llevar', 'Domicilio')),
            mesa_id INTEGER,
            estado_pedido TEXT DEFAULT 'Entregado' CHECK(estado_pedido IN ('Recibido', 'En Cocina', 'Listo', 'Entregado')),
            FOREIGN KEY (comercio_id) REFERENCES comercios(id) ON DELETE CASCADE,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE SET NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (mesa_id) REFERENCES mesas(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS detalle_ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            cantidad REAL NOT NULL,
            precio_unitario REAL NOT NULL,
            subtotal REAL NOT NULL,
            notas_item TEXT,
            FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE,
            FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS pagos_credito (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comercio_id INTEGER NOT NULL,
            cliente_id INTEGER NOT NULL,
            monto REAL NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            usuario_id INTEGER NOT NULL,
            notas TEXT,
            FOREIGN KEY (comercio_id) REFERENCES comercios(id) ON DELETE CASCADE,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS movimientos_inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comercio_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('entrada', 'salida')),
            cantidad REAL NOT NULL,
            motivo TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            usuario_id INTEGER NOT NULL,
            FOREIGN KEY (comercio_id) REFERENCES comercios(id) ON DELETE CASCADE,
            FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comercio_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            contacto TEXT,
            nit_rut TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (comercio_id) REFERENCES comercios(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comercio_id INTEGER NOT NULL,
            proveedor_id INTEGER,
            factura_numero TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total REAL NOT NULL,
            usuario_id INTEGER NOT NULL,
            notas TEXT,
            FOREIGN KEY (comercio_id) REFERENCES comercios(id) ON DELETE CASCADE,
            FOREIGN KEY (proveedor_id) REFERENCES proveedores(id) ON DELETE SET NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS detalle_compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compra_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            cantidad REAL NOT NULL,
            costo_unitario REAL NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (compra_id) REFERENCES compras(id) ON DELETE CASCADE,
            FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comercio_id INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            descripcion TEXT,
            monto REAL NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            usuario_id INTEGER NOT NULL,
            FOREIGN KEY (comercio_id) REFERENCES comercios(id) ON DELETE CASCADE,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS caja_diaria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comercio_id INTEGER NOT NULL,
            fecha_apertura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_cierre TIMESTAMP,
            monto_inicial REAL NOT NULL,
            monto_final REAL,
            ingresos_efectivo REAL DEFAULT 0,
            ingresos_tarjeta REAL DEFAULT 0,
            ingresos_transferencia REAL DEFAULT 0,
            ingresos_credito REAL DEFAULT 0,
            gastos_totales REAL DEFAULT 0,
            estado TEXT DEFAULT 'Abierta' CHECK(estado IN ('Abierta', 'Cerrada')),
            usuario_apertura_id INTEGER NOT NULL,
            usuario_cierre_id INTEGER,
            notas TEXT,
            FOREIGN KEY (comercio_id) REFERENCES comercios(id) ON DELETE CASCADE,
            FOREIGN KEY (usuario_apertura_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (usuario_cierre_id) REFERENCES usuarios(id) ON DELETE SET NULL
        );
    ''')

    if not needs_fresh:
        # Alter tables safely if columns are missing
        try:
            db.execute("ALTER TABLE comercios ADD COLUMN nit_rut TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE comercios ADD COLUMN moneda_simbolo TEXT DEFAULT '$';")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE comercios ADD COLUMN moneda_formato TEXT DEFAULT 'es-CO';")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE comercios ADD COLUMN logo_url TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE comercios ADD COLUMN activo INTEGER DEFAULT 1;")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE comercios ADD COLUMN zona_horaria TEXT DEFAULT 'America/Bogota';")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE comercios ADD COLUMN control_mesas INTEGER DEFAULT 0;")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE comercios ADD COLUMN fecha_ultimo_pago TIMESTAMP;")
            db.execute("UPDATE comercios SET fecha_ultimo_pago = fecha_registro WHERE fecha_ultimo_pago IS NULL;")
        except sqlite3.OperationalError:
            pass

        db.commit()

        # Recrear tabla usuarios para eliminar restricción de rol si existe (solo si la tabla existe previamente)
        usuarios_exist = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios'").fetchone()
        if usuarios_exist:
            try:
                db.execute("INSERT INTO usuarios (comercio_id, nombre, email, password_hash, rol) VALUES (1, 'Test', 'test_migration@crm.com', '1', 'superadmin')")
                db.execute("DELETE FROM usuarios WHERE email = 'test_migration@crm.com'")
                db.commit()
            except (sqlite3.IntegrityError, sqlite3.OperationalError):
                try:
                    db.execute("PRAGMA foreign_keys = OFF;")
                    db.execute("ALTER TABLE usuarios RENAME TO usuarios_old;")
                    db.execute('''
                        CREATE TABLE usuarios (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            comercio_id INTEGER NOT NULL,
                            nombre TEXT NOT NULL,
                            email TEXT UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            rol TEXT DEFAULT 'vendedor',
                            activo INTEGER DEFAULT 1,
                            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (comercio_id) REFERENCES comercios(id) ON DELETE CASCADE
                        );
                    ''')
                    db.execute('''
                        INSERT INTO usuarios (id, comercio_id, nombre, email, password_hash, rol, activo, fecha_registro)
                        SELECT id, comercio_id, nombre, email, password_hash, rol, activo, fecha_registro FROM usuarios_old;
                    ''')
                    db.execute("DROP TABLE usuarios_old;")
                    db.execute("PRAGMA foreign_keys = ON;")
                    db.commit()
                    print("Migracion de tabla usuarios completada con exito.")
                except Exception as e:
                    db.execute("PRAGMA foreign_keys = ON;")
                    print(f"Error al migrar tabla usuarios: {e}")
                    db.rollback()

        # Recrear tabla comercios para eliminar restricción de tipo si existe (solo si la tabla existe previamente)
        comercios_exist = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comercios'").fetchone()
        if comercios_exist:
            try:
                db.execute("INSERT INTO comercios (nombre, tipo, logo_emoji, api_key) VALUES ('Test', 'tipo_de_prueba_largo_y_libre', '🏪', 'key-test-1')")
                db.execute("DELETE FROM comercios WHERE api_key = 'key-test-1'")
                db.commit()
            except (sqlite3.IntegrityError, sqlite3.OperationalError):
                try:
                    db.execute("PRAGMA foreign_keys = OFF;")
                    db.execute("ALTER TABLE comercios RENAME TO comercios_old;")
                    db.execute('''
                        CREATE TABLE comercios (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            nombre TEXT NOT NULL,
                            tipo TEXT NOT NULL,
                            direccion TEXT,
                            telefono TEXT,
                            logo_emoji TEXT DEFAULT '🏪',
                            logo_url TEXT,
                            api_key TEXT UNIQUE NOT NULL,
                            activo INTEGER DEFAULT 1,
                            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    ''')
                    db.execute('''
                        INSERT INTO comercios (id, nombre, tipo, direccion, telefono, logo_emoji, logo_url, api_key, activo, fecha_registro)
                        SELECT id, nombre, tipo, direccion, telefono, logo_emoji, logo_url, api_key, activo, fecha_registro FROM comercios_old;
                    ''')
                    db.execute("DROP TABLE comercios_old;")
                    db.execute("PRAGMA foreign_keys = ON;")
                    db.commit()
                    print("Migracion de tabla comercios completada con exito.")
                except Exception as e:
                    db.execute("PRAGMA foreign_keys = ON;")
                    print(f"Error al migrar tabla comercios: {e}")
                    db.rollback()

    # Insertar comercios y datos iniciales solo si la tabla comercios está vacía Y SEED_DEMO_DATA=true explícitamente
    count = db.execute('SELECT COUNT(*) FROM comercios').fetchone()[0]
    seed_allowed = os.environ.get('SEED_DEMO_DATA', 'false').lower() in ('true', '1', 't')
    if count == 0 and seed_allowed:
        super_email = os.environ.get('SUPERADMIN_EMAIL', 'super@saas.com').strip().lower()
        super_pass = os.environ.get('SUPERADMIN_PASSWORD', 'super123').strip()

        # 1. HELADERÍA DEMO
        cur = db.execute('''
            INSERT INTO comercios (nombre, tipo, logo_emoji, api_key)
            VALUES (?, ?, ?, ?)
        ''', ('Heladería Cremosa 🍦', 'heladeria', '🍦', 'key-heladeria-123'))
        heladeria_id = cur.lastrowid

        db.execute('''
            INSERT INTO usuarios (comercio_id, nombre, email, password_hash, rol)
            VALUES (?, ?, ?, ?, ?)
        ''', (heladeria_id, 'Admin Heladería', 'admin@heladeria.com', generate_password_hash('admin123'), 'admin'))

        db.execute('''
            INSERT INTO usuarios (comercio_id, nombre, email, password_hash, rol)
            VALUES (?, ?, ?, ?, ?)
        ''', (heladeria_id, 'Super Administrador', super_email, generate_password_hash(super_pass), 'superadmin'))

        productos_heladeria = [
            ('Helado Maracuyá',          'Helados',   'Por bola', 4000),
            ('Helado Coco',              'Helados',   'Por bola', 4000),
            ('Helado Ron con Pasas',     'Helados',   'Por bola', 4000),
            ('Helado Queso/Bocadillo',   'Helados',   'Por bola', 4000),
            ('Helado Oreo',              'Helados',   'Por bola', 4000),
            ('Fresas con Crema',         'Fresas',    'Grande',   10000),
            ('Fresas con Crema',         'Fresas',    'Pequeña',  5000),
            ('Solteritas',               'Solteritas','Unidad',   2000),
        ]
        for nombre, categoria, variante, precio in productos_heladeria:
            db.execute('''
                INSERT INTO productos (comercio_id, nombre, categoria, variante, precio)
                VALUES (?, ?, ?, ?, ?)
            ''', (heladeria_id, nombre, categoria, variante, precio))

        # 2. PIZZERÍA DEMO
        cur = db.execute('''
            INSERT INTO comercios (nombre, tipo, logo_emoji, api_key, control_mesas)
            VALUES (?, ?, ?, ?, 1)
        ''', ('Pizzería Don Giovanni 🍕', 'pizzeria', '🍕', 'key-pizzeria-123'))
        pizzeria_id = cur.lastrowid

        db.execute('''
            INSERT INTO usuarios (comercio_id, nombre, email, password_hash, rol)
            VALUES (?, ?, ?, ?, ?)
        ''', (pizzeria_id, 'Admin Pizzería', 'admin@pizzeria.com', generate_password_hash('pizzeria123'), 'admin'))

        # Mesas
        for num in ['Mesa 1', 'Mesa 2', 'Mesa 3', 'Mesa 4', 'Mesa 5']:
            db.execute('INSERT INTO mesas (comercio_id, numero, estado) VALUES (?, ?, ?)', (pizzeria_id, num, 'Libre'))

        productos_pizzeria = [
            ('Pizza Margarita', 'Pizzas', 'Personal', 12000),
            ('Pizza Margarita', 'Pizzas', 'Familiar', 30000),
            ('Pizza Pepperoni', 'Pizzas', 'Personal', 14000),
            ('Pizza Pepperoni', 'Pizzas', 'Familiar', 35000),
            ('Pizza Hawaiana',  'Pizzas', 'Personal', 14000),
            ('Pizza Hawaiana',  'Pizzas', 'Familiar', 35000),
            ('Coca-Cola 1.5L',  'Bebidas', 'Familiar', 6000),
            ('Coca-Cola 350ml', 'Bebidas', 'Personal', 3000),
        ]
        for nombre, categoria, variante, precio in productos_pizzeria:
            db.execute('''
                INSERT INTO productos (comercio_id, nombre, categoria, variante, precio)
                VALUES (?, ?, ?, ?, ?)
            ''', (pizzeria_id, nombre, categoria, variante, precio))

        # 3. FERRETERÍA DEMO
        cur = db.execute('''
            INSERT INTO comercios (nombre, tipo, logo_emoji, api_key)
            VALUES (?, ?, ?, ?)
        ''', ('Ferretería El Tornillo 🛠️', 'ferreteria', '🛠️', 'key-ferreteria-123'))
        ferreteria_id = cur.lastrowid

        db.execute('''
            INSERT INTO usuarios (comercio_id, nombre, email, password_hash, rol)
            VALUES (?, ?, ?, ?, ?)
        ''', (ferreteria_id, 'Admin Ferretería', 'admin@ferreteria.com', generate_password_hash('ferreteria123'), 'admin'))

        productos_ferreteria = [
            ('Martillo de Uña', 'Herramientas', 'Unidad', 18000, 11000, 15, 3, 'Stanley', 'Unidad'),
            ('Destornillador Estrella', 'Herramientas', 'Unidad', 7500, 4500, 20, 5, 'Tramontina', 'Unidad'),
            ('Clavos de Acero 2"', 'Fijaciones', 'Libra', 6000, 3500, 50, 10, 'Generico', 'Libra'),
            ('Cinta Aislante Negra', 'Eléctricos', 'Rollo', 4000, 2200, 8, 5, '3M', 'Rollo'),
            ('Taladro Percutor 500W', 'Herramientas Eléctricas', 'Unidad', 185000, 125000, 4, 2, 'DeWalt', 'Unidad'),
        ]
        for nombre, cat, var, prec, cost, stock, stock_min, marca, unid in productos_ferreteria:
            db.execute('''
                INSERT INTO productos (comercio_id, nombre, categoria, variante, precio, costo, stock, stock_minimo, marca, unidad_medida)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (ferreteria_id, nombre, cat, var, prec, cost, stock, stock_min, marca, unid))

        # 4. GENERAL RETAIL DEMO
        cur = db.execute('''
            INSERT INTO comercios (nombre, tipo, logo_emoji, api_key)
            VALUES (?, ?, ?, ?)
        ''', ('Minimercado La Esquina 🏪', 'general', '🏪', 'key-general-123'))
        general_id = cur.lastrowid

        db.execute('''
            INSERT INTO usuarios (comercio_id, nombre, email, password_hash, rol)
            VALUES (?, ?, ?, ?, ?)
        ''', (general_id, 'Admin Minimercado', 'admin@laesquina.com', generate_password_hash('laesquina123'), 'admin'))

        productos_general = [
            ('Arroz Diana 1kg', 'Granos', 'Bolsa', 4200, 3100, 100, 15, 'Diana', 'Bolsa', '7702001001'),
            ('Aceite Girasol 1L', 'Aceites', 'Botella', 16500, 12500, 30, 5, 'Gourmet', 'Botella', '7702001002'),
            ('Leche Entera 1L', 'Lácteos', 'Bolsa', 3800, 2900, 45, 8, 'Colanta', 'Bolsa', '7702001003'),
            ('Café Sello Rojo 500g', 'Cafetería', 'Bolsa', 12000, 9000, 25, 5, 'Sello Rojo', 'Bolsa', '7702001004'),
        ]
        for nombre, cat, var, prec, cost, stock, stock_min, marca, unid, sku in productos_general:
            db.execute('''
                INSERT INTO productos (comercio_id, nombre, categoria, variante, precio, costo, stock, stock_minimo, marca, unidad_medida, sku)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (general_id, nombre, cat, var, prec, cost, stock, stock_min, marca, unid, sku))

        db.commit()

    db.close()
