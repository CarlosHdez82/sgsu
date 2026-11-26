# -*- coding: utf-8 -*-
"""Módulo de reportes y estadísticas (RF11): supervisor y administrador."""
import csv
import io
from datetime import date

from flask import Blueprint, Response, render_template, request

from ..models import (ADMINISTRADOR, ESTADOS, FUNCIONARIO, NOMBRE_ESTADO, PRIORIDADES, SUPERVISOR,
                      Categoria, Rol, Usuario)
from ..seguridad import rol_requerido
from ..servicios import reportes

bp = Blueprint("reportes", __name__, url_prefix="/reportes")


def _filtros():
    a = request.args

    def fecha(k):
        try:
            return date.fromisoformat(a.get(k, ""))
        except ValueError:
            return None

    def entero(k):
        return int(a[k]) if a.get(k, "").isdigit() else None

    return {"desde": fecha("desde"), "hasta": fecha("hasta"), "categoria_id": entero("categoria"),
            "responsable_id": entero("responsable"),
            "prioridad": a.get("prioridad") if a.get("prioridad") in PRIORIDADES else None,
            "estado": a.get("estado") if a.get("estado") in ESTADOS else None}


@bp.route("/")
@rol_requerido(SUPERVISOR, ADMINISTRADOR)
def index():
    f = _filtros()
    r = reportes.resumen(**f)
    funcionarios = Usuario.query.join(Rol).filter(Rol.nombre == FUNCIONARIO).order_by(Usuario.nombre).all()
    return render_template("reportes.html", r=r, f=f, args=request.args,
                           categorias=Categoria.query.order_by(Categoria.nombre).all(), funcionarios=funcionarios,
                           estados=[(e, NOMBRE_ESTADO[e]) for e in ESTADOS], prioridades=PRIORIDADES)


@bp.route("/exportar.csv")
@rol_requerido(SUPERVISOR, ADMINISTRADOR)
def exportar():
    lista = reportes.solicitudes_filtradas(**_filtros())
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Código", "Fecha de registro", "Solicitante", "Categoría", "Asunto", "Prioridad", "Estado",
                "Responsable", "Fecha límite", "Vencida", "Fecha de cierre"])
    for s in lista:
        w.writerow([s.codigo, s.fecha_registro.strftime("%Y-%m-%d %H:%M"), s.solicitante.nombre, s.categoria.nombre,
                    s.asunto, s.prioridad, s.nombre_estado, s.responsable.nombre if s.responsable else "",
                    s.fecha_limite.strftime("%Y-%m-%d %H:%M"), "Sí" if s.vencida else "No",
                    s.fecha_cierre.strftime("%Y-%m-%d %H:%M") if s.fecha_cierre else ""])
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=reporte_solicitudes.csv"})
