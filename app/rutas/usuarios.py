# -*- coding: utf-8 -*-
"""Módulo de gestión de usuarios y roles (RF02). Solo para el administrador."""
import re

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db
from ..models import ADMINISTRADOR, Rol, Usuario
from ..seguridad import rol_requerido

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


def validar_clave(clave):
    """Política de contraseñas: mínimo 8 caracteres, con letras y números."""
    return len(clave) >= 8 and re.search(r"[A-Za-z]", clave) and re.search(r"\d", clave)


def validar_usuario(datos, rol, activo, u):
    """Valida el formulario de usuario y devuelve la lista de errores (vacía si todo está bien)."""
    errores = []
    if not datos["documento"].isdigit() or not 5 <= len(datos["documento"]) <= 15:
        errores.append("El documento debe tener entre 5 y 15 dígitos.")
    if len(datos["nombre"]) < 3:
        errores.append("El nombre es obligatorio.")
    if not PATRON_CORREO.match(datos["correo"]):
        errores.append("El correo no es válido.")
    if rol is None:
        errores.append("Debe seleccionar un rol.")
    if (u is None or datos["clave"]) and not validar_clave(datos["clave"]):
        errores.append("La contraseña debe tener mínimo 8 caracteres e incluir letras y números.")
    if _duplicado(datos, u):
        errores.append("Ya existe un usuario con ese correo o documento.")
    if u and u.id == current_user.id and (not activo or (rol and rol.nombre != ADMINISTRADOR)):
        errores.append("No puede desactivar su propia cuenta ni quitarse el rol de administrador.")
    return errores


def _duplicado(datos, u):
    q = Usuario.query.filter(db.or_(Usuario.correo == datos["correo"], Usuario.documento == datos["documento"]))
    if u:
        q = q.filter(Usuario.id != u.id)
    return q.first() is not None


@bp.route("/")
@rol_requerido(ADMINISTRADOR)
def lista():
    q = Usuario.query.join(Rol)
    texto = request.args.get("q", "").strip()
    rol = request.args.get("rol", "")
    if texto:
        q = q.filter(db.or_(Usuario.nombre.ilike(f"%{texto}%"), Usuario.correo.ilike(f"%{texto}%"),
                            Usuario.documento.ilike(f"%{texto}%")))
    if rol:
        q = q.filter(Rol.nombre == rol)
    return render_template("usuarios/lista.html", usuarios=q.order_by(Usuario.nombre).all(),
                           roles=Rol.query.order_by(Rol.nombre).all(), texto=texto, rol=rol)


@bp.route("/nuevo", methods=["GET", "POST"])
@bp.route("/<int:uid>/editar", methods=["GET", "POST"])
@rol_requerido(ADMINISTRADOR)
def formulario(uid=None):
    u = db.session.get(Usuario, uid) if uid else None
    if uid and u is None:
        abort(404)
    roles = Rol.query.order_by(Rol.nombre).all()
    if request.method == "POST":
        f = request.form
        datos = {k: f.get(k, "").strip() for k in ("documento", "nombre", "correo", "dependencia", "clave")}
        datos["correo"] = datos["correo"].lower()
        rol_id = f.get("rol_id", "")
        rol = db.session.get(Rol, int(rol_id)) if rol_id.isdigit() else None
        activo = f.get("activo") == "on"
        errores = validar_usuario(datos, rol, activo, u)
        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("usuarios/form.html", u=u, roles=roles, datos=datos, activo=activo,
                                   rol_id=rol.id if rol else None), 400
        if u is None:
            u = Usuario()
            db.session.add(u)
        u.documento, u.nombre, u.correo = datos["documento"], datos["nombre"], datos["correo"]
        u.dependencia, u.rol, u.activo = datos["dependencia"], rol, activo
        if datos["clave"]:
            u.establecer_password(datos["clave"])
        db.session.commit()
        flash(f"Usuario «{u.nombre}» guardado.", "ok")
        return redirect(url_for("usuarios.lista"))
    datos = {"documento": u.documento, "nombre": u.nombre, "correo": u.correo,
             "dependencia": u.dependencia} if u else {}
    return render_template("usuarios/form.html", u=u, roles=roles, datos=datos,
                           activo=u.activo if u else True, rol_id=u.rol_id if u else None)
