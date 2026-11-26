# -*- coding: utf-8 -*-
"""Notificaciones con el patrón de diseño Observador (Observer).

El servicio de solicitudes publica eventos (registrada, asignada, cambio de estado,
observación) sin saber quién los escucha. Los suscriptores reaccionan: el notificador
interno guarda avisos en la base de datos y el notificador de correo (opcional) los
envía por correo electrónico. Se puede añadir otro canal sin modificar el servicio.
"""
import logging

from ..extensions import db
from ..models import ADMINISTRADOR, NOMBRE_ESTADO, SUPERVISOR, Notificacion, Rol, Usuario

log = logging.getLogger("sgsu.eventos")

SOLICITUD_REGISTRADA = "solicitud_registrada"
SOLICITUD_ASIGNADA = "solicitud_asignada"
ESTADO_CAMBIADO = "estado_cambiado"
OBSERVACION_AGREGADA = "observacion_agregada"


class PublicadorEventos:
    """Sujeto observado: mantiene la lista de suscriptores y les reenvía cada evento."""

    def __init__(self):
        self._suscriptores = []

    def suscribir(self, suscriptor):
        if suscriptor not in self._suscriptores:
            self._suscriptores.append(suscriptor)

    def desuscribir(self, suscriptor):
        if suscriptor in self._suscriptores:
            self._suscriptores.remove(suscriptor)

    def limpiar(self):
        self._suscriptores.clear()

    def publicar(self, evento, solicitud, actor, **datos):
        for s in list(self._suscriptores):
            s.actualizar(evento, solicitud, actor, **datos)


class Suscriptor:
    """Interfaz del observador."""

    def actualizar(self, evento, solicitud, actor, **datos):  # pragma: no cover - interfaz
        raise NotImplementedError


def destinatarios(evento, solicitud, actor):
    """Decide a quién se avisa de cada evento (nunca al propio actor)."""
    ids = set()
    if evento == SOLICITUD_REGISTRADA:
        roles = Rol.query.filter(Rol.nombre.in_([SUPERVISOR, ADMINISTRADOR])).all()
        ids |= {u.id for r in roles for u in r.usuarios if u.activo}
    else:
        ids.add(solicitud.solicitante_id)
        if solicitud.responsable_id:
            ids.add(solicitud.responsable_id)
    ids.discard(actor.id)
    return ids


def redactar(evento, solicitud, **datos):
    c = solicitud.codigo
    if evento == SOLICITUD_REGISTRADA:
        return f"Nueva solicitud {c} ({solicitud.categoria.nombre}, prioridad {solicitud.prioridad.lower()})."
    if evento == SOLICITUD_ASIGNADA:
        return f"La solicitud {c} fue asignada a {solicitud.responsable.nombre}."
    if evento == ESTADO_CAMBIADO:
        return (f"La solicitud {c} pasó de {NOMBRE_ESTADO[datos['anterior']]} "
                f"a {NOMBRE_ESTADO[datos['nuevo']]}.")
    if evento == OBSERVACION_AGREGADA:
        return f"Nueva observación en la solicitud {c}."
    return f"Actualización en la solicitud {c}."


class NotificadorInterno(Suscriptor):
    """Guarda un aviso en la bandeja interna de cada destinatario."""

    def actualizar(self, evento, solicitud, actor, **datos):
        mensaje = redactar(evento, solicitud, **datos)
        for uid in destinatarios(evento, solicitud, actor):
            db.session.add(Notificacion(usuario_id=uid, solicitud_id=solicitud.id, mensaje=mensaje))


class NotificadorCorreo(Suscriptor):
    """Canal opcional de correo. En esta versión deja constancia en el registro (log) de la aplicación;
    para enviar correos reales basta con implementar `enviar` con smtplib y configurar el servidor."""

    def __init__(self):
        self.enviados = []

    def enviar(self, correo, asunto, cuerpo):
        self.enviados.append((correo, asunto, cuerpo))
        log.info("Correo a %s: %s", correo, asunto)

    def actualizar(self, evento, solicitud, actor, **datos):
        mensaje = redactar(evento, solicitud, **datos)
        for uid in destinatarios(evento, solicitud, actor):
            u = db.session.get(Usuario, uid)
            self.enviar(u.correo, f"[SGSU] {solicitud.codigo}", mensaje)


publicador = PublicadorEventos()
