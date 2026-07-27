# 🍦 CRM Antojitos y Más

Sistema de gestión (CRM) para la heladería **Antojitos y Más**. Desarrollado con Python + Flask + SQLite. Accesible desde cualquier dispositivo en la misma red WiFi.

---

## 🚀 Cómo iniciar

**Opción 1 — Doble clic:**
```
start.bat
```

**Opción 2 — Terminal:**
```bash
pip install -r requirements.txt
python app.py
```

Luego abrir en el navegador: `http://localhost:5000`

Desde celular o tablet en el mismo WiFi:
`http://[IP-de-tu-PC]:5000`

---

## 🔐 Usuarios por defecto

| Usuario | Correo                  | Contraseña | Rol      |
|---------|-------------------------|------------|----------|
| Admin   | admin@antojitos.com     | admin123   | Admin    |
| Mamá    | mama@antojitos.com      | mama123    | Vendedor |

> ⚠️ Cambia las contraseñas después del primer inicio de sesión.

---

## 🗺️ Módulos

| Módulo      | URL               | Descripción                         |
|-------------|-------------------|-------------------------------------|
| Dashboard   | `/dashboard`      | Métricas, gráficos, resumen del día |
| Nueva Venta | `/ventas/nueva`   | Registrar venta con carrito         |
| Historial   | `/ventas/historial`| Historial filtrable con anulaciones|
| Productos   | `/productos`      | Gestión del catálogo                |
| Clientes    | `/clientes`       | Créditos y historial por cliente    |
| Reportes    | `/reportes`       | Exportar Excel y PDF                |

---

## 🔗 API REST (para n8n)

Base URL: `http://[IP]:5000/api/`

Header requerido: `X-API-Key: antojitos-n8n-key-2024`

| Método | Endpoint        | Descripción                  |
|--------|-----------------|------------------------------|
| GET    | `/api/resumen`  | Totales del día              |
| GET    | `/api/ventas`   | Listar ventas (parámetros: `desde`, `hasta`) |
| GET    | `/api/productos`| Catálogo de productos        |
| GET    | `/api/clientes` | Clientes (parámetro: `credito=1`) |
| POST   | `/api/venta`    | Crear venta desde n8n        |

---

## 📦 Tecnologías

- **Backend:** Python 3 + Flask
- **Base de datos:** SQLite (archivo `antojitos.db`)
- **Frontend:** Bootstrap 5 + Chart.js + Vanilla JS
- **Reportes:** openpyxl (Excel) + reportlab (PDF)

---

## 🍦 Productos iniciales

| Producto                | Variante   | Precio   |
|-------------------------|------------|----------|
| Helado Maracuyá         | Por bola   | $4.000   |
| Helado Coco             | Por bola   | $4.000   |
| Helado Ron con Pasas    | Por bola   | $4.000   |
| Helado Queso/Bocadillo  | Por bola   | $4.000   |
| Helado Vainilla         | Por bola   | $4.000   |
| Helado Oreo             | Por bola   | $4.000   |
| Fresas con Crema        | Grande     | $10.000  |
| Fresas con Crema        | Pequeña    | $5.000   |
| Solteritas              | Unidad     | $2.000   |
