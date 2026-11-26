# -*- coding: utf-8 -*-
"""Configuración común de las pruebas: base de datos SQLite en memoria con datos mínimos."""
import pytest

from app import create_app, reloj
from app.extensions import db
from app.models import ADMINISTRADOR, ESTUDIANTE, FUNCIONARIO, SUPERVISOR, Categoria, Rol, Usuario
from app.semilla import cargar_basicos

CLAVE = "Prueba2026"


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "CSRF_ACTIVO": False,
                      "SECRET_KEY": "pruebas"})
    with app.app_context():
        db.create_all()
        cargar_basicos()
        _crear_datos()
        yield app
        db.session.remove()
        db.drop_all()
    reloj.fijar(None)


def _usuario(correo, rol, nombre=None, activo=True):
    u = Usuario(documento=str(abs(hash(correo)) % 10**10).zfill(10), nombre=nombre or correo.split("@")[0],
                correo=correo, rol=Rol.query.filter_by(nombre=rol).one(), activo=activo)
    u.establecer_password(CLAVE)
    db.session.add(u)
    return u


def _crear_datos():
    _usuario("sup@t.co", SUPERVISOR, "Supervisora")
    _usuario("fun@t.co", FUNCIONARIO, "Funcionario Uno")
    _usuario("fun2@t.co", FUNCIONARIO, "Funcionario Dos")
    _usuario("est@t.co", ESTUDIANTE, "Estudiante Uno")
    _usuario("est2@t.co", ESTUDIANTE, "Estudiante Dos")
    _usuario("inactivo@t.co", FUNCIONARIO, "Inactivo", activo=False)
    db.session.add(Categoria(nombre="Certificados", descripcion="", tiempo_respuesta_horas=48))
    db.session.add(Categoria(nombre="Antigua", descripcion="", tiempo_respuesta_horas=24, activa=False))
    db.session.commit()


@pytest.fixture
def u():
    """Acceso rápido a los usuarios por nombre corto."""
    def buscar(correo):
        return Usuario.query.filter_by(correo=correo).one()
    return type("U", (), {
        "admin": property(lambda s: buscar("admin@sgsu.edu.co")), "sup": property(lambda s: buscar("sup@t.co")),
        "fun": property(lambda s: buscar("fun@t.co")), "fun2": property(lambda s: buscar("fun2@t.co")),
        "est": property(lambda s: buscar("est@t.co")), "est2": property(lambda s: buscar("est2@t.co")),
        "inactivo": property(lambda s: buscar("inactivo@t.co")),
    })()


@pytest.fixture
def cat():
    return Categoria.query.filter_by(nombre="Certificados").one()


@pytest.fixture
def cliente(app):
    return app.test_client()


@pytest.fixture
def login(cliente):
    def entrar(correo, clave=CLAVE):
        cliente.post("/logout")
        return cliente.post("/login", data={"correo": correo, "clave": clave}, follow_redirects=True)
    return entrar
