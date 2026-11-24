import os
import secrets
import sqlite3
import csv
from pathlib import Path
from datetime import date, datetime
from io import StringIO

from flask import Flask, request, redirect, url_for, flash, render_template_string, Response

# CONFIGURACION
CARPETA = Path(__file__).resolve().parent
BASE_DATOS = CARPETA / "reciclar.db"
RESPALDOS = CARPETA / "copias_seguridad"

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

MATERIALES = ["Plástico", "Papel", "Cartón", "Metal", "Vidrio"]
UNIDADES = ["Kg", "Unidades"]


# BASE DE DATOS
def conectar():
    db = sqlite3.connect(BASE_DATOS)
    db.row_factory = sqlite3.Row
    return db


def iniciar_bd():
    with conectar() as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS materiales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            material TEXT NOT NULL,
            cantidad REAL NOT NULL,
            unidad TEXT NOT NULL,
            observacion TEXT
        )
        """)


# DISEÑO GENERAL
HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EcoGestión - Reciclaje</title>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:Arial;background:#f1f6f2;color:#263c30}
header{background:#174e37;color:white;padding:22px 30px}
header h1{margin:0}
.layout{display:flex;min-height:90vh}
nav{width:220px;background:white;padding:20px}
nav a{display:block;padding:13px;margin-bottom:7px;text-decoration:none;color:#24533a;border-radius:8px}
nav a:hover{background:#e1f1e6}
main{flex:1;padding:30px;min-width:0}
.card,.panel{background:white;padding:22px;border-radius:12px;margin-bottom:18px;box-shadow:0 2px 8px #00000010}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:15px}
.numero{font-size:28px;color:#18804c;font-weight:bold;margin-top:10px}
input,select,textarea{width:100%;padding:11px;border:1px solid #ccd8cf;border-radius:7px}
label{display:block;margin:13px 0 6px;font-weight:bold}
button,.btn{display:inline-block;background:#18804c;color:white;border:0;padding:11px 16px;border-radius:7px;text-decoration:none;cursor:pointer}
.sec{background:#e5eee7;color:#24533a}
.danger{background:#b83d3d}
table{width:100%;border-collapse:collapse;background:white}
th,td{padding:12px;text-align:left;border-bottom:1px solid #e6ece7;font-size:13px}
th{background:#e7f1e9}
.tabla{overflow-x:auto}
.barra{height:12px;background:#e7eee8;border-radius:10px;margin:8px 0 18px;overflow:hidden}
.barra div{height:100%;background:#23945b}
.alert{background:#e0f2e5;color:#205c35;padding:12px;margin-bottom:15px;border-radius:8px}
.error{background:#fbe4e4;color:#a02c2c}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:15px}
@media(max-width:700px){.layout{display:block}nav{width:100%;display:flex;overflow:auto}nav a{white-space:nowrap}main{padding:15px}.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
<h1>♻ EcoGestión</h1>
<p>Sistema de Gestión de Materiales Reciclables</p>
</header>
<div class="layout">
<nav>
<a href="/">⌂ Inicio</a>
<a href="/nuevo">＋ Registrar material</a>
<a href="/registros">▤ Consultar registros</a>
<a href="/estadisticas">▥ Estadísticas</a>
<a href="/exportar">⇩ Exportar información</a>
<a href="/respaldo">▣ Copia de seguridad</a>
</nav>
<main>
{% for categoria,mensaje in get_flashed_messages(with_categories=true) %}
<div class="alert {{ 'error' if categoria=='error' else '' }}">{{mensaje}}</div>
{% endfor %}
{{contenido|safe}}
</main>
</div>
</body>
</html>
"""


def pagina(contenido):
    return render_template_string(HTML, contenido=contenido)


# INICIO
@app.route("/")
def inicio():
    with conectar() as db:
        total = db.execute("SELECT COUNT(*) FROM materiales").fetchone()[0]
        kg = db.execute("SELECT COALESCE(SUM(cantidad),0) FROM materiales WHERE unidad='Kg'").fetchone()[0]
        unidades = db.execute("SELECT COALESCE(SUM(cantidad),0) FROM materiales WHERE unidad='Unidades'").fetchone()[0]
        recientes = db.execute("SELECT * FROM materiales ORDER BY id DESC LIMIT 5").fetchall()

    contenido = render_template_string("""
    <h2>Panel principal</h2>
    <p>Bienvenido al sistema de gestión de reciclaje.</p>
    <div class="cards">
      <div class="card">Registros<div class="numero">{{total}}</div></div>
      <div class="card">Peso recibido<div class="numero">{{"%.2f"|format(kg)}} kg</div></div>
      <div class="card">Unidades recibidas<div class="numero">{{"%.2f"|format(unidades)}}</div></div>
    </div>
    <div class="panel">
      <h3>Últimos registros</h3>
      {% if recientes %}
      <div class="tabla"><table>
      <tr><th>ID</th><th>Fecha</th><th>Material</th><th>Cantidad</th><th>Unidad</th></tr>
      {% for r in recientes %}
      <tr><td>{{r.id}}</td><td>{{r.fecha}}</td><td>{{r.material}}</td><td>{{r.cantidad}}</td><td>{{r.unidad}}</td></tr>
      {% endfor %}
      </table></div>
      {% else %}
      <p>Aún no hay registros. Comenzá cargando un material.</p>
      {% endif %}
      <br><a class="btn" href="/nuevo">Registrar material</a>
    </div>
    """, total=total, kg=kg, unidades=unidades, recientes=recientes)

    return pagina(contenido)


# FORMULARIO
@app.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        try:
            fecha = request.form["fecha"]
            datetime.strptime(fecha, "%Y-%m-%d")
            material = request.form["material"]
            cantidad = float(request.form["cantidad"].replace(",", "."))
            unidad = request.form["unidad"]
            observacion = request.form.get("observacion", "")

            if cantidad <= 0 or material not in MATERIALES or unidad not in UNIDADES:
                raise ValueError

            with conectar() as db:
                db.execute("""
                INSERT INTO materiales(fecha,material,cantidad,unidad,observacion)
                VALUES(?,?,?,?,?)
                """, (fecha, material, cantidad, unidad, observacion))

            flash("Material registrado correctamente.")
            return redirect("/registros")

        except (ValueError, KeyError):
            flash("Verifique los datos ingresados. La cantidad debe ser positiva.", "error")

    contenido = render_template_string("""
    <h2>Registrar material</h2>
    <div class="panel">
    <form method="POST">
    <label>Número de registro</label>
    <input value="Automático al guardar" disabled>
    <div class="grid">
    <div><label>Fecha</label><input type="date" name="fecha" value="{{hoy}}" required></div>
    <div><label>Material</label>
    <select name="material" required>
    <option value="">Seleccionar</option>
    {% for m in materiales %}<option>{{m}}</option>{% endfor %}
    </select></div>
    <div><label>Cantidad</label><input type="number" name="cantidad" min="0.01" step="0.01" required></div>
    <div><label>Unidad</label>
    <select name="unidad">{% for u in unidades %}<option>{{u}}</option>{% endfor %}</select></div>
    </div>
    <label>Observaciones</label>
    <textarea name="observacion"></textarea><br><br>
    <button>Guardar registro</button>
    <a class="btn sec" href="/">Cancelar</a>
    </form></div>
    """, hoy=date.today().isoformat(), materiales=MATERIALES, unidades=UNIDADES)

    return pagina(contenido)


# CONSULTAR REGISTROS
@app.route("/registros")
def registros():
    busqueda = request.args.get("q", "")
    with conectar() as db:
        datos = db.execute("""
        SELECT * FROM materiales
        WHERE material LIKE ? OR CAST(id AS TEXT) LIKE ?
        ORDER BY id DESC
        """, (f"%{busqueda}%", f"%{busqueda}%")).fetchall()

    contenido = render_template_string("""
    <h2>Consultar registros</h2>
    <div class="panel">
    <form method="GET">
    <input name="q" placeholder="Buscar material o número" value="{{busqueda}}">
    <br><br><button>Buscar</button>
    <a class="btn sec" href="/registros">Limpiar</a>
    </form></div>
    <div class="panel tabla">
    <table>
    <tr><th>ID</th><th>Fecha</th><th>Material</th><th>Cantidad</th><th>Unidad</th><th>Observación</th><th>Acciones</th></tr>
    {% for r in datos %}
    <tr>
    <td>{{r.id}}</td><td>{{r.fecha}}</td><td>{{r.material}}</td>
    <td>{{r.cantidad}}</td><td>{{r.unidad}}</td><td>{{r.observacion}}</td>
    <td>
    <a class="btn" href="/editar/{{r.id}}">Editar</a>
    <form method="POST" action="/eliminar/{{r.id}}" onsubmit="return confirm('¿Eliminar registro?')" style="display:inline">
    <button class="danger">Borrar</button></form>
    </td></tr>
    {% endfor %}
    </table>
    {% if not datos %}<p>No hay registros para mostrar.</p>{% endif %}
    </div>
    """, datos=datos, busqueda=busqueda)

    return pagina(contenido)


# MODIFICAR
@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    with conectar() as db:
        r = db.execute("SELECT * FROM materiales WHERE id=?", (id,)).fetchone()

    if not r:
        return "Registro no encontrado", 404

    if request.method == "POST":
        try:
            fecha = request.form["fecha"]
            datetime.strptime(fecha, "%Y-%m-%d")
            material = request.form["material"]
            cantidad = float(request.form["cantidad"].replace(",", "."))
            unidad = request.form["unidad"]
            observacion = request.form.get("observacion", "")

            if cantidad <= 0 or material not in MATERIALES or unidad not in UNIDADES:
                raise ValueError

            with conectar() as db:
                db.execute("""
                UPDATE materiales SET fecha=?,material=?,cantidad=?,unidad=?,observacion=?
                WHERE id=?
                """, (fecha, material, cantidad, unidad, observacion, id))

            flash("Registro modificado correctamente.")
            return redirect("/registros")
        except (ValueError, KeyError):
            flash("Los datos ingresados no son válidos.", "error")

    contenido = render_template_string("""
    <h2>Modificar registro N.º {{r.id}}</h2>
    <div class="panel"><form method="POST">
    <label>Fecha</label><input type="date" name="fecha" value="{{r.fecha}}" required>
    <label>Material</label><select name="material">
    {% for m in materiales %}<option {% if m==r.material %}selected{% endif %}>{{m}}</option>{% endfor %}
    </select>
    <label>Cantidad</label><input type="number" name="cantidad" min="0.01" step="0.01" value="{{r.cantidad}}" required>
    <label>Unidad</label><select name="unidad">
    {% for u in unidades %}<option {% if u==r.unidad %}selected{% endif %}>{{u}}</option>{% endfor %}
    </select>
    <label>Observación</label><textarea name="observacion">{{r.observacion}}</textarea><br><br>
    <button>Guardar cambios</button>
    <a class="btn sec" href="/registros">Cancelar</a>
    </form></div>
    """, r=r, materiales=MATERIALES, unidades=UNIDADES)

    return pagina(contenido)


# ELIMINAR
@app.route("/eliminar/<int:id>", methods=["POST"])
def eliminar(id):
    with conectar() as db:
        db.execute("DELETE FROM materiales WHERE id=?", (id,))
    flash("Registro eliminado correctamente.")
    return redirect("/registros")


# ESTADISTICAS AVANZADAS
@app.route("/estadisticas")
def estadisticas():

    colores = [
        "#198754", "#36a66b", "#83c99a",
        "#e6b94b", "#4b8fbd"
    ]

    with conectar() as db:

        total_registros = db.execute(
            "SELECT COUNT(*) FROM materiales"
        ).fetchone()[0]

        total_kg = db.execute("""
            SELECT COALESCE(SUM(cantidad),0)
            FROM materiales WHERE unidad='Kg'
        """).fetchone()[0]

        total_unidades = db.execute("""
            SELECT COALESCE(SUM(cantidad),0)
            FROM materiales WHERE unidad='Unidades'
        """).fetchone()[0]

        cantidad_materiales = db.execute("""
            SELECT COUNT(DISTINCT material)
            FROM materiales
        """).fetchone()[0]

        resumen = db.execute("""
            SELECT material, unidad,
                   SUM(cantidad) AS total,
                   COUNT(*) AS registros
            FROM materiales
            GROUP BY material, unidad
            ORDER BY material
        """).fetchall()

    # Preparar los gráficos sin mezclar Kg y unidades
    graficos = []

    for unidad in UNIDADES:

        datos = [
            {
                "material": r["material"],
                "total": float(r["total"]),
                "registros": r["registros"]
            }
            for r in resumen if r["unidad"] == unidad
        ]

        total = sum(r["total"] for r in datos)
        maximo = max([r["total"] for r in datos], default=1)

        # Crear gráfico circular
        segmentos = []
        acumulado = 0

        for i, dato in enumerate(datos):
            porcentaje = dato["total"] / total * 100 if total else 0
            inicio = acumulado
            acumulado += porcentaje

            dato["porcentaje"] = round(porcentaje, 1)
            dato["color"] = colores[i % len(colores)]
            dato["ancho"] = round(porcentaje, 1)

            segmentos.append(
                f'{dato["color"]} {inicio:.2f}% {acumulado:.2f}%'
            )

        gradiente = (
            "conic-gradient(" + ", ".join(segmentos) + ")"
            if segmentos else
            "conic-gradient(#e8eee9 0% 100%)"
        )

        graficos.append({
            "unidad": unidad,
            "datos": datos,
            "total": total,
            "maximo": maximo,
            "gradiente": gradiente
        })

    contenido = render_template_string("""
    <style>
    .estadisticas-titulo {
        display:flex;
        justify-content:space-between;
        align-items:center;
        flex-wrap:wrap;
        gap:12px;
        margin-bottom:25px;
    }

    .estadisticas-titulo p {
        color:#75847a;
        margin-top:5px;
    }

    .indicadores {
        display:grid;
        grid-template-columns:repeat(auto-fit,minmax(175px,1fr));
        gap:16px;
        margin-bottom:25px;
    }

    .indicador {
        background:white;
        padding:22px;
        border-radius:13px;
        border:1px solid #e5eee7;
        box-shadow:0 3px 12px #00000008;
    }

    .indicador .icono {
        font-size:25px;
        margin-bottom:12px;
    }

    .indicador small {
        color:#748278;
    }

    .indicador h2 {
        font-size:27px;
        margin:9px 0 0;
        color:#176b45;
    }

    .graficos {
        display:grid;
        grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
        gap:18px;
        margin-bottom:22px;
    }

    .grafico {
        background:white;
        padding:23px;
        border-radius:13px;
        border:1px solid #e5eee7;
        box-shadow:0 3px 12px #00000008;
    }

    .grafico h3 {
        margin-top:0;
        color:#24533a;
    }

    .donut-contenedor {
        display:flex;
        justify-content:center;
        align-items:center;
        margin:25px 0;
    }

    .donut {
        width:175px;
        height:175px;
        border-radius:50%;
        position:relative;
        display:flex;
        align-items:center;
        justify-content:center;
    }

    .donut:after {
        content:"";
        position:absolute;
        width:112px;
        height:112px;
        background:white;
        border-radius:50%;
    }

    .donut-centro {
        position:absolute;
        z-index:2;
        text-align:center;
        font-size:20px;
        font-weight:bold;
        color:#176b45;
    }

    .donut-centro small {
        display:block;
        font-size:11px;
        color:#77847b;
        font-weight:normal;
    }

    .leyenda {
        display:flex;
        justify-content:space-between;
        gap:10px;
        padding:8px 0;
        border-bottom:1px solid #edf1ed;
        font-size:13px;
    }

    .punto {
        display:inline-block;
        width:10px;
        height:10px;
        border-radius:50%;
        margin-right:7px;
    }

    .barra-item {
        margin:17px 0;
    }

    .barra-info {
        display:flex;
        justify-content:space-between;
        font-size:13px;
        margin-bottom:7px;
    }

    .barra-fondo {
        height:12px;
        border-radius:20px;
        background:#edf2ee;
        overflow:hidden;
    }

    .barra-progreso {
        height:100%;
        border-radius:20px;
    }

    .nota {
        background:#edf6ef;
        border-radius:9px;
        padding:13px;
        color:#315b3f;
        font-size:12px;
        margin-top:16px;
    }
    </style>

    <div class="estadisticas-titulo">
      <div>
        <h2>Panel de estadísticas</h2>
        <p>Análisis general de los materiales reciclables recibidos.</p>
      </div>
      <a href="/registros" class="btn">Ver registros</a>
    </div>

    <div class="indicadores">

      <div class="indicador">
        <div class="icono">📋</div>
        <small>Total de registros</small>
        <h2>{{ total_registros }}</h2>
      </div>

      <div class="indicador">
        <div class="icono">⚖️</div>
        <small>Peso total recibido</small>
        <h2>{{ "%.2f"|format(total_kg) }} kg</h2>
      </div>

      <div class="indicador">
        <div class="icono">♻️</div>
        <small>Unidades recibidas</small>
        <h2>{{ "%.2f"|format(total_unidades) }}</h2>
      </div>

      <div class="indicador">
        <div class="icono">🌱</div>
        <small>Tipos de materiales</small>
        <h2>{{ cantidad_materiales }}</h2>
      </div>

    </div>

    <div class="graficos">

    {% for g in graficos %}

      <div class="grafico">
        <h3>Distribución por material</h3>
        <p style="color:#75847a;font-size:13px">
          Cantidades expresadas en {{ g.unidad }}
        </p>

        <div class="donut-contenedor">
          <div class="donut"
               style="background:{{ g.gradiente }}">
            <div class="donut-centro">
              {{ "%.2f"|format(g.total) }}
              <small>{{ g.unidad }}</small>
            </div>
          </div>
        </div>

        {% if g.datos %}
          {% for d in g.datos %}
          <div class="leyenda">
            <span>
              <span class="punto"
                style="background:{{ d.color }}"></span>
              {{ d.material }}
            </span>
            <strong>{{ d.porcentaje }}%</strong>
          </div>
          {% endfor %}
        {% else %}
          <p style="text-align:center;color:#75847a">
            No hay datos disponibles.
          </p>
        {% endif %}

      </div>

    {% endfor %}

    </div>

    <div class="grafico">
      <h3>Comparación de cantidades por material</h3>
      <p style="color:#75847a;font-size:13px">
        Los gráficos se separan por unidad para evitar comparar
        kilogramos con unidades individuales.
      </p>

      {% for g in graficos %}

        <h4 style="color:#176b45;margin-top:25px">
          {{ g.unidad }}
        </h4>

        {% if g.datos %}
          {% for d in g.datos %}
          <div class="barra-item">

            <div class="barra-info">
              <span>{{ d.material }}</span>
              <strong>{{ "%.2f"|format(d.total) }} {{ g.unidad }}</strong>
            </div>

            <div class="barra-fondo">
              <div class="barra-progreso"
                style="width:{{ d.total/g.maximo*100 }}%;
                       background:{{ d.color }}">
              </div>
            </div>

          </div>
          {% endfor %}
        {% else %}
          <p style="color:#75847a">Sin registros de esta unidad.</p>
        {% endif %}

      {% endfor %}

    </div>

    <div class="nota">
      <strong>Información del sistema:</strong>
      Los indicadores se calculan automáticamente utilizando
      los registros almacenados en la base de datos SQLite.
    </div>

    <br>
    <a href="/exportar" class="btn">⇩ Exportar información</a>
    <a href="/respaldo" class="btn sec">Crear copia de seguridad</a>

    """,
    total_registros=total_registros,
    total_kg=total_kg,
    total_unidades=total_unidades,
    cantidad_materiales=cantidad_materiales,
    graficos=graficos
    )

    return pagina(contenido)


# EXPORTAR CSV
@app.route("/exportar")
def exportar():
    with conectar() as db:
        datos = db.execute("SELECT * FROM materiales ORDER BY id").fetchall()

    salida = StringIO()
    escritor = csv.writer(salida, delimiter=";")
    escritor.writerow(["ID", "Fecha", "Material", "Cantidad", "Unidad", "Observación"])

    for r in datos:
        escritor.writerow([r["id"], r["fecha"], r["material"], r["cantidad"], r["unidad"], r["observacion"]])

    return Response(
        "\ufeff" + salida.getvalue(),
        content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=reciclaje.csv"}
    )


# COPIA DE SEGURIDAD
@app.route("/respaldo")
def respaldo():
    RESPALDOS.mkdir(exist_ok=True)
    nombre = "respaldo_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".db"
    destino = RESPALDOS / nombre

    with conectar() as origen:
        with sqlite3.connect(destino) as copia:
            origen.backup(copia)

    flash("Copia de seguridad creada correctamente: " + nombre)
    return redirect("/")


# EJECUCION
if __name__ == "__main__":
    iniciar_bd()
    print("EcoGestión iniciado")
    print("Abrir http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
