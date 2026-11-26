# -*- coding: utf-8 -*-
"""Ciclo de vida de una solicitud con el patrón de diseño Estado (State).

Cada estado es una clase que sabe qué acciones acepta y a qué estado lleva cada una.
Si una acción no está permitida en el estado actual, se lanza TransicionInvalida.
Agregar un estado nuevo solo exige crear otra subclase y registrarla en FABRICA.
"""
from ..models import (ASIGNADA, CERRADA, EN_PROCESO, NOMBRE_ESTADO, REABIERTA, RECHAZADA,
                      REGISTRADA, RESUELTA)

# Acciones del ciclo de vida
ASIGNAR, INICIAR, RESOLVER, CERRAR, RECHAZAR, REABRIR = (
    "asignar", "iniciar", "resolver", "cerrar", "rechazar", "reabrir")

NOMBRE_ACCION = {
    ASIGNAR: "Asignar / reasignar responsable", INICIAR: "Iniciar atención", RESOLVER: "Marcar como resuelta",
    CERRAR: "Cerrar solicitud", RECHAZAR: "Rechazar solicitud", REABRIR: "Reabrir solicitud",
}


class TransicionInvalida(Exception):
    """La acción pedida no es válida en el estado actual de la solicitud."""


class EstadoSolicitud:
    """Estado abstracto. Las subclases definen `nombre`, `transiciones` y si se puede modificar."""
    nombre = None
    transiciones: dict = {}
    permite_modificacion = True
    es_final = False

    def acciones(self):
        return list(self.transiciones)

    def acepta(self, accion) -> bool:
        return accion in self.transiciones

    def siguiente(self, accion) -> str:
        if accion not in self.transiciones:
            raise TransicionInvalida(
                f"No se puede «{NOMBRE_ACCION.get(accion, accion)}» una solicitud en estado "
                f"{NOMBRE_ESTADO[self.nombre]}.")
        return self.transiciones[accion]


class Registrada(EstadoSolicitud):
    nombre = REGISTRADA
    transiciones = {ASIGNAR: ASIGNADA, RECHAZAR: RECHAZADA}


class Asignada(EstadoSolicitud):
    nombre = ASIGNADA
    transiciones = {ASIGNAR: ASIGNADA, INICIAR: EN_PROCESO, RECHAZAR: RECHAZADA}


class EnProceso(EstadoSolicitud):
    nombre = EN_PROCESO
    transiciones = {RESOLVER: RESUELTA, ASIGNAR: ASIGNADA}


class Resuelta(EstadoSolicitud):
    nombre = RESUELTA
    transiciones = {CERRAR: CERRADA, REABRIR: REABIERTA}


class Cerrada(EstadoSolicitud):
    """Una solicitud cerrada no admite cambios, salvo una reapertura autorizada."""
    nombre = CERRADA
    transiciones = {REABRIR: REABIERTA}
    permite_modificacion = False
    es_final = True


class Rechazada(EstadoSolicitud):
    nombre = RECHAZADA
    transiciones = {}
    permite_modificacion = False
    es_final = True


class Reabierta(EstadoSolicitud):
    nombre = REABIERTA
    transiciones = {INICIAR: EN_PROCESO, ASIGNAR: ASIGNADA}


FABRICA = {c.nombre: c() for c in (Registrada, Asignada, EnProceso, Resuelta, Cerrada, Rechazada, Reabierta)}


def estado_de(nombre: str) -> EstadoSolicitud:
    """Devuelve el objeto Estado que corresponde al nombre guardado en la base de datos."""
    return FABRICA[nombre]
