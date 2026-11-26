# -*- coding: utf-8 -*-
"""Reloj del sistema.

Toda la aplicación obtiene la fecha y hora actual a través de este módulo. Así las
pruebas y la carga de datos de demostración pueden fijar la hora sin tocar la lógica.
"""
from datetime import datetime

_fijada = None


def ahora() -> datetime:
    return _fijada or datetime.now().replace(microsecond=0)


def fijar(momento):
    """Fija la hora devuelta por ahora(); con None vuelve al reloj real."""
    global _fijada
    _fijada = momento
