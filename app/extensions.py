# -*- coding: utf-8 -*-
"""Instancias compartidas de las extensiones de Flask (se inicializan en create_app)."""
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Inicie sesión para continuar."
login_manager.login_message_category = "aviso"
