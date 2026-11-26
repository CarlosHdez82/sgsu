# -*- coding: utf-8 -*-
"""Página de inicio (tablero) adaptada al rol del usuario."""
from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..models import (ADMINISTRADOR, ESTADOS, FUNCIONARIO, NOMBRE_ESTADO, Categoria, Solicitud,
                      Usuario)
from ..servicios import reportes
from ..servicios.solicitudes import visibles_para

bp = Blueprint("principal", __name__)


@bp.route("/")
def raiz():
    return redirect(url_for("principal.inicio") if current_user.is_authenticated else url_for("auth.login"))


@bp.route("/inicio")
@login_required
def inicio():
    q = visibles_para(current_user)
    conteo = {e: q.filter(Solicitud.estado == e).count() for e in ESTADOS}
    recientes = q.order_by(Solicitud.fecha_actualizacion.desc()).limit(6).all()
    datos = {"conteo": [(NOMBRE_ESTADO[e], e, conteo[e]) for e in ESTADOS], "recientes": recientes,
             "total": sum(conteo.values())}
    if current_user.tiene_rol(FUNCIONARIO):
        datos["vencidas"] = [s for s in q.all() if s.vencida]
    if current_user.tiene_rol(ADMINISTRADOR):
        datos["n_usuarios"] = Usuario.query.count()
        datos["n_categorias"] = Categoria.query.filter_by(activa=True).count()
    if not current_user.tiene_rol(FUNCIONARIO, "ESTUDIANTE"):
        r = reportes.resumen()
        datos["indicadores"] = {k: r[k] for k in ("abiertas", "vencidas", "promedio_horas", "cumplimiento")}
    return render_template("inicio.html", **datos)
