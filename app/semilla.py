# -*- coding: utf-8 -*-
"""Datos iniciales y de demostración.

Los datos de demostración se generan pasando por el servicio de solicitudes (no se insertan
a mano), de modo que cumplen las mismas reglas de negocio y dejan historial y notificaciones.
"""
import random
from datetime import datetime, timedelta

from . import reloj
from .extensions import db
from .models import (ADMINISTRADOR, ESTUDIANTE, FUNCIONARIO, SUPERVISOR, Categoria, Notificacion, Parametro,
                     Rol, Usuario)
from .servicios import solicitudes as srv

CLAVE_DEMO = "Sgsu2026"  # contraseña de prueba de todos los usuarios de demostración

ROLES = {
    ADMINISTRADOR: "Gestiona usuarios, roles, categorías y parámetros del sistema.",
    ESTUDIANTE: "Registra solicitudes y consulta únicamente sus propios casos.",
    FUNCIONARIO: "Atiende las solicitudes asignadas, registra observaciones y actualiza estados.",
    SUPERVISOR: "Asigna solicitudes, consulta indicadores, reportes y el estado general.",
}

PARAMETROS = [
    ("nombre_institucion", "Corporación Universitaria Latinoamericana", "Nombre de la institución"),
    ("tiempo_respuesta_defecto_horas", "72", "Tiempo de respuesta por defecto (horas)"),
    ("longitud_minima_descripcion", "20", "Longitud mínima de la descripción (caracteres)"),
]


def cargar_basicos():
    for nombre, desc in ROLES.items():
        if not Rol.query.filter_by(nombre=nombre).first():
            db.session.add(Rol(nombre=nombre, descripcion=desc))
    for clave, valor, desc in PARAMETROS:
        if not db.session.get(Parametro, clave):
            db.session.add(Parametro(clave=clave, valor=valor, descripcion=desc))
    db.session.flush()
    if not Usuario.query.filter_by(correo="admin@sgsu.edu.co").first():
        _usuario("1000000001", "Administrador del Sistema", "admin@sgsu.edu.co", ADMINISTRADOR, "Oficina TIC")
    db.session.commit()


def _usuario(doc, nombre, correo, rol, dependencia):
    u = Usuario(documento=doc, nombre=nombre, correo=correo, dependencia=dependencia,
                rol=Rol.query.filter_by(nombre=rol).one(), fecha_creacion=datetime(2026, 9, 1, 8, 0))
    u.establecer_password(CLAVE_DEMO)
    db.session.add(u)
    return u


CATEGORIAS = [
    ("Certificados y constancias", "Certificados de estudio, notas, paz y salvo y constancias.", 48, "registro"),
    ("Homologaciones y notas", "Homologación de asignaturas y corrección de calificaciones.", 120, "registro"),
    ("Matrícula académica", "Inscripción, adición y cancelación de asignaturas.", 48, "registro"),
    ("Soporte tecnológico", "Plataforma virtual, correo institucional y redes.", 24, "tic"),
    ("Pagos y financiera", "Liquidaciones, pagos, devoluciones y financiación.", 72, "financiera"),
    ("Bienestar universitario", "Apoyos, becas, salud, deportes y actividades culturales.", 72, "bienestar"),
]

TEXTOS = {
    "Certificados y constancias": [
        ("Certificado de estudio para trámite bancario", "Necesito un certificado de estudio vigente con el semestre que curso para presentarlo en el banco."),
        ("Constancia de notas del semestre anterior", "Solicito constancia de calificaciones del periodo 2026-1 para postularme a una convocatoria de beca."),
        ("Paz y salvo académico", "Requiero el paz y salvo académico para continuar con el proceso de grado."),
    ],
    "Homologaciones y notas": [
        ("Homologación de Cálculo I", "Cursé Cálculo I en otra universidad y deseo homologarla. Adjunto el contenido programático."),
        ("Corrección de nota de Programación II", "La nota final registrada en la plataforma no coincide con la publicada por el docente."),
    ],
    "Matrícula académica": [
        ("Adición de asignatura electiva", "Deseo adicionar la electiva de Analítica de datos, el sistema no me permite inscribirla."),
        ("Cancelación de asignatura", "Solicito la cancelación de Física II por cruce de horario con mi trabajo."),
    ],
    "Soporte tecnológico": [
        ("No puedo ingresar al aula virtual", "Desde ayer la plataforma virtual muestra error de credenciales aunque la contraseña es correcta."),
        ("Restablecer correo institucional", "Olvidé la contraseña del correo institucional y la opción de recuperación no funciona."),
        ("Falla de la red inalámbrica en el bloque B", "En los salones del bloque B la red inalámbrica se desconecta constantemente."),
    ],
    "Pagos y financiera": [
        ("Pago no reflejado en el sistema", "Realicé el pago de la matrícula hace cinco días y aún aparece como pendiente."),
        ("Solicitud de financiación de matrícula", "Quisiera información y trámite para financiar el valor de la matrícula en cuotas."),
    ],
    "Bienestar universitario": [
        ("Inscripción a apoyo alimentario", "Solicito ser incluido en el programa de apoyo alimentario del semestre."),
        ("Cita con psicología", "Requiero una cita con el servicio de psicología de bienestar universitario."),
    ],
}

SOLUCIONES = {
    "Certificados y constancias": "Se expidió el documento solicitado y se envió al correo institucional del estudiante.",
    "Homologaciones y notas": "El comité curricular revisó el caso y se actualizó el registro académico.",
    "Matrícula académica": "Se realizó el ajuste de la matrícula en el sistema académico.",
    "Soporte tecnológico": "Se restablecieron las credenciales y se verificó el acceso con el usuario.",
    "Pagos y financiera": "Se conciliaron los pagos con el banco y se actualizó el estado de cuenta.",
    "Bienestar universitario": "Se agendó la atención y se confirmó la inscripción en el programa.",
}

HOY = datetime(2026, 11, 25, 17, 0)


def cargar_demo(semilla=2026):
    rnd = random.Random(semilla)
    sup = _usuario("1000000002", "Marta Lucía Rivas", "supervisor@sgsu.edu.co", SUPERVISOR, "Vicerrectoría Académica")
    func = {
        "registro": _usuario("1000000003", "Andrés Felipe Torres", "andres.torres@sgsu.edu.co", FUNCIONARIO, "Registro y Control"),
        "tic": _usuario("1000000004", "Jorge Iván Castillo", "jorge.castillo@sgsu.edu.co", FUNCIONARIO, "Soporte TIC"),
        "financiera": _usuario("1000000005", "Diana Marcela Ospina", "diana.ospina@sgsu.edu.co", FUNCIONARIO, "Gestión Financiera"),
        "bienestar": _usuario("1000000006", "Paola Andrea Mejía", "paola.mejia@sgsu.edu.co", FUNCIONARIO, "Bienestar Universitario"),
    }
    est = [
        _usuario("1100000001", "Valentina Ruiz Díaz", "valentina.ruiz@sgsu.edu.co", ESTUDIANTE, "Ingeniería de Sistemas"),
        _usuario("1100000002", "Santiago Herrera López", "santiago.herrera@sgsu.edu.co", ESTUDIANTE, "Ingeniería Industrial"),
        _usuario("1100000003", "Daniela Fuentes Mora", "daniela.fuentes@sgsu.edu.co", ESTUDIANTE, "Contaduría Pública"),
        _usuario("1100000004", "Camilo Andrés Pardo", "camilo.pardo@sgsu.edu.co", ESTUDIANTE, "Derecho"),
        _usuario("1100000005", "Sebastián Royero Gil", "sebastian.royero@sgsu.edu.co", ESTUDIANTE, "Ingeniería de Sistemas"),
    ]
    _usuario("1000000007", "Luis Carlos Pérez", "luis.perez@sgsu.edu.co", FUNCIONARIO, "Registro y Control").activo = False
    cats = {}
    for nombre, desc, horas, area in CATEGORIAS:
        c = Categoria(nombre=nombre, descripcion=desc, tiempo_respuesta_horas=horas)
        db.session.add(c)
        cats[nombre] = (c, area)
    db.session.add(Categoria(nombre="Biblioteca", descripcion="Préstamos y renovaciones (categoría retirada).",
                             tiempo_respuesta_horas=48, activa=False))
    db.session.commit()

    inicio = datetime(2026, 10, 1, 7, 0)
    total = 34
    for i in range(total):
        # fechas repartidas entre el 1 de octubre y hoy, con horario de oficina
        dia = inicio + timedelta(days=int(55 * i / total) + rnd.randint(0, 1))
        t = dia.replace(hour=rnd.randint(7, 16), minute=rnd.choice((0, 10, 20, 30, 45, 50)))
        nombre_cat = rnd.choice(list(TEXTOS))
        cat, area = cats[nombre_cat]
        asunto, desc = rnd.choice(TEXTOS[nombre_cat])
        alumno = rnd.choice(est)
        prioridad = rnd.choices(("BAJA", "MEDIA", "ALTA", "URGENTE"), (2, 5, 3, 1))[0]
        reloj.fijar(t)
        s = srv.registrar(alumno, cat.id, asunto, desc, prioridad)

        edad = (HOY - t).days
        destino = rnd.choices(["CERRADA", "RESUELTA", "EN_PROCESO", "ASIGNADA", "RECHAZADA", "REGISTRADA"],
                              (10, 3, 3, 2, 1, 1))[0]
        if edad <= 1:
            destino = rnd.choice(["REGISTRADA", "ASIGNADA"])
        elif edad <= 4 and destino == "CERRADA":
            destino = "EN_PROCESO"

        def avanzar(horas_min, horas_max):
            nonlocal t
            previo = t
            t = t + timedelta(hours=rnd.randint(horas_min, horas_max), minutes=rnd.randint(0, 59))
            if t > HOY:  # nunca en el futuro y siempre después del paso anterior
                t = max(previo + timedelta(minutes=5), HOY - timedelta(minutes=rnd.randint(5, 90)))
            reloj.fijar(t)

        if destino == "REGISTRADA":
            continue
        if destino == "RECHAZADA":
            avanzar(2, 20)
            srv.rechazar(s, sup, "La solicitud no corresponde a esta dependencia; debe tramitarse ante la facultad.")
            continue
        avanzar(1, 4)
        srv.asignar(s, sup, func[area].id)
        if destino == "ASIGNADA":
            continue
        avanzar(1, 6)
        srv.iniciar(s, func[area])
        if rnd.random() < 0.5:
            avanzar(1, 12)
            srv.observar(s, func[area], "Se está verificando la información con la dependencia correspondiente.")
        if destino == "EN_PROCESO":
            continue
        # algunas se resuelven fuera del tiempo de respuesta para que los indicadores sean realistas
        lento = rnd.random() < 0.25
        avanzar(*((cat.tiempo_respuesta_horas, cat.tiempo_respuesta_horas + 40) if lento else (cat.tiempo_respuesta_horas // 6, cat.tiempo_respuesta_horas // 2)))
        srv.resolver(s, func[area], SOLUCIONES[nombre_cat])
        if destino == "RESUELTA":
            continue
        avanzar(2, 40)
        srv.cerrar(s, alumno, "Conforme con la respuesta recibida")

    # Casos de demostración del ciclo completo: reapertura autorizada y reapertura por inconformidad
    reloj.fijar(datetime(2026, 11, 10, 9, 15))
    s = srv.registrar(est[0], cats["Pagos y financiera"][0].id, "Doble cobro en la matrícula",
                      "En el extracto aparecen dos cobros por el mismo valor de la matrícula del semestre 2026-2.", "ALTA")
    reloj.fijar(datetime(2026, 11, 10, 11, 0)); srv.asignar(s, sup, func["financiera"].id)
    reloj.fijar(datetime(2026, 11, 10, 14, 30)); srv.iniciar(s, func["financiera"])
    reloj.fijar(datetime(2026, 11, 12, 10, 0)); srv.resolver(s, func["financiera"], "Se anuló el segundo cobro y se solicitó la devolución al banco.")
    reloj.fijar(datetime(2026, 11, 13, 8, 0)); srv.cerrar(s, est[0], "Conforme")
    reloj.fijar(datetime(2026, 11, 20, 16, 0))
    srv.reabrir(s, sup, "La estudiante reporta que la devolución no se ha reflejado; se reabre para seguimiento.")
    reloj.fijar(datetime(2026, 11, 21, 9, 0)); srv.iniciar(s, func["financiera"])
    reloj.fijar(datetime(2026, 11, 21, 9, 30))
    srv.observar(s, func["financiera"], "Se escaló el caso al banco con el número de radicado 45821.")

    reloj.fijar(datetime(2026, 11, 18, 10, 5))
    s = srv.registrar(est[1], cats["Soporte tecnológico"][0].id, "Error al subir trabajos en el aula virtual",
                      "Al cargar un archivo PDF en la actividad de la semana 12 la plataforma muestra un error 500.", "URGENTE")
    reloj.fijar(datetime(2026, 11, 18, 10, 40)); srv.asignar(s, sup, func["tic"].id)
    reloj.fijar(datetime(2026, 11, 18, 11, 0)); srv.iniciar(s, func["tic"])
    reloj.fijar(datetime(2026, 11, 18, 15, 20)); srv.resolver(s, func["tic"], "Se amplió el tamaño máximo de archivo permitido en la actividad.")
    reloj.fijar(datetime(2026, 11, 19, 8, 10))
    srv.reabrir(s, est[1], "El error persiste con archivos de más de 20 MB.")
    reloj.fijar(datetime(2026, 11, 19, 9, 0))
    srv.observar(s, est[1], "Adjunto captura del error: aparece al 90 % de la carga.")

    reloj.fijar(datetime(2026, 11, 14, 11, 30))
    s = srv.registrar(est[3], cats["Bienestar universitario"][0].id, "Préstamo de equipo de cómputo",
                      "Solicito el préstamo de un portátil durante el semestre para realizar mis trabajos.", "MEDIA")
    reloj.fijar(datetime(2026, 11, 14, 15, 0))
    srv.rechazar(s, sup, "Bienestar no presta equipos; el trámite se hace en la Biblioteca con el carné estudiantil.")

    reloj.fijar(None)
    # los avisos de más de tres días se dan por leídos
    Notificacion.query.filter(Notificacion.fecha < HOY - timedelta(days=3)).update({"leida": True})
    db.session.commit()
