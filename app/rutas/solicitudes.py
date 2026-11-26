# -*- coding: utf-8 -*-
"""Módulos de registro, asignación, atención y seguimiento de solicitudes (RF04 a RF09)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..dominio.estados import ASIGNAR, NOMBRE_ACCION, RESOLVER, TransicionInvalida
from ..models import (ESTADOS, ESTUDIANTE, FUNCIONARIO, NOMBRE_ESTADO, PRIORIDADES, Categoria, Rol,
                      Solicitud, Usuario)
from ..seguridad import rol_requerido
from ..servicios import solicitudes as servicio
from ..servicios.solicitudes import AccesoDenegado, ReglaNegocioError

bp = Blueprint("solicitudes", __name__, url_prefix="/solicitudes")


@bp.route("/")
@login_required
def lista():
    q = servicio.visibles_para(current_user)
    f = {k: request.args.get(k, "").strip() for k in ("estado", "categoria", "prioridad", "q")}
    if f["estado"] in ESTADOS:
        q = q.filter(Solicitud.estado == f["estado"])
    if f["categoria"].isdigit():
        q = q.filter(Solicitud.categoria_id == int(f["categoria"]))
    if f["prioridad"] in PRIORIDADES:
        q = q.filter(Solicitud.prioridad == f["prioridad"])
    if f["q"]:
        q = q.filter(Solicitud.codigo.ilike(f"%{f['q']}%") | Solicitud.asunto.ilike(f"%{f['q']}%"))
    solicitudes = q.order_by(Solicitud.fecha_registro.desc()).all()
    titulo = {ESTUDIANTE: "Mis solicitudes", FUNCIONARIO: "Solicitudes asignadas"}.get(
        current_user.rol.nombre, "Todas las solicitudes")
    return render_template("solicitudes/lista.html", solicitudes=solicitudes, f=f, titulo=titulo,
                           categorias=Categoria.query.order_by(Categoria.nombre).all(),
                           estados=[(e, NOMBRE_ESTADO[e]) for e in ESTADOS], prioridades=PRIORIDADES)


@bp.route("/nueva", methods=["GET", "POST"])
@rol_requerido(ESTUDIANTE)
def nueva():
    categorias = Categoria.query.filter_by(activa=True).order_by(Categoria.nombre).all()
    datos = {}
    if request.method == "POST":
        datos = {k: request.form.get(k, "") for k in ("categoria_id", "asunto", "descripcion", "prioridad")}
        try:
            s = servicio.registrar(current_user, **datos)
            flash(f"Solicitud {s.codigo} registrada. Puede seguir su estado en «Mis solicitudes».", "ok")
            return redirect(url_for("solicitudes.detalle", sid=s.id))
        except ReglaNegocioError as e:
            flash(str(e), "error")
    return render_template("solicitudes/nueva.html", categorias=categorias, prioridades=PRIORIDADES,
                           datos=datos), (400 if request.method == "POST" else 200)


def _cargar(sid):
    try:
        return servicio.obtener_visible(current_user, sid)
    except AccesoDenegado:
        abort(404)  # no se revela si la solicitud existe


@bp.route("/<int:sid>")
@login_required
def detalle(sid):
    s = _cargar(sid)
    funcionarios = (Usuario.query.join(Rol).filter(Rol.nombre == FUNCIONARIO, Usuario.activo.is_(True))
                    .order_by(Usuario.nombre).all())
    return render_template("solicitudes/detalle.html", s=s, acciones=servicio.acciones_disponibles(s, current_user),
                           puede_observar=servicio.puede_observar(s, current_user), funcionarios=funcionarios,
                           NOMBRE_ACCION=NOMBRE_ACCION, ASIGNAR=ASIGNAR, RESOLVER=RESOLVER)


@bp.route("/<int:sid>/accion", methods=["POST"])
@login_required
def accion(sid):
    s = _cargar(sid)
    nombre = request.form.get("accion", "")
    motivo = request.form.get("motivo", "")
    try:
        if nombre == ASIGNAR:
            servicio.asignar(s, current_user, request.form.get("responsable_id"), motivo)
        elif nombre == RESOLVER:
            servicio.resolver(s, current_user, request.form.get("solucion", ""))
        elif nombre in servicio.ACCIONES:
            servicio.ACCIONES[nombre](s, current_user, motivo)
        else:
            abort(400)
        flash(f"Solicitud {s.codigo}: ahora está en estado {s.nombre_estado}.", "ok")
    except (AccesoDenegado, ReglaNegocioError, TransicionInvalida) as e:
        servicio.db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("solicitudes.detalle", sid=sid))


@bp.route("/<int:sid>/observar", methods=["POST"])
@login_required
def observar(sid):
    s = _cargar(sid)
    try:
        servicio.observar(s, current_user, request.form.get("texto", ""))
        flash("Observación registrada.", "ok")
    except (ReglaNegocioError, AccesoDenegado) as e:
        servicio.db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("solicitudes.detalle", sid=sid) + "#observaciones")
