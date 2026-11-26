# -*- coding: utf-8 -*-
"""Pruebas funcionales a través de HTTP: autenticación, control de acceso por rol y módulos."""
import pytest

from app import create_app
from app.extensions import db
from app.models import Categoria, Notificacion, Parametro, Solicitud, Usuario
from tests.conftest import CLAVE

DESC = "Necesito un certificado de estudio para un trámite."


# ---------------------------------------------------------------- RF01 autenticación
def test_login_correcto_redirige_al_inicio(login):
    r = login("est@t.co")
    assert r.status_code == 200 and "Hola, Estudiante" in r.get_data(as_text=True)


@pytest.mark.parametrize("correo,clave", [("est@t.co", "mala"), ("nadie@t.co", CLAVE)])
def test_login_incorrecto_muestra_mensaje_generico(login, correo, clave):
    r = login(correo, clave)
    assert "Correo o contraseña incorrectos" in r.get_data(as_text=True)


def test_usuario_inactivo_no_ingresa(login):
    assert "inactiva" in login("inactivo@t.co").get_data(as_text=True)


def test_paginas_protegidas_exigen_sesion(cliente):
    for ruta in ("/inicio", "/solicitudes/", "/usuarios/", "/reportes/", "/notificaciones/"):
        r = cliente.get(ruta)
        assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_logout(cliente, login):
    login("est@t.co")
    cliente.post("/logout")
    assert cliente.get("/inicio").status_code == 302


def test_contrasenas_guardadas_con_hash(app):
    for usuario in Usuario.query.all():
        assert CLAVE not in usuario.password_hash and usuario.password_hash.startswith(("scrypt:", "pbkdf2:"))


def test_redireccion_abierta_bloqueada(cliente):
    r = cliente.post("/login?next=https://sitio-externo.com", data={"correo": "est@t.co", "clave": CLAVE})
    assert r.headers["Location"].endswith("/inicio")


def test_csrf_activo_rechaza_post_sin_token():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "CSRF_ACTIVO": True})
    with app.app_context():
        r = app.test_client().post("/login", data={"correo": "x@t.co", "clave": "y"})
        assert r.status_code == 400
        db.session.remove()
        db.engine.dispose()


# ---------------------------------------------------------------- control de acceso por rol
MATRIZ = [  # (ruta, roles con acceso)
    ("/usuarios/", {"admin"}), ("/categorias/", {"admin"}), ("/parametros/", {"admin"}),
    ("/reportes/", {"admin", "sup"}), ("/solicitudes/nueva", {"est"}),
    ("/solicitudes/", {"admin", "sup", "fun", "est"}), ("/notificaciones/", {"admin", "sup", "fun", "est"}),
]
CORREOS = {"admin": ("admin@sgsu.edu.co", "Sgsu2026"), "sup": ("sup@t.co", CLAVE), "fun": ("fun@t.co", CLAVE),
           "est": ("est@t.co", CLAVE)}


@pytest.fixture
def admin_con_clave(app):
    a = Usuario.query.filter_by(correo="admin@sgsu.edu.co").one()
    a.establecer_password("Sgsu2026")
    db.session.commit()


@pytest.mark.parametrize("rol", list(CORREOS))
def test_matriz_de_acceso_por_rol(cliente, login, admin_con_clave, rol):
    login(*CORREOS[rol])
    for ruta, permitidos in MATRIZ:
        esperado = 200 if rol in permitidos else 403
        assert cliente.get(ruta).status_code == esperado, (rol, ruta)


# ---------------------------------------------------------------- flujo completo por la web
def test_flujo_completo_por_http(cliente, login, u, cat):
    login("est@t.co")
    r = cliente.post("/solicitudes/nueva", data={"categoria_id": cat.id, "asunto": "Certificado de estudio",
                                                 "descripcion": DESC, "prioridad": "ALTA"}, follow_redirects=True)
    assert "registrada" in r.get_data(as_text=True)
    s = Solicitud.query.one()
    assert s.estado == "REGISTRADA" and s.solicitante_id == u.est.id

    login("sup@t.co")
    cliente.post(f"/solicitudes/{s.id}/accion", data={"accion": "asignar", "responsable_id": u.fun.id})
    assert db.session.get(Solicitud, s.id).estado == "ASIGNADA"

    login("fun@t.co")
    cliente.post(f"/solicitudes/{s.id}/accion", data={"accion": "iniciar"})
    cliente.post(f"/solicitudes/{s.id}/observar", data={"texto": "Revisando el caso"})
    r = cliente.post(f"/solicitudes/{s.id}/accion", data={"accion": "resolver", "solucion": ""},
                     follow_redirects=True)
    assert "debe registrar la solución" in r.get_data(as_text=True)
    cliente.post(f"/solicitudes/{s.id}/accion", data={"accion": "resolver",
                                                      "solucion": "Certificado enviado por correo."})
    assert db.session.get(Solicitud, s.id).estado == "RESUELTA"

    login("est@t.co")
    cliente.post(f"/solicitudes/{s.id}/accion", data={"accion": "cerrar"})
    s = db.session.get(Solicitud, s.id)
    assert s.estado == "CERRADA" and len(s.historial) == 5 and len(s.observaciones) == 2
    r = cliente.get(f"/solicitudes/{s.id}")
    assert "no admite modificaciones" in r.get_data(as_text=True)


def test_estudiante_no_ve_solicitud_ajena(cliente, login, u, cat):
    from app.servicios import solicitudes as srv
    ajena = srv.registrar(u.est2, cat.id, "Solicitud ajena", DESC, "MEDIA")
    login("est@t.co")
    assert cliente.get(f"/solicitudes/{ajena.id}").status_code == 404
    assert "Solicitud ajena" not in cliente.get("/solicitudes/").get_data(as_text=True)


def test_accion_no_autorizada_no_cambia_estado(cliente, login, u, cat):
    from app.servicios import solicitudes as srv
    s = srv.registrar(u.est, cat.id, "Certificado", DESC, "MEDIA")
    login("est@t.co")
    r = cliente.post(f"/solicitudes/{s.id}/accion", data={"accion": "asignar", "responsable_id": u.fun.id},
                     follow_redirects=True)
    assert "No tiene permiso" in r.get_data(as_text=True)
    assert db.session.get(Solicitud, s.id).estado == "REGISTRADA"


# ---------------------------------------------------------------- RF02 usuarios y RF03 categorías
def test_admin_crea_usuario_y_valida(cliente, login, admin_con_clave):
    login(*CORREOS["admin"])
    datos = {"documento": "123456789", "nombre": "Nuevo Usuario", "correo": "nuevo@t.co", "rol_id": "2",
             "dependencia": "Sistemas", "clave": "corta", "activo": "on"}
    assert cliente.post("/usuarios/nuevo", data=datos).status_code == 400
    datos["clave"] = "Segura2026"
    cliente.post("/usuarios/nuevo", data=datos)
    nuevo = Usuario.query.filter_by(correo="nuevo@t.co").one()
    assert nuevo.verificar_password("Segura2026")
    assert cliente.post("/usuarios/nuevo", data=datos).status_code == 400  # correo duplicado


def test_admin_no_puede_desactivarse(cliente, login, admin_con_clave, u):
    login(*CORREOS["admin"])
    a = u.admin
    r = cliente.post(f"/usuarios/{a.id}/editar", data={"documento": a.documento, "nombre": a.nombre,
                                                      "correo": a.correo, "rol_id": a.rol_id, "clave": ""})
    assert r.status_code == 400 and db.session.get(Usuario, a.id).activo


def test_admin_gestiona_categorias(cliente, login, admin_con_clave):
    login(*CORREOS["admin"])
    assert cliente.post("/categorias/nueva", data={"nombre": "Grados", "tiempo_respuesta_horas": "0"}).status_code == 400
    cliente.post("/categorias/nueva", data={"nombre": "Grados", "descripcion": "Trámites de grado",
                                            "tiempo_respuesta_horas": "96", "activa": "on"})
    assert Categoria.query.filter_by(nombre="Grados").one().tiempo_respuesta_horas == 96
    assert cliente.post("/categorias/nueva", data={"nombre": "grados", "tiempo_respuesta_horas": "5"}).status_code == 400


def test_parametros_validados(cliente, login, admin_con_clave):
    login(*CORREOS["admin"])
    base = {p.clave: p.valor for p in Parametro.query.all()}
    cliente.post("/parametros/", data={**base, "longitud_minima_descripcion": "abc"})
    assert Parametro.obtener("longitud_minima_descripcion") == "20"
    cliente.post("/parametros/", data={**base, "longitud_minima_descripcion": "30"})
    assert Parametro.obtener("longitud_minima_descripcion") == "30"


# ---------------------------------------------------------------- RF10 notificaciones y RF11 reportes
def test_bandeja_de_notificaciones(cliente, login, u, cat):
    from app.servicios import solicitudes as srv
    s = srv.registrar(u.est, cat.id, "Certificado", DESC, "MEDIA")
    login("sup@t.co")
    assert "Nueva solicitud" in cliente.get("/notificaciones/").get_data(as_text=True)
    n = Notificacion.query.filter_by(usuario_id=u.sup.id).one()
    r = cliente.post(f"/notificaciones/{n.id}/abrir")
    assert r.headers["Location"].endswith(f"/solicitudes/{s.id}") and db.session.get(Notificacion, n.id).leida
    login("est@t.co")
    assert cliente.post(f"/notificaciones/{n.id}/abrir").status_code == 404  # aviso de otro usuario


def test_reportes_y_exportacion(cliente, login, u, cat):
    from app.servicios import solicitudes as srv
    s = srv.registrar(u.est, cat.id, "Certificado", DESC, "ALTA")
    srv.asignar(s, u.sup, u.fun.id)
    srv.registrar(u.est2, cat.id, "Otra solicitud", DESC, "BAJA")
    login("sup@t.co")
    html = cliente.get("/reportes/?prioridad=ALTA").get_data(as_text=True)
    assert "Total en el periodo" in html and "Funcionario Uno" in html and "Detalle (1)" in html
    csv = cliente.get("/reportes/exportar.csv?estado=ASIGNADA").get_data(as_text=True)
    lineas = csv.strip().splitlines()
    assert len(lineas) == 2 and "Funcionario Uno" in lineas[1]
