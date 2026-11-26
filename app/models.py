# -*- coding: utf-8 -*-
"""Modelo de dominio y de persistencia (ORM, Object-Relational Mapping, con SQLAlchemy).

Clases principales: Rol, Usuario, Categoria, Solicitud, HistorialEstado, Observacion,
Notificacion y Parametro. Cada una corresponde a una tabla de la base de datos relacional.
"""
from datetime import timedelta

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import reloj
from .extensions import db

# ---------------------------------------------------------------- constantes
ADMINISTRADOR, ESTUDIANTE, FUNCIONARIO, SUPERVISOR = "ADMINISTRADOR", "ESTUDIANTE", "FUNCIONARIO", "SUPERVISOR"
ROLES = (ADMINISTRADOR, ESTUDIANTE, FUNCIONARIO, SUPERVISOR)

PRIORIDADES = ("BAJA", "MEDIA", "ALTA", "URGENTE")

REGISTRADA, ASIGNADA, EN_PROCESO, RESUELTA = "REGISTRADA", "ASIGNADA", "EN_PROCESO", "RESUELTA"
CERRADA, RECHAZADA, REABIERTA = "CERRADA", "RECHAZADA", "REABIERTA"
ESTADOS = (REGISTRADA, ASIGNADA, EN_PROCESO, RESUELTA, CERRADA, RECHAZADA, REABIERTA)

NOMBRE_ESTADO = {
    REGISTRADA: "Registrada", ASIGNADA: "Asignada", EN_PROCESO: "En proceso", RESUELTA: "Resuelta",
    CERRADA: "Cerrada", RECHAZADA: "Rechazada", REABIERTA: "Reabierta",
}


class Rol(db.Model):
    __tablename__ = "rol"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(20), unique=True, nullable=False)
    descripcion = db.Column(db.String(200), nullable=False, default="")

    usuarios = db.relationship("Usuario", back_populates="rol")

    def __repr__(self):
        return f"<Rol {self.nombre}>"


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuario"
    id = db.Column(db.Integer, primary_key=True)
    documento = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    correo = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    rol_id = db.Column(db.Integer, db.ForeignKey("rol.id"), nullable=False)
    dependencia = db.Column(db.String(120), nullable=False, default="")
    activo = db.Column(db.Boolean, nullable=False, default=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=reloj.ahora)

    rol = db.relationship("Rol", back_populates="usuarios")
    solicitudes = db.relationship("Solicitud", back_populates="solicitante",
                                  foreign_keys="Solicitud.solicitante_id")
    asignadas = db.relationship("Solicitud", back_populates="responsable",
                                foreign_keys="Solicitud.responsable_id")
    notificaciones = db.relationship("Notificacion", back_populates="usuario",
                                     order_by="desc(Notificacion.fecha)")

    # --- seguridad
    def establecer_password(self, clave: str):
        self.password_hash = generate_password_hash(clave)

    def verificar_password(self, clave: str) -> bool:
        return check_password_hash(self.password_hash, clave)

    @property
    def is_active(self):  # Flask-Login no deja iniciar sesión a usuarios inactivos
        return bool(self.activo)

    def tiene_rol(self, *roles) -> bool:
        return self.rol is not None and self.rol.nombre in roles

    def no_leidas(self) -> int:
        return Notificacion.query.filter_by(usuario_id=self.id, leida=False).count()

    def __repr__(self):
        return f"<Usuario {self.correo}>"


class Categoria(db.Model):
    __tablename__ = "categoria"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), unique=True, nullable=False)
    descripcion = db.Column(db.String(255), nullable=False, default="")
    tiempo_respuesta_horas = db.Column(db.Integer, nullable=False, default=72)
    activa = db.Column(db.Boolean, nullable=False, default=True)

    solicitudes = db.relationship("Solicitud", back_populates="categoria")

    def __repr__(self):
        return f"<Categoria {self.nombre}>"


class Solicitud(db.Model):
    __tablename__ = "solicitud"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False, index=True)
    fecha_registro = db.Column(db.DateTime, nullable=False, default=reloj.ahora)
    solicitante_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categoria.id"), nullable=False)
    asunto = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    prioridad = db.Column(db.String(10), nullable=False, default="MEDIA")
    responsable_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=True)
    estado = db.Column(db.String(15), nullable=False, default=REGISTRADA, index=True)
    solucion = db.Column(db.Text, nullable=True)
    fecha_limite = db.Column(db.DateTime, nullable=False)
    fecha_actualizacion = db.Column(db.DateTime, nullable=False, default=reloj.ahora)
    fecha_cierre = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.CheckConstraint("prioridad IN ('BAJA','MEDIA','ALTA','URGENTE')", name="ck_prioridad"),
        db.CheckConstraint("estado IN ('REGISTRADA','ASIGNADA','EN_PROCESO','RESUELTA','CERRADA',"
                           "'RECHAZADA','REABIERTA')", name="ck_estado"),
    )

    solicitante = db.relationship("Usuario", back_populates="solicitudes", foreign_keys=[solicitante_id])
    responsable = db.relationship("Usuario", back_populates="asignadas", foreign_keys=[responsable_id])
    categoria = db.relationship("Categoria", back_populates="solicitudes")
    historial = db.relationship("HistorialEstado", back_populates="solicitud",
                                order_by="HistorialEstado.fecha, HistorialEstado.id",
                                cascade="all, delete-orphan")
    observaciones = db.relationship("Observacion", back_populates="solicitud",
                                    order_by="Observacion.fecha, Observacion.id",
                                    cascade="all, delete-orphan")

    @property
    def nombre_estado(self):
        return NOMBRE_ESTADO[self.estado]

    @property
    def vencida(self) -> bool:
        """True si superó el tiempo de respuesta de su categoría sin haberse resuelto."""
        if self.estado in (RESUELTA, CERRADA, RECHAZADA):
            return False
        return reloj.ahora() > self.fecha_limite

    def calcular_fecha_limite(self, horas: int):
        self.fecha_limite = self.fecha_registro + timedelta(hours=horas)

    def __repr__(self):
        return f"<Solicitud {self.codigo} {self.estado}>"


class HistorialEstado(db.Model):
    __tablename__ = "historial_estado"
    id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey("solicitud.id"), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    estado_anterior = db.Column(db.String(15), nullable=True)
    estado_nuevo = db.Column(db.String(15), nullable=False)
    responsable_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=True)
    motivo = db.Column(db.String(500), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=reloj.ahora)

    solicitud = db.relationship("Solicitud", back_populates="historial")
    usuario = db.relationship("Usuario", foreign_keys=[usuario_id])
    responsable = db.relationship("Usuario", foreign_keys=[responsable_id])


class Observacion(db.Model):
    __tablename__ = "observacion"
    id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey("solicitud.id"), nullable=False, index=True)
    autor_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    es_solucion = db.Column(db.Boolean, nullable=False, default=False)
    fecha = db.Column(db.DateTime, nullable=False, default=reloj.ahora)

    solicitud = db.relationship("Solicitud", back_populates="observaciones")
    autor = db.relationship("Usuario")


class Notificacion(db.Model):
    __tablename__ = "notificacion"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False, index=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey("solicitud.id"), nullable=True)
    mensaje = db.Column(db.String(300), nullable=False)
    leida = db.Column(db.Boolean, nullable=False, default=False)
    fecha = db.Column(db.DateTime, nullable=False, default=reloj.ahora)

    usuario = db.relationship("Usuario", back_populates="notificaciones")
    solicitud = db.relationship("Solicitud")

    def marcar_leida(self):
        self.leida = True


class Parametro(db.Model):
    __tablename__ = "parametro"
    clave = db.Column(db.String(50), primary_key=True)
    valor = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.String(255), nullable=False, default="")

    @staticmethod
    def obtener(clave, defecto=None):
        p = db.session.get(Parametro, clave)
        return p.valor if p else defecto

    @staticmethod
    def entero(clave, defecto):
        try:
            return int(Parametro.obtener(clave, defecto))
        except (TypeError, ValueError):
            return defecto
