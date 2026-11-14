"""Definición única del cuestionario de Marcello V1 (versión "v1").

Es la fuente de verdad para: validación del backend, semilla de la base de datos,
columnas de exportación y estadísticas. Si se cambia una pregunta u opción, debe
crearse una NUEVA versión de encuesta (no editar la "v1" una vez hay respuestas).
"""
from dataclasses import dataclass

SURVEY_CODE = "v1"
SURVEY_TITLE = "Marcello V1 — Levantamiento de requisitos"

LIKERT_LABELS = (
    "Sin importancia",
    "Poco importante",
    "Moderadamente importante",
    "Muy importante",
    "Extremadamente importante",
)


@dataclass(frozen=True)
class QuestionDef:
    code: str
    position: int
    text: str
    qtype: str  # "single" | "multiple" | "likert"
    options: tuple  # el valor de cada opción es su posición (1..n)


def _likert(pos: int, text: str) -> QuestionDef:
    return QuestionDef(f"P{pos}", pos, text, "likert", LIKERT_LABELS)


QUESTIONS = (
    QuestionDef("P1", 1, "¿Cuál es su perfil profesional?", "single", (
        "Médico especialista en medicina regenerativa",
        "Biólogo celular",
        "Genetista",
        "Ingeniero biomédico",
        "Bioinformático",
        "Ingeniero de bioimpresión 3D",
        "Ingeniero de simulación computacional",
        "Investigador en ingeniería de tejidos",
        "Especialista en control de calidad y validación",
        "Especialista en sistemas de información y gestión de datos biomédicos",
    )),
    _likert(2, "¿Qué tan importante es disponer de software especializado para simular tejidos destinados a bioimpresión?"),
    QuestionDef("P3", 3, "¿Qué información es necesaria para realizar simulaciones personalizadas? (puede elegir varias)", "multiple", (
        "Imágenes anatómicas o médicas",
        "Información celular y biológica",
        "Información genética",
        "Información clínica",
        "Propiedades físicas y mecánicas de los tejidos",
    )),
    _likert(4, "¿Qué tan importante es incorporar características individuales del paciente?"),
    QuestionDef("P5", 5, "¿Qué características debería representar el software? (puede elegir varias)", "multiple", (
        "Geometría, dimensiones y estructura del tejido",
        "Organización y distribución celular",
        "Propiedades biológicas",
        "Propiedades mecánicas y físicas",
        "Respuesta funcional del tejido",
    )),
    _likert(6, "¿Qué tan importante es incorporar información genética y celular?"),
    QuestionDef("P7", 7, "¿Qué operaciones debería permitir el software sobre la información genética y celular? (puede elegir varias)", "multiple", (
        "Registrar y almacenar información",
        "Procesar y analizar información",
        "Relacionar información con las características del tejido",
        "Integrar información en simulaciones",
        "Consultar y recuperar información",
    )),
    _likert(8, "¿Qué tan importante es poder modificar parámetros y configuraciones de simulación?"),
    QuestionDef("P9", 9, "¿Qué mecanismos deberían usarse para validar las simulaciones? (puede elegir varios)", "multiple", (
        "Comparación con criterios científicos preestablecidos",
        "Revisión por especialistas",
        "Comparación con resultados experimentales",
        "Evaluación de propiedades físicas y biológicas",
        "Registro de evidencias y resultados",
    )),
    _likert(10, "¿Qué tan importante es conservar y comparar versiones de simulaciones y resultados?"),
    QuestionDef("P11", 11, "¿Con qué sistemas y herramientas debería integrarse Marcello V1? (puede elegir varios)", "multiple", (
        "Equipos de adquisición de imágenes médicas",
        "Sistemas de información clínica",
        "Software y equipos de bioimpresión 3D",
        "Herramientas de simulación computacional",
        "Herramientas de análisis bioinformático",
    )),
    _likert(12, "¿Qué tan importante es exportar modelos y parámetros hacia herramientas de bioimpresión?"),
    QuestionDef("P13", 13, "¿Qué medidas de seguridad son necesarias? (puede elegir varias)", "multiple", (
        "Control de acceso",
        "Cifrado de información",
        "Anonimización o seudonimización",
        "Registro de accesos y modificaciones",
        "Copias de seguridad y recuperación",
    )),
    QuestionDef("P14", 14, "¿Qué elementos son necesarios para garantizar la trazabilidad? (puede elegir varios)", "multiple", (
        "Datos de entrada",
        "Parámetros y configuraciones",
        "Versiones de modelos y resultados",
        "Modificaciones realizadas",
        "Revisiones y validaciones de especialistas",
    )),
    QuestionDef("P15", 15, "¿Cuál debería ser la principal prioridad de desarrollo?", "single", (
        "Gestión y procesamiento de datos del paciente",
        "Simulación geométrica, biológica y mecánica",
        "Personalización de simulaciones",
        "Validación de resultados",
        "Integración con sistemas externos",
        "Seguridad, privacidad y trazabilidad",
    )),
)

QUESTIONS_BY_CODE = {q.code: q for q in QUESTIONS}


def survey_to_dict() -> dict:
    return {
        "code": SURVEY_CODE,
        "title": SURVEY_TITLE,
        "questions": [
            {
                "code": q.code,
                "position": q.position,
                "text": q.text,
                "type": q.qtype,
                "options": [{"value": i, "label": label} for i, label in enumerate(q.options, start=1)],
            }
            for q in QUESTIONS
        ],
    }


def validate_answers(raw: dict):
    """Valida respuestas {código: [valores]}. Devuelve (limpias, errores)."""
    clean, errors = {}, {}
    for code in raw:
        if code not in QUESTIONS_BY_CODE:
            errors[str(code)] = "pregunta desconocida"
    for q in QUESTIONS:
        values = raw.get(q.code)
        if not values:
            errors[q.code] = "respuesta obligatoria"
            continue
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in values):
            errors[q.code] = "los valores deben ser números enteros"
            continue
        n = len(q.options)
        if any(v < 1 or v > n for v in values):
            errors[q.code] = f"valor fuera de rango (1 a {n})"
            continue
        if len(set(values)) != len(values):
            errors[q.code] = "opciones duplicadas"
            continue
        if q.qtype in ("single", "likert") and len(values) != 1:
            errors[q.code] = "debe seleccionar exactamente una opción"
            continue
        clean[q.code] = sorted(values)
    return clean, errors
