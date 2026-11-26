# -*- coding: utf-8 -*-
"""Reportes y estadísticas para el supervisor (RF11)."""
from datetime import datetime, time

from sqlalchemy import func

from ..extensions import db
from ..models import (CERRADA, ESTADOS, NOMBRE_ESTADO, PRIORIDADES, RECHAZADA, RESUELTA, Categoria,
                      HistorialEstado, Solicitud, Usuario)


def _filtrar(q, desde=None, hasta=None, categoria_id=None, prioridad=None, responsable_id=None, estado=None):
    if desde:
        q = q.filter(Solicitud.fecha_registro >= datetime.combine(desde, time.min))
    if hasta:
        q = q.filter(Solicitud.fecha_registro <= datetime.combine(hasta, time.max))
    if categoria_id:
        q = q.filter(Solicitud.categoria_id == categoria_id)
    if prioridad:
        q = q.filter(Solicitud.prioridad == prioridad)
    if responsable_id:
        q = q.filter(Solicitud.responsable_id == responsable_id)
    if estado:
        q = q.filter(Solicitud.estado == estado)
    return q


def solicitudes_filtradas(**filtros):
    return _filtrar(Solicitud.query, **filtros).order_by(Solicitud.fecha_registro.desc()).all()


def _conteo(columna, **filtros):
    q = _filtrar(db.session.query(columna, func.count(Solicitud.id)), **filtros).group_by(columna)
    return dict(q.all())


def resumen(**filtros):
    """Devuelve totales e indicadores para el periodo y filtros indicados."""
    lista = solicitudes_filtradas(**filtros)
    total = len(lista)

    por_estado = _conteo(Solicitud.estado, **filtros)
    por_prioridad = _conteo(Solicitud.prioridad, **filtros)
    por_categoria_id = _conteo(Solicitud.categoria_id, **filtros)
    por_responsable_id = _conteo(Solicitud.responsable_id, **filtros)

    categorias = {c.id: c.nombre for c in Categoria.query.all()}
    usuarios = {u.id: u.nombre for u in Usuario.query.all()}

    # tiempo de resolución: desde el registro hasta el primer paso a Resuelta
    pares = list(_pares_resueltas(lista))
    horas = [h for _, h in pares]
    finalizadas = sum(1 for s in lista if s.estado in (RESUELTA, CERRADA, RECHAZADA))
    abiertas = total - finalizadas
    vencidas = sum(1 for s in lista if s.vencida)
    a_tiempo = sum(1 for s, h in pares if h <= s.categoria.tiempo_respuesta_horas)
    resueltas = len(horas)

    return {
        "total": total,
        "abiertas": abiertas,
        "finalizadas": finalizadas,
        "vencidas": vencidas,
        "promedio_horas": round(sum(horas) / resueltas, 1) if resueltas else None,
        "cumplimiento": round(100 * a_tiempo / resueltas, 1) if resueltas else None,
        "por_estado": [(NOMBRE_ESTADO[e], por_estado.get(e, 0)) for e in ESTADOS],
        "por_prioridad": [(p.capitalize(), por_prioridad.get(p, 0)) for p in PRIORIDADES],
        "por_categoria": sorted(((categorias[k], v) for k, v in por_categoria_id.items()), key=lambda x: -x[1]),
        "por_responsable": sorted(((usuarios.get(k, "Sin asignar") if k else "Sin asignar", v)
                                   for k, v in por_responsable_id.items()), key=lambda x: -x[1]),
        "lista": lista,
    }


def _pares_resueltas(lista):
    for s in lista:
        h = (HistorialEstado.query.filter_by(solicitud_id=s.id, estado_nuevo=RESUELTA)
             .order_by(HistorialEstado.fecha).first())
        if h:
            yield s, (h.fecha - s.fecha_registro).total_seconds() / 3600
