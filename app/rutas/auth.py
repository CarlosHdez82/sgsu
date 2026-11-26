# -*- coding: utf-8 -*-
"""Módulo de autenticación (RF01): inicio y cierre de sesión."""
from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..models import Usuario

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("principal.inicio"))
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        clave = request.form.get("clave", "")
        u = Usuario.query.filter_by(correo=correo).first()
        if u is None or not u.verificar_password(clave):
            flash("Correo o contraseña incorrectos.", "error")  # mensaje genérico: no revela qué dato falló
        elif not u.activo:
            flash("Su cuenta está inactiva. Comuníquese con el administrador.", "error")
        else:
            session.clear()
            login_user(u)
            destino = request.args.get("next", "")
            # evita redirecciones abiertas a otros sitios: solo rutas internas
            if not destino.startswith("/") or destino.startswith("//") or urlparse(destino).netloc:
                destino = url_for("principal.inicio")
            return redirect(destino)
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    flash("Sesión cerrada.", "ok")
    return redirect(url_for("auth.login"))
