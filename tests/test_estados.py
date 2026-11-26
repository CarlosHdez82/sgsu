# -*- coding: utf-8 -*-
"""Pruebas unitarias del ciclo de vida (patrón Estado), sin base de datos."""
import pytest

from app.dominio.estados import (ASIGNAR, CERRAR, INICIAR, REABRIR, RECHAZAR, RESOLVER, TransicionInvalida,
                                 estado_de)
from app.models import ESTADOS

VALIDAS = [
    ("REGISTRADA", ASIGNAR, "ASIGNADA"), ("REGISTRADA", RECHAZAR, "RECHAZADA"),
    ("ASIGNADA", ASIGNAR, "ASIGNADA"), ("ASIGNADA", INICIAR, "EN_PROCESO"), ("ASIGNADA", RECHAZAR, "RECHAZADA"),
    ("EN_PROCESO", RESOLVER, "RESUELTA"), ("EN_PROCESO", ASIGNAR, "ASIGNADA"),
    ("RESUELTA", CERRAR, "CERRADA"), ("RESUELTA", REABRIR, "REABIERTA"),
    ("CERRADA", REABRIR, "REABIERTA"),
    ("REABIERTA", INICIAR, "EN_PROCESO"), ("REABIERTA", ASIGNAR, "ASIGNADA"),
]
TODAS = (ASIGNAR, INICIAR, RESOLVER, CERRAR, RECHAZAR, REABRIR)


@pytest.mark.parametrize("origen,accion,destino", VALIDAS)
def test_transiciones_validas(origen, accion, destino):
    assert estado_de(origen).siguiente(accion) == destino


INVALIDAS = [(e, a) for e in ESTADOS for a in TODAS if (e, a) not in {(o, ac) for o, ac, _ in VALIDAS}]


@pytest.mark.parametrize("origen,accion", INVALIDAS)
def test_transiciones_invalidas_se_rechazan(origen, accion):
    with pytest.raises(TransicionInvalida):
        estado_de(origen).siguiente(accion)


def test_cerrada_y_rechazada_no_permiten_modificacion():
    assert not estado_de("CERRADA").permite_modificacion
    assert not estado_de("RECHAZADA").permite_modificacion
    assert estado_de("RECHAZADA").acciones() == []


def test_todos_los_estados_tienen_clase():
    assert {estado_de(e).nombre for e in ESTADOS} == set(ESTADOS)
