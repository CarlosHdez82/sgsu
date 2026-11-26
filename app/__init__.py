# -*- coding: utf-8 -*-
"""SGSU – Sistema de Gestión de Solicitudes Universitarias.

Fábrica de la aplicación (patrón Application Factory): crea y configura la aplicación Flask,
registra extensiones, módulos (blueprints), protección CSRF (Cross-Site Request Forgery,
falsificación de petición en sitios cruzados) y comandos de consola.
"""
import logging
import os
import secrets

import click
from flask import Flask, abort, render_template, request, session

from .extensions import db, login_manager

BASE = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    SECRET_KEY = os.environ.get("SGSU_SECRET_KEY") or "cambie-esta-clave-en-produccion"
    SQLALCHEMY_DATABASE_URI = os.environ.get("SGSU_DATABASE_URL") or \
        "sqlite:///" + os.path.join(BASE, "instance", "sgsu.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # 8 horas
    CSRF_ACTIVO = True
    CORREO_ACTIVO = os.environ.get("SGSU_CORREO", "0") == "1"


def create_app(config=None):
    app = Flask(__name__, instance_path=os.path.join(BASE, "instance"))
    app.config.from_object(Config)
    if config:
        app.config.update(config)
    os.makedirs(app.instance_path, exist_ok=True)
    logging.basicConfig(level=logging.INFO)

    db.init_app(app)
    login_manager.init_app(app)

    from . import models  # noqa: F401  (registra las tablas)
    from .servicios import eventos

    eventos.publicador.limpiar()
    eventos.publicador.suscribir(eventos.NotificadorInterno())
    if app.config["CORREO_ACTIVO"]:
        eventos.publicador.suscribir(eventos.NotificadorCorreo())

    @login_manager.user_loader
    def cargar_usuario(uid):
        return db.session.get(models.Usuario, int(uid))

    # ---------------- protección CSRF sencilla basada en un token de sesión
    @app.before_request
    def verificar_csrf():
        if request.method == "POST" and app.config.get("CSRF_ACTIVO", True):
            enviado = request.form.get("csrf_token", "")
            if not enviado or enviado != session.get("csrf_token"):
                abort(400, description="Token de seguridad inválido. Recargue la página e intente de nuevo.")

    def token_csrf():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        return session["csrf_token"]

    @app.context_processor
    def contexto():
        return {"csrf_token": token_csrf, "M": models,
                "institucion": models.Parametro.obtener("nombre_institucion", "Institución universitaria")}

    @app.template_filter("fecha")
    def fmt_fecha(valor, con_hora=True):
        if not valor:
            return "—"
        return valor.strftime("%d/%m/%Y %H:%M" if con_hora else "%d/%m/%Y")

    # ---------------- módulos
    from .rutas.auth import bp as auth_bp
    from .rutas.principal import bp as principal_bp
    from .rutas.usuarios import bp as usuarios_bp
    from .rutas.categorias import bp as categorias_bp
    from .rutas.solicitudes import bp as solicitudes_bp
    from .rutas.reportes import bp as reportes_bp
    from .rutas.notificaciones import bp as notificaciones_bp
    from .rutas.parametros import bp as parametros_bp
    for bp in (auth_bp, principal_bp, usuarios_bp, categorias_bp, solicitudes_bp, reportes_bp,
               notificaciones_bp, parametros_bp):
        app.register_blueprint(bp)

    for codigo in (400, 403, 404):
        app.register_error_handler(codigo, lambda e, c=codigo: (render_template("error.html", error=e, codigo=c), c))

    # ---------------- comandos de consola
    @app.cli.command("init-db")
    @click.option("--demo/--sin-demo", default=True, help="Cargar datos de demostración.")
    def init_db(demo):
        """Crea la base de datos (borra la existente) y carga datos iniciales."""
        from .semilla import cargar_basicos, cargar_demo
        db.drop_all()
        db.create_all()
        cargar_basicos()
        if demo:
            cargar_demo()
        click.echo("Base de datos creada" + (" con datos de demostración." if demo else "."))

    with app.app_context():
        db.create_all()

    return app
