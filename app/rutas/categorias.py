# -*- coding: utf-8 -*-
"""Módulo de gestión de categorías de solicitudes (RF03). Solo para el administrador."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import ADMINISTRADOR, Categoria
from ..seguridad import rol_requerido

bp = Blueprint("categorias", __name__, url_prefix="/categorias")


@bp.route("/")
@rol_requerido(ADMINISTRADOR)
def lista():
    return render_template("categorias/lista.html", categorias=Categoria.query.order_by(Categoria.nombre).all())


@bp.route("/nueva", methods=["GET", "POST"])
@bp.route("/<int:cid>/editar", methods=["GET", "POST"])
@rol_requerido(ADMINISTRADOR)
def formulario(cid=None):
    c = db.session.get(Categoria, cid) if cid else None
    if cid and c is None:
        abort(404)
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        horas = request.form.get("tiempo_respuesta_horas", "").strip()
        activa = request.form.get("activa") == "on"
        errores = []
        if len(nombre) < 3:
            errores.append("El nombre debe tener al menos 3 caracteres.")
        if not horas.isdigit() or not 1 <= int(horas) <= 720:
            errores.append("El tiempo de respuesta debe estar entre 1 y 720 horas.")
        dup = Categoria.query.filter(db.func.lower(Categoria.nombre) == nombre.lower())
        if c:
            dup = dup.filter(Categoria.id != c.id)
        if dup.first():
            errores.append("Ya existe una categoría con ese nombre.")
        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("categorias/form.html", c=c, nombre=nombre, descripcion=descripcion,
                                   horas=horas, activa=activa), 400
        if c is None:
            c = Categoria()
            db.session.add(c)
        c.nombre, c.descripcion, c.tiempo_respuesta_horas, c.activa = nombre, descripcion, int(horas), activa
        db.session.commit()
        flash(f"Categoría «{c.nombre}» guardada.", "ok")
        return redirect(url_for("categorias.lista"))
    return render_template("categorias/form.html", c=c, nombre=c.nombre if c else "",
                           descripcion=c.descripcion if c else "",
                           horas=c.tiempo_respuesta_horas if c else 72, activa=c.activa if c else True)
