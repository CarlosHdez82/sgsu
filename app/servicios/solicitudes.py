# -*- coding: utf-8 -*-
"""Servicio de solicitudes: aplica las reglas de negocio del ciclo de vida.

Las vistas (rutas web) nunca cambian el estado directamente: siempre llaman a este
servicio, que valida datos y permisos, consulta al objeto Estado si la transición es
válida, guarda el historial y publica el evento para las notificaciones.
"""
from ..dominio.estados import (ASIGNAR, CERRAR, INICIAR, REABRIR, RECHAZAR, RESOLVER,
                               TransicionInvalida, estado_de)
from ..extensions import db
from ..models import (ADMINISTRADOR, CERRADA, ESTUDIANTE, FUNCIONARIO, PRIORIDADES, REGISTRADA,
                      RESUELTA, SUPERVISOR, Categoria, HistorialEstado, Observacion, Parametro,
                      Solicitud, Usuario)
from .. import reloj
from . import eventos

GESTORES = (ADMINISTRADOR, SUPERVISOR)  # usuarios autorizados para asignar y reabrir solicitudes cerradas


class ReglaNegocioError(Exception):
    """Se viola una regla de negocio o un dato obligatorio no es válido."""


class AccesoDenegado(Exception):
    """El usuario no tiene permiso para la operación."""


# ------------------------------------------------------------------ consultas
def visibles_para(usuario):
    """Consulta base con las solicitudes que el usuario puede ver."""
    q = Solicitud.query
    if usuario.tiene_rol(ESTUDIANTE):
        return q.filter(Solicitud.solicitante_id == usuario.id)  # solo sus propias solicitudes
    if usuario.tiene_rol(FUNCIONARIO):
        return q.filter(Solicitud.responsable_id == usuario.id)
    return q  # administrador y supervisor ven todas


def obtener_visible(usuario, solicitud_id) -> Solicitud:
    s = visibles_para(usuario).filter(Solicitud.id == solicitud_id).first()
    if s is None:
        raise AccesoDenegado("La solicitud no existe o no tiene permiso para consultarla.")
    return s


def acciones_disponibles(solicitud, usuario):
    """Acciones del ciclo de vida que este usuario puede ejecutar ahora sobre la solicitud."""
    estado = estado_de(solicitud.estado)
    return [a for a in estado.acciones() if _autorizado(a, solicitud, usuario)]


def puede_observar(solicitud, usuario) -> bool:
    if not estado_de(solicitud.estado).permite_modificacion:
        return False
    return (usuario.tiene_rol(*GESTORES) or usuario.id in (solicitud.solicitante_id, solicitud.responsable_id))


# ------------------------------------------------------------------ comandos
def siguiente_codigo() -> str:
    anio = reloj.ahora().year
    prefijo = f"SOL-{anio}-"
    ultimo = (db.session.query(Solicitud.codigo).filter(Solicitud.codigo.like(prefijo + "%"))
              .order_by(Solicitud.codigo.desc()).first())
    n = int(ultimo[0].split("-")[-1]) + 1 if ultimo else 1
    return f"{prefijo}{n:04d}"


def registrar(usuario, categoria_id, asunto, descripcion, prioridad) -> Solicitud:
    if usuario is None or not usuario.is_authenticated:
        raise AccesoDenegado("Solo un usuario autenticado puede registrar solicitudes.")
    if not usuario.tiene_rol(ESTUDIANTE):
        raise AccesoDenegado("Solo los estudiantes registran solicitudes.")
    asunto = (asunto or "").strip()
    descripcion = (descripcion or "").strip()
    errores = []
    categoria = db.session.get(Categoria, int(categoria_id)) if str(categoria_id or "").isdigit() else None
    if categoria is None or not categoria.activa:
        errores.append("Debe seleccionar una categoría activa.")
    if len(asunto) < 5:
        errores.append("El asunto debe tener al menos 5 caracteres.")
    minimo = Parametro.entero("longitud_minima_descripcion", 20)
    if len(descripcion) < minimo:
        errores.append(f"La descripción debe tener al menos {minimo} caracteres.")
    if prioridad not in PRIORIDADES:
        errores.append("La prioridad no es válida.")
    if errores:
        raise ReglaNegocioError(" ".join(errores))

    s = Solicitud(codigo=siguiente_codigo(), fecha_registro=reloj.ahora(), solicitante=usuario,
                  categoria=categoria, asunto=asunto, descripcion=descripcion, prioridad=prioridad,
                  estado=REGISTRADA, fecha_actualizacion=reloj.ahora())
    s.calcular_fecha_limite(categoria.tiempo_respuesta_horas
                            or Parametro.entero("tiempo_respuesta_defecto_horas", 72))
    db.session.add(s)
    db.session.flush()
    _historial(s, usuario, None, REGISTRADA, "Registro de la solicitud")
    eventos.publicador.publicar(eventos.SOLICITUD_REGISTRADA, s, usuario)
    db.session.commit()
    return s


def asignar(solicitud, usuario, responsable_id, motivo="") -> Solicitud:
    _verificar(ASIGNAR, solicitud, usuario)
    responsable = db.session.get(Usuario, int(responsable_id)) if str(responsable_id or "").isdigit() else None
    if responsable is None or not responsable.activo or not responsable.tiene_rol(FUNCIONARIO):
        raise ReglaNegocioError("El responsable debe ser un funcionario activo.")
    if responsable.id == solicitud.responsable_id and solicitud.estado in ("ASIGNADA", "EN_PROCESO"):
        raise ReglaNegocioError("La solicitud ya está asignada a ese funcionario.")
    reasignacion = solicitud.responsable_id is not None
    texto = motivo.strip() or ("Reasignación de responsable" if reasignacion else "Asignación de responsable")
    solicitud.responsable = responsable
    _cambiar(solicitud, usuario, ASIGNAR, texto)
    eventos.publicador.publicar(eventos.SOLICITUD_ASIGNADA, solicitud, usuario)
    db.session.commit()
    return solicitud


def iniciar(solicitud, usuario, motivo="") -> Solicitud:
    return _transicion_simple(solicitud, usuario, INICIAR, motivo.strip() or "Inicio de la atención")


def resolver(solicitud, usuario, solucion) -> Solicitud:
    _verificar(RESOLVER, solicitud, usuario)
    solucion = (solucion or "").strip()
    if len(solucion) < 10:
        raise ReglaNegocioError("Para marcar la solicitud como resuelta debe registrar la solución aplicada "
                                "(mínimo 10 caracteres).")
    solicitud.solucion = solucion
    db.session.add(Observacion(solicitud=solicitud, autor=usuario, texto=solucion, es_solucion=True,
                               fecha=reloj.ahora()))
    _cambiar(solicitud, usuario, RESOLVER, "Solución registrada")
    db.session.commit()
    return solicitud


def cerrar(solicitud, usuario, motivo="") -> Solicitud:
    return _transicion_simple(solicitud, usuario, CERRAR, motivo.strip() or "Cierre: solicitante conforme")


def rechazar(solicitud, usuario, motivo) -> Solicitud:
    return _transicion_con_motivo(solicitud, usuario, RECHAZAR, motivo)


def reabrir(solicitud, usuario, motivo) -> Solicitud:
    return _transicion_con_motivo(solicitud, usuario, REABRIR, motivo)


def observar(solicitud, usuario, texto) -> Observacion:
    texto = (texto or "").strip()
    if not estado_de(solicitud.estado).permite_modificacion:
        raise ReglaNegocioError(f"Una solicitud {solicitud.nombre_estado.lower()} no puede modificarse.")
    if not puede_observar(solicitud, usuario):
        raise AccesoDenegado("No tiene permiso para registrar observaciones en esta solicitud.")
    if len(texto) < 3:
        raise ReglaNegocioError("La observación no puede estar vacía.")
    o = Observacion(solicitud=solicitud, autor=usuario, texto=texto, fecha=reloj.ahora())
    db.session.add(o)
    solicitud.fecha_actualizacion = reloj.ahora()
    db.session.flush()
    eventos.publicador.publicar(eventos.OBSERVACION_AGREGADA, solicitud, usuario)
    db.session.commit()
    return o


ACCIONES = {INICIAR: iniciar, CERRAR: cerrar, RECHAZAR: rechazar, REABRIR: reabrir}


# ------------------------------------------------------------------ apoyo interno
def _autorizado(accion, s, u) -> bool:
    """Política de permisos por acción (control de acceso según rol y relación con la solicitud)."""
    es_gestor = u.tiene_rol(*GESTORES)
    es_responsable = s.responsable_id is not None and u.id == s.responsable_id
    es_solicitante = u.id == s.solicitante_id
    if accion == ASIGNAR:
        return es_gestor
    if accion in (INICIAR, RESOLVER):
        return es_responsable
    if accion == RECHAZAR:
        return es_gestor or es_responsable
    if accion == CERRAR:
        return es_gestor or es_solicitante
    if accion == REABRIR:
        if s.estado == CERRADA:
            return es_gestor  # reapertura autorizada: solo administrador o supervisor
        return es_gestor or es_solicitante  # desde Resuelta: el solicitante no está conforme
    return False


def _verificar(accion, solicitud, usuario):
    estado_de(solicitud.estado).siguiente(accion)  # lanza TransicionInvalida si no aplica
    if not _autorizado(accion, solicitud, usuario):
        raise AccesoDenegado("No tiene permiso para realizar esta acción sobre la solicitud.")


def _historial(solicitud, usuario, anterior, nuevo, motivo):
    db.session.add(HistorialEstado(solicitud_id=solicitud.id, usuario_id=usuario.id, estado_anterior=anterior,
                                   estado_nuevo=nuevo, responsable_id=solicitud.responsable_id,
                                   motivo=motivo, fecha=reloj.ahora()))


def _cambiar(solicitud, usuario, accion, motivo):
    anterior = solicitud.estado
    nuevo = estado_de(anterior).siguiente(accion)
    solicitud.estado = nuevo
    solicitud.fecha_actualizacion = reloj.ahora()
    if nuevo == CERRADA:
        solicitud.fecha_cierre = reloj.ahora()
    elif anterior == CERRADA:
        solicitud.fecha_cierre = None
    if anterior == RESUELTA and nuevo != CERRADA:
        solicitud.solucion = None  # al reabrirse, la solución anterior deja de ser la vigente
    _historial(solicitud, usuario, anterior, nuevo, motivo)
    db.session.flush()
    if anterior != nuevo:
        eventos.publicador.publicar(eventos.ESTADO_CAMBIADO, solicitud, usuario, anterior=anterior, nuevo=nuevo)


def _transicion_simple(solicitud, usuario, accion, motivo):
    _verificar(accion, solicitud, usuario)
    _cambiar(solicitud, usuario, accion, motivo)
    db.session.commit()
    return solicitud


def _transicion_con_motivo(solicitud, usuario, accion, motivo):
    _verificar(accion, solicitud, usuario)
    motivo = (motivo or "").strip()
    if len(motivo) < 5:
        raise ReglaNegocioError("Debe indicar el motivo (mínimo 5 caracteres).")
    _cambiar(solicitud, usuario, accion, motivo)
    db.session.commit()
    return solicitud


__all__ = ["ReglaNegocioError", "AccesoDenegado", "TransicionInvalida", "registrar", "asignar", "iniciar",
           "resolver", "cerrar", "rechazar", "reabrir", "observar", "visibles_para", "obtener_visible",
           "acciones_disponibles", "puede_observar"]
