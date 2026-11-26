# -*- coding: utf-8 -*-
"""Pruebas de integración del servicio de solicitudes: reglas de negocio RN01 a RN09."""
from datetime import datetime

import pytest

from app import reloj
from app.models import HistorialEstado, Notificacion, Solicitud
from app.servicios import solicitudes as srv
from app.servicios.solicitudes import AccesoDenegado, ReglaNegocioError
from app.dominio.estados import TransicionInvalida

DESC = "Necesito un certificado de estudio para un trámite."


def nueva(u, cat, prioridad="MEDIA"):
    return srv.registrar(u.est, cat.id, "Certificado de estudio", DESC, prioridad)


def hasta_resuelta(u, cat):
    s = nueva(u, cat)
    srv.asignar(s, u.sup, u.fun.id)
    srv.iniciar(s, u.fun)
    srv.resolver(s, u.fun, "Se expidió el certificado solicitado.")
    return s


# RN01 – solo usuarios autenticados (y con rol estudiante) registran
def test_registro_exige_usuario_autenticado(app, cat):
    with pytest.raises(AccesoDenegado):
        srv.registrar(None, cat.id, "Asunto válido", DESC, "MEDIA")


def test_solo_estudiante_registra(app, u, cat):
    with pytest.raises(AccesoDenegado):
        srv.registrar(u.fun, cat.id, "Asunto válido", DESC, "MEDIA")


# RN02 – toda solicitud asociada a una categoría (activa)
@pytest.mark.parametrize("categoria", [None, "", "999", "abc"])
def test_registro_exige_categoria_existente(app, u, categoria):
    with pytest.raises(ReglaNegocioError, match="categoría"):
        srv.registrar(u.est, categoria, "Asunto válido", DESC, "MEDIA")


def test_categoria_inactiva_no_admite_solicitudes(app, u):
    from app.models import Categoria
    antigua = Categoria.query.filter_by(nombre="Antigua").one()
    with pytest.raises(ReglaNegocioError, match="categoría"):
        srv.registrar(u.est, antigua.id, "Asunto válido", DESC, "MEDIA")


# RN03 – estado inicial Registrada, código consecutivo, fecha límite según la categoría
def test_estado_inicial_y_datos_calculados(app, u, cat):
    reloj.fijar(datetime(2026, 11, 2, 8, 0))
    s1, s2 = nueva(u, cat), nueva(u, cat)
    assert s1.estado == "REGISTRADA"
    assert (s1.codigo, s2.codigo) == ("SOL-2026-0001", "SOL-2026-0002")
    assert s1.fecha_limite == datetime(2026, 11, 4, 8, 0)  # 48 h
    assert s1.historial[0].estado_anterior is None and s1.historial[0].estado_nuevo == "REGISTRADA"


# RN09 – validación de datos obligatorios
@pytest.mark.parametrize("asunto,desc,prio", [("", DESC, "MEDIA"), ("Asunto válido", "corta", "MEDIA"),
                                              ("Asunto válido", DESC, "MAXIMA")])
def test_validacion_de_datos_obligatorios(app, u, cat, asunto, desc, prio):
    with pytest.raises(ReglaNegocioError):
        srv.registrar(u.est, cat.id, asunto, desc, prio)
    assert Solicitud.query.count() == 0


# RN04 – solo un usuario autorizado asigna o reasigna
@pytest.mark.parametrize("quien", ["est", "fun"])
def test_no_autorizados_no_asignan(app, u, cat, quien):
    s = nueva(u, cat)
    with pytest.raises(AccesoDenegado):
        srv.asignar(s, getattr(u, quien), u.fun.id)


def test_supervisor_y_administrador_asignan_y_reasignan(app, u, cat):
    s = nueva(u, cat)
    srv.asignar(s, u.sup, u.fun.id)
    assert s.estado == "ASIGNADA" and s.responsable_id == u.fun.id
    srv.asignar(s, u.admin, u.fun2.id, "Carga de trabajo")
    assert s.responsable_id == u.fun2.id
    assert s.historial[-1].motivo == "Carga de trabajo"


@pytest.mark.parametrize("responsable", ["est", "inactivo", "sup"])
def test_responsable_debe_ser_funcionario_activo(app, u, cat, responsable):
    s = nueva(u, cat)
    with pytest.raises(ReglaNegocioError):
        srv.asignar(s, u.sup, getattr(u, responsable).id)


def test_solo_el_responsable_inicia_y_resuelve(app, u, cat):
    s = nueva(u, cat)
    srv.asignar(s, u.sup, u.fun.id)
    with pytest.raises(AccesoDenegado):
        srv.iniciar(s, u.fun2)
    srv.iniciar(s, u.fun)
    with pytest.raises(AccesoDenegado):
        srv.resolver(s, u.sup, "Solución escrita por otra persona")


# RN05 – para resolver se exige la solución
@pytest.mark.parametrize("solucion", ["", "   ", "corta"])
def test_resolver_exige_solucion(app, u, cat, solucion):
    s = nueva(u, cat)
    srv.asignar(s, u.sup, u.fun.id)
    srv.iniciar(s, u.fun)
    with pytest.raises(ReglaNegocioError, match="solución"):
        srv.resolver(s, u.fun, solucion)
    assert s.estado == "EN_PROCESO"


def test_resolver_guarda_solucion_como_observacion(app, u, cat):
    s = hasta_resuelta(u, cat)
    assert s.estado == "RESUELTA" and s.solucion
    assert s.observaciones[-1].es_solucion


def test_no_se_puede_saltar_estados(app, u, cat):
    s = nueva(u, cat)
    with pytest.raises(TransicionInvalida):
        srv.cerrar(s, u.sup)
    srv.asignar(s, u.sup, u.fun.id)
    with pytest.raises(TransicionInvalida):
        srv.resolver(s, u.fun, "Solución directa sin iniciar")


# RN06 – una solicitud cerrada no se modifica, salvo reapertura autorizada
def test_cerrada_no_admite_observaciones(app, u, cat):
    s = hasta_resuelta(u, cat)
    srv.cerrar(s, u.est)
    assert s.estado == "CERRADA" and s.fecha_cierre is not None
    with pytest.raises(ReglaNegocioError):
        srv.observar(s, u.sup, "Intento de modificar")


def test_solo_gestor_reabre_una_cerrada(app, u, cat):
    s = hasta_resuelta(u, cat)
    srv.cerrar(s, u.est)
    with pytest.raises(AccesoDenegado):
        srv.reabrir(s, u.est, "Quiero reabrirla")
    with pytest.raises(ReglaNegocioError, match="motivo"):
        srv.reabrir(s, u.sup, "")
    srv.reabrir(s, u.sup, "Seguimiento pendiente")
    assert s.estado == "REABIERTA" and s.fecha_cierre is None


def test_solicitante_puede_reabrir_desde_resuelta(app, u, cat):
    s = hasta_resuelta(u, cat)
    srv.reabrir(s, u.est, "La solución no funcionó")
    assert s.estado == "REABIERTA" and s.solucion is None
    srv.iniciar(s, u.fun)
    assert s.estado == "EN_PROCESO"


def test_rechazo_exige_motivo_y_es_final(app, u, cat):
    s = nueva(u, cat)
    with pytest.raises(ReglaNegocioError):
        srv.rechazar(s, u.sup, "")
    srv.rechazar(s, u.sup, "No corresponde a esta dependencia")
    assert s.estado == "RECHAZADA"
    with pytest.raises(TransicionInvalida):
        srv.reabrir(s, u.sup, "Intento de reabrir")


# RN07 – cada cambio de estado guarda fecha, usuario y motivo
def test_historial_completo(app, u, cat):
    s = hasta_resuelta(u, cat)
    srv.cerrar(s, u.est)
    pasos = [(h.estado_anterior, h.estado_nuevo) for h in s.historial]
    assert pasos == [(None, "REGISTRADA"), ("REGISTRADA", "ASIGNADA"), ("ASIGNADA", "EN_PROCESO"),
                     ("EN_PROCESO", "RESUELTA"), ("RESUELTA", "CERRADA")]
    for h in HistorialEstado.query.all():
        assert h.fecha and h.usuario_id and h.motivo


# RN08 – el estudiante solo consulta sus propias solicitudes
def test_estudiante_solo_ve_las_suyas(app, u, cat):
    propia = nueva(u, cat)
    ajena = srv.registrar(u.est2, cat.id, "Solicitud de otro", DESC, "BAJA")
    assert srv.visibles_para(u.est).all() == [propia]
    with pytest.raises(AccesoDenegado):
        srv.obtener_visible(u.est, ajena.id)


def test_funcionario_solo_ve_asignadas(app, u, cat):
    s = nueva(u, cat)
    assert srv.visibles_para(u.fun).count() == 0
    srv.asignar(s, u.sup, u.fun.id)
    assert srv.visibles_para(u.fun).all() == [s]
    assert srv.visibles_para(u.fun2).count() == 0


# Notificaciones (patrón Observador)
def test_notificaciones_por_evento(app, u, cat):
    s = nueva(u, cat)
    assert {n.usuario_id for n in Notificacion.query.all()} == {u.sup.id, u.admin.id}
    srv.asignar(s, u.sup, u.fun.id)
    avisos = Notificacion.query.filter(Notificacion.mensaje.like("%asignada%")).all()
    assert {n.usuario_id for n in avisos} == {u.est.id, u.fun.id}
    srv.iniciar(s, u.fun)
    assert Notificacion.query.filter_by(usuario_id=u.est.id).filter(
        Notificacion.mensaje.like("%En proceso%")).count() == 1
    assert Notificacion.query.filter_by(usuario_id=u.fun.id).filter(
        Notificacion.mensaje.like("%En proceso%")).count() == 0  # el actor no se notifica a sí mismo


def test_notificador_correo_opcional(app, u, cat):
    from app.servicios import eventos
    correo = eventos.NotificadorCorreo()
    eventos.publicador.suscribir(correo)
    try:
        nueva(u, cat)
    finally:
        eventos.publicador.desuscribir(correo)
    assert {c[0] for c in correo.enviados} == {"sup@t.co", "admin@sgsu.edu.co"}


def test_vencimiento(app, u, cat):
    reloj.fijar(datetime(2026, 11, 1, 8, 0))
    s = nueva(u, cat)
    reloj.fijar(datetime(2026, 11, 3, 9, 0))
    assert s.vencida
    srv.asignar(s, u.sup, u.fun.id)
    srv.iniciar(s, u.fun)
    srv.resolver(s, u.fun, "Atendida fuera de tiempo")
    assert not s.vencida
