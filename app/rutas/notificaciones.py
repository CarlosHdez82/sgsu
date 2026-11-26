# -*- coding: utf-8 -*-
"""Bandeja de notificaciones internas (RF10)."""
from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Notificacion

bp = Blueprint("notificaciones", __name__, url_prefix="/notificaciones")


@bp.route("/")
@login_required
def lista():
    avisos = (Notificacion.query.filter_by(usuario_id=current_user.id)
              .order_by(Notificacion.fecha.desc(), Notificacion.id.desc()).limit(100).all())
    return render_template("notificaciones.html", avisos=avisos)


@bp.route("/<int:nid>/abrir", methods=["POST"])
@login_required
def abrir(nid):
    n = db.session.get(Notificacion, nid)
    if n is None or n.usuario_id != current_user.id:
        abort(404)
    n.marcar_leida()
    db.session.commit()
    if n.solicitud_id:
        return redirect(url_for("solicitudes.detalle", sid=n.solicitud_id))
    return redirect(url_for("notificaciones.lista"))


@bp.route("/leer-todas", methods=["POST"])
@login_required
def leer_todas():
    Notificacion.query.filter_by(usuario_id=current_user.id, leida=False).update({"leida": True})
    db.session.commit()
    return redirect(url_for("notificaciones.lista"))
