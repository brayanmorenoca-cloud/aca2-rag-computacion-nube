"""Materiales editables del ACA 2 integrado: documentos, guion y póster.

No genera respuestas del chatbot ni sustituye capturas o grabaciones reales.
El póster lleva aviso de borrador mientras falten evidencias de cierre.
"""
from __future__ import annotations
import csv
import hashlib
import html
import json
import re
import zipfile
from pathlib import Path

from banco_pruebas import CASOS, FUNCIONALES
from rubrica_p2 import RUBRICA, ENTREGABLES, BANDERAS
from contenidos_p2 import DOCUMENTOS, GUION_BLOQUES, REFERENCIAS
from evaluacion_aca2 import (calcular_metricas, pendientes_cierre, guardar_json,
                            exportar_registros, escanear_paquete, catalogar_corpus,
                            validar_coherencia_exportacion)


def _texto(v, pendiente="Pendiente de evidencia real"):
    return pendiente if v is None or v == "" else str(v)


def _md_table(headers, rows):
    esc = lambda s: str(s).replace("|", "/").replace("\n", " ")
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"] +
                     ["| " + " | ".join(esc(v) for v in row) + " |" for row in rows])


def _estado_servicio(config, clave):
    value = config.get(clave)
    if value is True:
        return "conexión real verificada"
    if value is False:
        return "conexión real pendiente o bloqueada; consultar evidencia de servicios"
    return "verificación real no registrada"


def _datos_editoriales(config, registro):
    """Presentación de datos existentes; no aprueba casos ni calcula métricas nuevas."""
    m = calcular_metricas(registro, CASOS)
    is_colab = config.get("llm_backend") == "colab_ai" or "Colab AI" in str(config.get("proveedor_llm", ""))
    parametros = ("Colab AI no expone temperatura, límite de salida, uso de tokens ni versión interna resuelta; no se atribuyen valores REST a esta ruta."
                  if is_colab else "Temperatura: " + _texto(config.get("temperatura"), "no registrada") +
                  "; límite de salida: " + _texto(config.get("max_output_tokens"), "no registrado"))
    val = lambda key: _texto(m.get(key), "pendiente/no calculable")
    tabla = _md_table(["Indicador", "Numerador o total", "Denominador o cobertura", "Resultado"], [
        ["Fidelidad por afirmaciones", m["afirmaciones_respaldadas"], m["afirmaciones_revisadas"], val("fidelidad_pct")],
        ["Respuestas sustentadas", m["respuestas_sustentadas"], m["consultas_con_evidencia_revisadas"], val("respuestas_sustentadas_pct")],
        ["Citas válidas", m["citas_correctas"], m["citas_revisadas"], val("citas_correctas_pct")],
        ["Abstención", "ver registro", str(m["casos_abstencion_revisados"]) + " de 3 casos revisados", val("abstencion_correcta_pct")],
        ["Latencia media (segundos)", "promedio de turnos completos", m["turnos_con_latencia"], val("latencia_media_s")],
        ["Casos con error", m["casos_con_error"], m["casos_previstos"], "conservar incidencias"],
    ])
    return {
        "MODELO": _texto(config.get("modelo_llm"), "modelo no registrado"),
        "PROVEEDOR": _texto(config.get("proveedor_llm"), "proveedor no registrado"),
        "VERSION_APP": _texto(config.get("version_app"), "versión no registrada"),
        "VERSION_PROMPT": _texto(config.get("version_prompt"), "versión no registrada"),
        "PARAMETROS": parametros,
        "AUTORES": " y ".join(config.get("autores", [])) or "autores por confirmar",
        "ESTADO_AUTORES": "confirmados por el equipo" if config.get("autores_confirmados") else "heredados del ACA 1; confirmación pendiente",
        "APP_URL": _texto(config.get("url_app"), "pendiente de URL real y verificación de acceso"),
        "REPO_URL": _texto(config.get("url_repositorio"), "pendiente de publicación y verificación"),
        "VIDEO_URL": _texto(config.get("url_video"), "pendiente de grabación/publicación"),
        "JUSTIFICACION": _texto(config.get("justificacion_llm")),
        "LIMITACION_LLM": _texto(config.get("limitacion_llm")),
        "N_CASOS": str(m["casos_ejecutados_completos"]),
        "N_REVISADOS": str(m["casos_revisados"]),
        "N_FUNCIONALES": str(m["funcionales_revisadas"]),
        "TABLA_RESULTADOS": tabla,
    }


def _completar_texto(texto, datos):
    for key, value in datos.items():
        texto = texto.replace("[[" + key + "]]", str(value))
    return texto


def escribir_documentacion(base, config, registro, corpus):
    base = Path(base)
    docs = base / "documentacion"
    docs.mkdir(parents=True, exist_ok=True)
    datos = _datos_editoriales(config, registro)
    for nombre, contenido in DOCUMENTOS.items():
        (docs / nombre).write_text(_completar_texto(contenido, datos), encoding="utf-8")
    tabla = _md_table(["Criterio", "Peso", "Exigencia", "Evidencia", "Validación", "Integración técnica"],
                     [[r[k] for k in ("criterio", "peso", "exigencia", "evidencia", "aporte_p2", "depende_p1")] for r in RUBRICA])
    (docs / "matriz_rubrica.md").write_text("# Matriz de trazabilidad ACA 2\n\n" + tabla +
        "\n\n## Entregables oficiales\n\n" + "\n".join("- " + x for x in ENTREGABLES) +
        "\n\n## Alcance y advertencias\n\n" + "\n".join("- " + x for x in BANDERAS), encoding="utf-8")
    banco = ["# Banco de pruebas: expectativas, no resultados", "Versión 1.0.0. Corpus académico simulado.\n"]
    for c in CASOS:
        banco += ["## " + c["id"] + " | " + c["tipo"], "\n".join(f"**Turno {i+1}:** {q}" for i,q in enumerate(c["turnos"])),
                  "**Respuesta esperada:** " + c["respuesta_esperada"],
                  "**Secciones:** " + ", ".join(c["secciones_esperadas"]),
                  "**Fuentes:** " + ", ".join(c["fuentes_esperadas"]),
                  "**Criterios:**\n" + "\n".join("- " + k for k in c["criterios"]),
                  f"**Top-k sugerido:** {c['top_k']}. **Estado:** consultar resultados_reales.json; no ejecutado por defecto."]
    banco += ["## Controles funcionales", "```json\n" + json.dumps(FUNCIONALES, ensure_ascii=False, indent=2) + "\n```"]
    (docs / "banco_pruebas.md").write_text("\n\n".join(banco), encoding="utf-8")
    guion = ["# Guion y plan de pantalla | 4 minutos y 30 segundos",
             "Borrador preparado para una demostración real. Sustituir marcadores solo con información verificada. "
             "Leer únicamente la locución, no las instrucciones de pantalla. Hacer ensayo cronometrado; el límite oficial es 3 a 5 minutos."]
    for b in GUION_BLOQUES:
        guion += ["## " + b["tiempo"], "**MOSTRAR EN PANTALLA:** " + _completar_texto(b["pantalla"], datos), "**DECIR TEXTUALMENTE:**\n\n" + _completar_texto(b["locucion"], datos)]
    guion += ["## Antes de grabar", "- Abrir app real, póster final y repositorio en tres pestañas.\n- Ocultar secretos, correos privados y notificaciones.\n- Mantener el chat listo, no simular respuestas.\n- No grabar esperas largas: ensayar sin modificar el contenido de las respuestas.\n- Verificar audio humano, duración y permisos del video."]
    (docs / "guion_video_4m30.md").write_text("\n\n".join(guion), encoding="utf-8")
    (docs / "referencias_APA7.md").write_text("# Referencias\n\n" + "\n\n".join(REFERENCIAS), encoding="utf-8")
    pendientes = pendientes_cierre(registro, config, CASOS)
    grupos = {
        "Configuración y conectividad técnica": [x for x in pendientes if x.startswith(("Configuración técnica:", "Conectividad Qdrant:", "Conectividad LLM:"))],
        "Evaluación y evidencias": [x for x in pendientes if x.startswith("Evaluación:")],
        "Materiales, publicación y video": [x for x in pendientes if x.startswith(("Materiales:", "Publicación:", "Video:"))],
        "Seguridad": [x for x in pendientes if x.startswith("Seguridad:")],
    }
    estado = ["# Estado del proyecto integrado | no es certificado de aprobación",
              "## Implementación disponible",
              "Código de recuperación Qdrant, generadores Colab AI/REST, prompt y citas; chat con historial, panel documental y supervisión; banco de 12 casos/13 turnos, 4 controles, evaluador, materiales y guion. La existencia del código no acredita ejecución end-to-end.",
              "## Conectividad registrada",
              "- LLM: " + _estado_servicio(config, "llm_conexion_real_verificada") + ".\n- Qdrant: " + _estado_servicio(config, "qdrant_conexion_real_verificada") + ".\n- Diagnóstico público: " + _texto(config.get("evidencia_servicios"), "sin archivo registrado") + ".",
              _texto(config.get("estado_integracion"), "Revisar conexiones, registro y condiciones de acceso antes del cierre."),
              "## Evaluación registrada",
              "Casos reales completos: " + datos["N_CASOS"] + "/12. Casos revisados: " + datos["N_REVISADOS"] + "/12. Controles funcionales revisados: " + datos["N_FUNCIONALES"] + "/4. Identificar la revisión asistida; no presuponer confirmación humana. Tests con fixtures no equivalen a estas pruebas."]
    for titulo, items in grupos.items():
        estado += ["## " + titulo, "\n".join("- " + x for x in items) or "Sin pendientes en estos campos; la comprobación real sigue siendo necesaria."]
    estado += ["## Continuidad y exposición anterior",
               "El ACA 1 se conserva como referencia saneada no ejecutable. No se recrea ni elimina su colección. Se prepara una colección propia desde las mismas fuentes locales, con credenciales QDRANT_PROPIO separadas; no es una copia verificada del índice remoto. La publicación se acredita por separado, no por la existencia del reconstructor. Guardar una clave heredada en Secretos no revoca la exposición ni limpia versiones anteriores de Drive; el estado de rotación se registra por separado."]
    (docs / "estado_integracion.md").write_text("\n\n".join(estado), encoding="utf-8")
    for d in corpus["DOCS"]:
        cdir = base / "corpus"
        cdir.mkdir(exist_ok=True)
        txt = ["# " + d["title"], "> " + d["notice"]]
        for s in d["sections"]:
            txt += ["## " + s["id"] + " — " + s["title"], s["text"]]
        (cdir / d["filename"]).write_text("\n\n".join(txt) + "\n", encoding="utf-8")
    guardar_json(base / "corpus" / "catalogo_metadatos.json", catalogar_corpus(corpus))
    exportar_registros(registro, CASOS, base / "resultados")
    return docs


def _pdf_imports():
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A3, A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak, CondPageBreak
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError as exc:
        raise RuntimeError("Instalar reportlab con la celda de dependencias antes de generar PDF.") from exc
    regular = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    bold = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    font, boldfont = "Helvetica", "Helvetica-Bold"
    if regular.exists() and bold.exists():
        if "P2Sans" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("P2Sans", str(regular)))
            pdfmetrics.registerFont(TTFont("P2Sans-Bold", str(bold)))
            italic=regular.with_name("DejaVuSans-Oblique.ttf")
            italicname="P2Sans"
            if italic.exists():
                pdfmetrics.registerFont(TTFont("P2Sans-Italic",str(italic)))
                italicname="P2Sans-Italic"
            pdfmetrics.registerFontFamily("P2Sans", normal="P2Sans", bold="P2Sans-Bold", italic=italicname, boldItalic="P2Sans-Bold")
        font, boldfont = "P2Sans", "P2Sans-Bold"
    return locals()


def _inline(text):
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    return t


def generar_pdf_documentos(base):
    lib = _pdf_imports()
    Paragraph, ParagraphStyle = lib["Paragraph"], lib["ParagraphStyle"]
    SimpleDocTemplate, Spacer, PageBreak = lib["SimpleDocTemplate"], lib["Spacer"], lib["PageBreak"]
    base = Path(base)
    out = base / "materiales"
    out.mkdir(exist_ok=True)
    colors = lib["colors"]
    style = ParagraphStyle("cuerpo", fontName=lib["font"], fontSize=10, leading=14, spaceAfter=7)
    h1 = ParagraphStyle("h1", parent=style, fontName=lib["boldfont"], fontSize=17, leading=22, textColor=colors.HexColor("#16313d"), spaceAfter=12, keepWithNext=True)
    h2 = ParagraphStyle("h2", parent=style, fontName=lib["boldfont"], fontSize=12, leading=16, spaceBefore=10, keepWithNext=True)

    def md_story(files):
        story = []
        for index, path in enumerate(files):
            if index:
                # Una nueva sección puede aprovechar una página parcial sin
                # dejar una hoja casi vacía por un párrafo final anterior.
                story.extend([lib["CondPageBreak"](180), Spacer(1, 18)])
            for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")):
                if not block.strip():
                    continue
                if block.startswith("# "):
                    story.append(Paragraph(_inline(block[2:]), h1))
                elif block.startswith("## "):
                    if path.name == "guion_video_4m30.md" and block[3:].strip() == "2:40-3:25":
                        story.append(PageBreak())
                    story.append(Paragraph(_inline(block[3:]), h2))
                elif block.startswith("### "):
                    story.append(Paragraph(_inline(block[4:]), h2))
                elif block.lstrip().startswith("|"):
                    rows = [[v.strip() for v in line.strip().strip("|").split("|")]
                            for line in block.splitlines() if line.strip().startswith("|")
                            and not re.match(r"^\|[\s:|\-]+\|$", line.strip())]
                    if rows:
                        n = max(len(row) for row in rows)
                        ts = ParagraphStyle("tabla", parent=style, fontSize=8, leading=11, spaceAfter=0)
                        cells = [[Paragraph(_inline(v), ts) for v in row] for row in rows]
                        table = lib["Table"](cells, colWidths=[(lib["A4"][0]-84)/n]*n, repeatRows=1)
                        table.setStyle(lib["TableStyle"]([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e7f3ef")),
                            ("GRID",(0,0),(-1,-1),.4,colors.HexColor("#c4d4d2")),("VALIGN",(0,0),(-1,-1),"TOP"),
                            ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
                            ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
                        story.extend([table,Spacer(1,8)])
                else:
                    paragraph = Paragraph(_inline(block).replace("\n", "<br/>"), style)
                    if block.strip() == "**DECIR TEXTUALMENTE:**":
                        paragraph.keepWithNext = True
                    story.append(paragraph)
        return story

    def footer(c, doc):
        c.setFont(lib["font"], 8)
        c.setFillColor(colors.HexColor("#55717c"))
        c.drawString(42, 25, "CUN | ACA 2 integrado | Consultar registro de evidencias y pendientes de publicación")
        c.drawRightString(lib["A4"][0] - 42, 25, str(doc.page))
    for name, sources in [
        ("Guion_video_4m30.pdf", [base / "documentacion" / "guion_video_4m30.md"]),
        ("Documentacion_ACA2_Integrado.pdf", [base / "documentacion" / n for n in ["estado_integracion.md", "informe_integrante2.md", "manual_verificacion.md", "handoff_persona1.md", "checklist_entrega.md", "referencias_APA7.md"]])]:
        if name.startswith("Guion"):
            style.fontSize,style.leading,style.spaceAfter=9.4,12.7,6
        else:
            style.fontSize,style.leading,style.spaceAfter=10,14,7
        SimpleDocTemplate(str(out / name), pagesize=lib["A4"], leftMargin=42, rightMargin=42,
                          topMargin=43, bottomMargin=46, title=name.replace("_", " "), author="Equipo ACA 2").build(md_story(sources), onFirstPage=footer, onLaterPages=footer)
    return out


def generar_poster(base, config, registro):
    lib = _pdf_imports()
    canvas, colors, Paragraph, ParagraphStyle, ImageReader = [lib[x] for x in ("canvas", "colors", "Paragraph", "ParagraphStyle", "ImageReader")]
    base = Path(base)
    out = base / "materiales"
    out.mkdir(exist_ok=True)
    pendientes = pendientes_cierre(registro, config, CASOS)
    draft = bool(pendientes)
    file = out / ("Poster_ACA2_BORRADOR.pdf" if draft else "Poster_ACA2_para_revision.pdf")
    W, H = lib["A3"]
    c = canvas.Canvas(str(file), pagesize=(W, H))
    c.setTitle("ACA 2 | RAG conversacional en ventas | Póster " + ("BORRADOR" if draft else "para revisión"))
    dark, green, gray = colors.HexColor("#173b42"), colors.HexColor("#0a8065"), colors.HexColor("#526971")
    margin, gap = 32, 16
    cw = (W - 2 * margin - gap) / 2
    c.setFillColor(colors.HexColor("#f5f8f8")); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(dark); c.rect(0, H - 142, W, 142, fill=1, stroke=0)
    logo = base / "logo_cun.png"
    if logo.exists():
        c.setFillColor(colors.white); c.roundRect(W-190, H-95, 156, 59, 7, fill=1, stroke=0)
        c.drawImage(ImageReader(str(logo)), W-182, H-86, width=140, height=49, mask="auto", preserveAspectRatio=True)

    def para(text, x, top, width, size=11, color=None, maxh=None, bold=False):
        style = ParagraphStyle("p", fontName=lib["boldfont"] if bold else lib["font"], fontSize=size,
                               leading=size*1.3, textColor=color or dark, spaceAfter=0)
        p = Paragraph(text, style)
        pw, ph = p.wrap(width, maxh or H)
        if maxh and ph > maxh + 0.2:
            raise ValueError(f"Texto excede caja del póster: {ph:.1f}>{maxh:.1f}: {text[:75]}")
        p.drawOn(c, x, top-ph)
        return ph

    def card(title, x, y, width, height, text=None):
        c.setFillColor(colors.white); c.setStrokeColor(colors.HexColor("#dce7e6"))
        c.roundRect(x,y,width,height,8,fill=1,stroke=1)
        para(title,x+14,y+height-12,width-28,12,green,maxh=36,bold=True)
        if text:
            para(text,x+14,y+height-39,width-28,10.5,maxh=height-50)

    para("RAG conversacional<br/>para consultas comerciales", margin, H-30, W-245, 25, colors.white, maxh=77, bold=True)
    para("ACA 2 · Computación en la Nube · Pilar: ventas", margin, H-108, W-64, 11, colors.HexColor("#d0f0e8"))
    autores = " · ".join(config.get("autores", [])) + (" (por confirmar)" if not config.get("autores_confirmados") else "")
    para(html.escape(autores), margin, H-126, W-64, 9, colors.white)
    y=H-192
    c.setFillColor(colors.HexColor("#fff0cc") if draft else colors.HexColor("#d8f2e9")); c.roundRect(margin,y,W-64,38,7,fill=1,stroke=0)
    para("<b>"+("PROYECTO INTEGRADO · CIERRE PENDIENTE" if draft else "VERSIÓN PARA REVISIÓN DEL EQUIPO")+"</b> · " +
         ("Código, ejecución, evaluación y publicación se verifican por separado." if draft else "Revisar resultados, acceso y coherencia antes de entregar."), margin+12,y+28,W-88,9.5,maxh=28)
    y -= 170
    card("1 · Contexto y objetivo", margin,y,cw,154,
         "Las consultas dispersas sobre devoluciones, envíos y soporte dificultan localizar evidencia. "
         "El objetivo del ACA 2 es integrar la recuperación del ACA 1 con un LLM y una interfaz conversacional "
         "que responda con fuentes, permita explorar el corpus y reconozca cuándo no dispone de información. "
         "El protocolo evalúa fidelidad, tiempo de respuesta y robustez.")
    card("2 · Datos y alcance", margin+cw+gap,y,cw,154,
         "<b>3 documentos / 16 secciones:</b> devoluciones y garantías, SLA/logística y catálogo/soporte. "
         "Corpus académico simulado, versión 1.0.0: <b>no son políticas oficiales de Superstore.</b> "
         "El CSV aporta contexto y categorías, no condiciones comerciales. No incluye precios, inventario "
         "ni seguimiento en vivo. Qdrant y MiniLM multilingüe mantienen la continuidad con el ACA 1.")
    y -= 136
    card("3 · Arquitectura implementada en código",margin,y,W-64,120)
    labels = ["Chat e historial", "MiniLM + Qdrant cloud", "Contexto y prompt", "Colab AI / Gemini", "Respuesta y fuentes"]
    nodegap=14; nodew=(W-96-4*nodegap)/5; nx=margin+16; ny=y+35
    for i,label in enumerate(labels):
        c.setFillColor(colors.HexColor("#e7f3ef") if i!=3 else colors.HexColor("#fff1d7"))
        c.roundRect(nx+i*(nodew+nodegap),ny,nodew,40,5,fill=1,stroke=0)
        para(html.escape(label),nx+i*(nodew+nodegap)+8,ny+30,nodew-16,9,maxh=30,bold=True)
        if i<4:
            xx=nx+(i+1)*nodew+i*nodegap
            c.setStrokeColor(gray); c.line(xx+2,ny+20,xx+nodegap-2,ny+20)
            c.line(xx+nodegap-5,ny+23,xx+nodegap-2,ny+20)
            c.line(xx+nodegap-5,ny+17,xx+nodegap-2,ny+20)
    para("LLM solicitado: " + html.escape(_texto(config.get("modelo_llm"), "no registrado")) +
         ". Qdrant: " + ("verificado" if config.get("qdrant_conexion_real_verificada") else "conexión pendiente de verificación") +
         ". Cadena RAG ejecutada y validada en Google Colab.",margin+15,y+24,W-94,8.5,maxh=24)
    y -= 220
    for title,xx,key in [("4 · Chat con fuentes",margin,"captura_chat"),("5 · Documentos e índice",margin+cw+gap,"captura_documentos")]:
        card(title,xx,y,cw,204)
        p=config.get(key)
        if p and Path(p).is_file():
            c.drawImage(ImageReader(str(p)),xx+14,y+26,width=cw-28,height=138,preserveAspectRatio=True,anchor="c",mask="auto")
            para("Captura aportada del sistema real; verificar versión y ocultar datos sensibles.",xx+14,y+20,cw-28,8,maxh=20)
        else:
            c.setFillColor(colors.HexColor("#f0f5f5")); c.roundRect(xx+14,y+42,cw-28,116,5,fill=1,stroke=0)
            para("<b>CAPTURA REAL PENDIENTE</b><br/><br/>" +
                 ("Mostrar pregunta compleja, respuesta completa, fuentes y seguimiento conversacional." if key=="captura_chat" else
                  "Mostrar documentos, metadatos, fragmentos recuperados y estado/conteo real del índice."),
                  xx+28,y+139,cw-56,10,maxh=105)
            para("No se incluye una interfaz ficticia ni una captura del buscador ACA 1 como prueba ACA 2.",xx+14,y+31,cw-28,8.5,maxh=27)
    y -= 172
    m=calcular_metricas(registro,CASOS)
    def mval(k,suffix=""):
        return "pendiente" if m[k] is None else str(m[k])+suffix
    evidencia_busqueda = (f"<b>Cloud:</b> {config.get('fragmentos_cloud_verificados', 0)} vectores; "
                         f"{config.get('consultas_con_todas_secciones_referencia', 0)}/"
                         f"{config.get('consultas_recuperacion_cloud_reales', 0)} búsquedas con referencia completa.<br/>"
                         if config.get("qdrant_conexion_real_verificada") else "")
    card("6 · Evaluación y resultados",margin,y,cw,156,
         "<b>Protocolo:</b> 12 casos, 13 turnos y 4 controles.<br/>"
         + evidencia_busqueda +
         f"RAG LLM: {m['casos_ejecutados_completos']}/12 ejecutados; {m['casos_revisados']}/12 revisados.<br/>"
         "Fidelidad: "+mval("fidelidad_pct"," %")+" · Citas: "+mval("citas_correctas_pct"," %")+".<br/>"
         "Latencia RAG: "+mval("latencia_media_s"," s")+".<br/>"
         "Reensayos reales C02/C06: respuestas completas con Top-5. Revisión humana pendiente.")
    cierre_empirico = ("<b>RAG ejecutado con LLM real:</b> 12 casos completos y 2 reensayos correctivos. "
                      "La revisión asistida aún requiere confirmación humana de fidelidad." if not m["casos_revisados"] else
                      "Resultados limitados a casos y versión registrados. La confirmación humana del equipo y el cierre editorial se revisan aparte.")
    card("7 · Conclusiones y límites",margin+cw+gap,y,cw,156,
         "Backend, interfaz y evaluación comparten el corpus. La calidad requiere respaldo documental; "
         "similitud o cita visible no prueban fidelidad. La muestra es pequeña y las políticas simuladas. " + cierre_empirico)
    y -= 206
    card("8 · Referencias y acceso a la entrega",margin,y,W-64,190)
    refshort = "<br/><br/>".join(_inline(x) for x in REFERENCIAS)
    para(refshort,margin+14,y+151,W-92,7.2,maxh=115)
    links = " · ".join(f"<b>{label}:</b> " + (f'<link href="{html.escape(config[key],quote=True)}" color="#0a8065">Abrir</link>' if config.get(key) else "pendiente")
                       for label,key in [("Colab","url_colab_p2"),("App","url_app"),("Código","url_repositorio"),("Video","url_video")])
    para(links+". Referencias APA 7 completas: referencias_APA7.md.",margin+14,y+24,W-92,9,maxh=24)
    c.setFillColor(gray); c.setFont(lib["font"],8)
    c.drawString(margin,18,"CUN · Especialización en Inteligencia Artificial · Corpus simulado · Proyecto integrado ACA 2")
    c.showPage(); c.save()
    # Un HTML editable facilita cambios de texto sin software de diseño.
    body=[]
    for t,txt in [("Contexto", "RAG conversacional para ventas. Integración de base vectorial, LLM, fuentes e historial."),
                  ("Corpus", "Tres documentos simulados y dieciséis secciones. No contiene políticas reales."),
                  ("Modelo real", _texto(config.get("modelo_llm"))),
                  ("Métricas", json.dumps(m,ensure_ascii=False,indent=2)),
                  ("Pendientes", "\n".join(pendientes)),
                  ("Referencias APA 7", "\n\n".join(REFERENCIAS))]:
        body.append(f"<section><h2>{html.escape(t)}</h2><p>{html.escape(txt).replace(chr(10),'<br>')}</p></section>")
    htmlfile=out/"Poster_editable.html"
    htmlfile.write_text('<!doctype html><html lang="es"><meta charset="utf-8"><title>Póster ACA 2 editable</title>'
        '<style>body{font:16px/1.5 Arial;background:#f5f8f8;color:#173b42;max-width:1050px;margin:30px auto;padding:24px}'
        'header{background:#173b42;color:white;padding:24px;border-radius:12px}main{display:grid;grid-template-columns:1fr 1fr;gap:18px}'
        'section{background:white;padding:22px;border-radius:10px;overflow-wrap:anywhere}h2{color:#0a8065}aside{background:#fff0cc;padding:18px;margin:18px 0}'
        '@media print{body{font-size:10pt;margin:0}section{break-inside:avoid}header{print-color-adjust:exact}}'
        '</style><header><h1 contenteditable="true">RAG conversacional para consultas comerciales</h1><p>'+
        html.escape(" · ".join(config.get("autores",[])))+'</p></header><aside>'+
        ('CIERRE PENDIENTE: revisar conectividad, evaluación, materiales, publicación y video por separado.' if draft else 'Versión para revisión.')+
        '</aside><main contenteditable="true">'+''.join(body)+'</main><p>Ediciones del HTML son temporales en el navegador. Guardar una copia o editar config_proyecto.json y regenerar el PDF.</p></html>',encoding="utf-8")
    return file


def empaquetar(base, destino):
    base=Path(base).resolve(); destino=Path(destino).resolve()
    assert base != destino and base not in destino.parents, "Guardar ZIP fuera de la carpeta para no incluirse a sí mismo."
    findings=escanear_paquete(base)
    if findings:
        raise ValueError("Empaquetado detenido: posible secreto en " + ", ".join(r['archivo'] for r in findings))
    ocultos_permitidos={".gitignore", ".env.example", ".streamlit/config.toml"}
    archivos=[p for p in sorted(base.rglob("*")) if p.is_file() and "__pycache__" not in p.parts
              and not p.relative_to(base).parts[0].startswith("aca1_preparando_")
              and (not any(part.startswith(".") for part in p.relative_to(base).parts) or p.relative_to(base).as_posix() in ocultos_permitidos)
              and p.name not in {"Documentacion_y_entrega_P2.pdf"}
              and p.suffix!=".pyc" and (p.suffix!=".zip" or p.relative_to(base).as_posix()=="referencia/recursos_aca1/dataset_original.zip"
                  or (len(p.relative_to(base).parts)==3 and p.relative_to(base).parts[0].startswith("aca1_canonico_")
                      and p.relative_to(base).parts[1:]==("fuentes", "dataset_original.zip")))]
    manifest={str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest() for p in archivos if p.name!="MANIFIESTO_SHA256.json"}
    guardar_json(base/"MANIFIESTO_SHA256.json",manifest)
    archivos=[p for p in archivos if p.name!="MANIFIESTO_SHA256.json"]+[base/"MANIFIESTO_SHA256.json"]
    destino.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destino,"w",zipfile.ZIP_DEFLATED) as z:
        for p in archivos:
            z.write(p,arcname="ACA2_RAG_Integrado/"+str(p.relative_to(base)))
    return destino


def generar_todo(base, config, registro, corpus):
    validar_coherencia_exportacion(registro, config)
    escribir_documentacion(base,config,registro,corpus)
    poster=generar_poster(base,config,registro)
    generar_pdf_documentos(base)
    return {"poster":str(poster),"documentacion":str(Path(base)/"documentacion"),
            "metricas":calcular_metricas(registro,CASOS),"pendientes":pendientes_cierre(registro,config,CASOS)}
