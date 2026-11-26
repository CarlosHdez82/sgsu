# -*- coding: utf-8 -*-
"""Parámetros generales del sistema (los gestiona el administrador)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import ADMINISTRADOR, Parametro
from ..seguridad import rol_requerido

bp = Blueprint("parametros", __name__, url_prefix="/parametros")

NUMERICOS = {"tiempo_respuesta_defecto_horas": (1, 720), "longitud_minima_descripcion": (5, 500)}


@bp.route("/", methods=["GET", "POST"])
@rol_requerido(ADMINISTRADOR)
def editar():
    parametros = Parametro.query.order_by(Parametro.clave).all()
    if request.method == "POST":
        errores = []
        for p in parametros:
            valor = request.form.get(p.clave, "").strip()
            if p.clave in NUMERICOS:
                lo, hi = NUMERICOS[p.clave]
                if not valor.isdigit() or not lo <= int(valor) <= hi:
                    errores.append(f"«{p.descripcion}» debe ser un número entre {lo} y {hi}.")
                    continue
            elif not valor:
                errores.append(f"«{p.descripcion}» es obligatorio.")
                continue
            p.valor = valor
        if errores:
            db.session.rollback()
            for e in errores:
                flash(e, "error")
        else:
            db.session.commit()
            flash("Parámetros actualizados.", "ok")
            return redirect(url_for("parametros.editar"))
    return render_template("parametros.html", parametros=parametros)
