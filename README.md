# SGSU – Sistema de Gestión de Solicitudes Universitarias

Proyecto final de **Ingeniería del Software** (Corporación Universitaria Latinoamericana, docente Kevin Villarreal Jiménez).

Integrantes: Carlos Alberto Hernández Castro · Camila Andrea Cáceres Reyes · Jaime Alberto Arrieta Chamorro.

SGSU centraliza las solicitudes de servicios que estudiantes y funcionarios hacían por correo, mensajería y atención presencial: registro, asignación de responsables, atención, seguimiento con historial, notificaciones internas y reportes con indicadores de tiempos de respuesta.

## Funcionalidades

| Módulo | Qué hace | Rol |
|---|---|---|
| Autenticación | Inicio y cierre de sesión, control de acceso por rol | Todos |
| Gestión de usuarios | Registro, consulta, edición, activación y asignación de roles | Administrador |
| Gestión de categorías | Tipos de solicitud con su tiempo de respuesta | Administrador |
| Parámetros | Institución, tiempo de respuesta por defecto, longitud mínima de la descripción | Administrador |
| Registro de solicitudes | Categoría, asunto, descripción y prioridad; código y fecha límite automáticos | Estudiante |
| Asignación y atención | Asignar o reasignar, iniciar, resolver con solución, rechazar, cerrar y reabrir | Supervisor, administrador, funcionario |
| Seguimiento e historial | Línea de tiempo con fecha, usuario, estado anterior y nuevo, y motivo | Todos (según permisos) |
| Notificaciones | Avisos internos al registrar, asignar, cambiar de estado u observar (correo opcional) | Todos |
| Reportes | Conteos por estado, categoría, prioridad y responsable; filtros por periodo; exportación CSV | Supervisor, administrador |

Ciclo de vida: `REGISTRADA → ASIGNADA → EN PROCESO → RESUELTA → CERRADA`, más `RECHAZADA` (final) y `REABIERTA`.

## Tecnologías

- **Python 3.12 o superior** (probado con 3.14) y **Flask 3.1**: framework web ligero, de curva de aprendizaje corta y estructura modular con *blueprints*.
- **SQLite** con **SQLAlchemy** (ORM, *Object-Relational Mapping*): base de datos relacional sin servidor; cambiar a PostgreSQL o MySQL solo requiere la variable `SGSU_DATABASE_URL`.
- **Flask-Login**: manejo de sesiones; contraseñas cifradas con *hash* (scrypt) de Werkzeug.
- **Jinja2** y **CSS** propio: interfaz que funciona sin conexión a internet.
- **pytest**, **pytest-cov** y **radon**: pruebas automáticas, cobertura y métricas de código.

## Instalación

```bash
git clone https://github.com/CarlosHdez82/sgsu.git
cd sgsu
python -m venv .venv
# Windows: .venv\Scripts\activate    ·    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
flask --app run.py init-db          # crea la base con datos de demostración (--sin-demo para vacía)
python run.py                       # http://127.0.0.1:5000
```

Variables opcionales: `SGSU_SECRET_KEY` (clave de sesión; obligatoria en producción), `SGSU_DATABASE_URL`, `SGSU_CORREO=1` (activa el notificador de correo), `PORT`.

## Usuarios de demostración

Todos usan la contraseña de prueba `Sgsu2026` (solo para la base de demostración).

| Rol | Correo |
|---|---|
| Administrador | admin@sgsu.edu.co |
| Supervisor | supervisor@sgsu.edu.co |
| Funcionario | andres.torres@sgsu.edu.co, jorge.castillo@sgsu.edu.co, diana.ospina@sgsu.edu.co, paola.mejia@sgsu.edu.co |
| Estudiante | valentina.ruiz@sgsu.edu.co, santiago.herrera@sgsu.edu.co, daniela.fuentes@sgsu.edu.co, camilo.pardo@sgsu.edu.co, sebastian.royero@sgsu.edu.co |

## Manual breve de uso

1. **Estudiante**: *Nueva solicitud* → elija categoría, escriba asunto y descripción, indique la prioridad y registre. En *Mis solicitudes* consulta el estado, el historial y las observaciones. Cuando la solicitud está *Resuelta* puede **cerrarla** (conforme) o **reabrirla** con un motivo.
2. **Supervisor**: recibe un aviso por cada solicitud nueva. En el detalle usa *Asignar / reasignar responsable*. Puede rechazar con motivo, reabrir solicitudes cerradas y consultar *Reportes*.
3. **Funcionario**: en *Solicitudes asignadas* abre el caso, pulsa *Iniciar atención*, agrega observaciones y lo marca como *Resuelta* escribiendo la solución aplicada.
4. **Administrador**: gestiona *Usuarios y roles*, *Categorías* y *Parámetros*; también puede asignar y consultar reportes.

## Pruebas y métricas

```bash
pytest                                # 99 pruebas: unitarias, de integración y funcionales
pytest --cov --cov-report=term        # cobertura (94 %)
radon cc app -s -a                    # complejidad ciclomática (promedio A ≈ 3,2)
radon mi app -s                       # índice de mantenibilidad
```

## Estructura

```
app/
  __init__.py          fábrica de la aplicación, configuración, CSRF y comandos
  models.py            entidades y tablas (Rol, Usuario, Categoria, Solicitud, HistorialEstado,
                       Observacion, Notificacion, Parametro)
  dominio/estados.py   ciclo de vida con el patrón Estado
  servicios/           reglas de negocio (solicitudes), notificaciones con el patrón Observador, reportes
  rutas/               controladores web por módulo (blueprints)
  templates/, static/  vistas Jinja2 y estilos
  seguridad.py         decorador de control de acceso por rol
  semilla.py           datos iniciales y de demostración
tests/                 pruebas automáticas
```

Arquitectura en capas (presentación → servicios → dominio → persistencia) sobre el patrón MVC (Modelo-Vista-Controlador). Patrones de diseño: **Estado**, **Observador**, **Fábrica de aplicación** y **Capa de servicio**.
