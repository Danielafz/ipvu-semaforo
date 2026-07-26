import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import json
import os
import importlib
import time
import base64
from pdf2image import convert_from_bytes
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

import extractor as extractor_mod
import comparador as comparador_mod
importlib.reload(extractor_mod)
importlib.reload(comparador_mod)

from extractor import extraer_ddjj, extraer_informe
from comparador import comparar, ROJO, AMARILLO, VERDE

POPPLER_PATH = r"D:\PROGRAMAS\poppler-26.02.0\Library\bin"

st.set_page_config(
    page_title="IPVU — Semáforo de Inconsistencias",
    page_icon="🚦",
    layout="wide"
)

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #1A1A1A; }
[data-testid="stSidebar"] { background-color: #388E3C; border-right: 3px solid #C9A84C; }
    [data-testid="stSidebar"] * { color: #F0F0F0 !important; }
    .header-line {
        height: 4px;
        background: linear-gradient(90deg, #1B5E20, #C9A84C, #E65100);
        border-radius: 2px; margin: 10px 0 20px 0;
    }
    .card {
        background-color: #F9F9F9; border: 1px solid #C9A84C;
        border-radius: 12px; padding: 20px; margin: 10px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }
    .main-title { font-size: 2.2rem; font-weight: 700; color: #1B5E20; text-align: center; margin-bottom: 5px; }
    .sub-title { font-size: 1rem; color: #555555; text-align: center; margin-bottom: 20px; }
    [data-testid="stMetric"] {
        background-color: #F9F9F9; border: 1px solid #C9A84C;
        border-radius: 10px; padding: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    [data-testid="stMetricLabel"] { color: #1B5E20 !important; font-size: 0.85rem !important; font-weight: 600 !important; }
    [data-testid="stMetricValue"] { color: #1A1A1A !important; font-size: 2rem !important; }
    [data-testid="stFileUploader"] { background-color: #F9F9F9; border: 2px dashed #C9A84C; border-radius: 10px; padding: 10px; }
    [data-testid="stFileUploader"] * { color: #1A1A1A !important; }
    [data-testid="stFileUploaderDropzone"] { background-color: #FFFFFF !important; color: #1A1A1A !important; }
    [data-testid="stFileUploaderDropzone"] * { color: #1A1A1A !important; }
    .stButton > button {
        background-color: #E65100; color: #FFFFFF; border: 2px solid #000000;
        border-radius: 8px; padding: 12px 30px; font-size: 1.1rem; font-weight: 700; transition: all 0.3s;
    }
    .stButton > button:hover { background-color: #BF360C; color: #FFFFFF; border-color: #000000; }
    .stDownloadButton > button { background-color: #FFFFFF; color: #1B5E20; border: 1px solid #1B5E20; border-radius: 8px; font-weight: 600; }
    .stDownloadButton > button:hover { background-color: #1B5E20; color: #FFFFFF; }
    [data-testid="stExpander"] { background-color: #F9F9F9; border: 1px solid #C9A84C; border-radius: 8px; }
    .stTextArea > div > div > textarea { background-color: #FFFFFF; color: #1A1A1A; border: 1px solid #C9A84C; border-radius: 8px; }
    .stTextInput > div > div > input { background-color: #FFFFFF; color: #1A1A1A; border: 1px solid #C9A84C; border-radius: 8px; }
    hr { border-color: #C9A84C; opacity: 0.5; }
    .custom-warning { background-color: #FFF3CD; border-left: 4px solid #C9A84C; border-radius: 8px; padding: 12px 16px; color: #856404; font-size: 0.9rem; margin: 10px 0; }
    h2, h3 { color: #1B5E20 !important; }
    p { color: #1A1A1A; }
    label { color: #1A1A1A !important; }
</style>
""", unsafe_allow_html=True)


def color_fila(row):
    if row["Resultado"] == VERDE:      return ["background-color: #E8F5E9; color: #1B5E20"] * len(row)
    elif row["Resultado"] == AMARILLO: return ["background-color: #FFF8E1; color: #856404"] * len(row)
    elif row["Resultado"] == ROJO:     return ["background-color: #FFEBEE; color: #B71C1C"] * len(row)
    return ["background-color: #F5F5F5; color: #555555"] * len(row)


def color_fila_hist(row):
    if "VERDE" in str(row["Veredicto"]):    return ["background-color: #E8F5E9; color: #1B5E20"] * len(row)
    elif "AMARILLO" in str(row["Veredicto"]): return ["background-color: #FFF8E1; color: #856404"] * len(row)
    elif "ROJO" in str(row["Veredicto"]):   return ["background-color: #FFEBEE; color: #B71C1C"] * len(row)
    return [""] * len(row)


def generar_pdf(ddjj, informe, resultados, veredicto, observaciones, ahora, analista=""):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    elementos = []
    styles = getSampleStyleSheet()
    titulo  = ParagraphStyle("titulo", parent=styles["Title"], fontSize=14,
                              textColor=colors.HexColor("#1B5E20"), alignment=TA_CENTER, spaceAfter=6)
    sub     = ParagraphStyle("sub", parent=styles["Normal"], fontSize=9,
                              alignment=TA_CENTER, textColor=colors.grey, spaceAfter=4)
    normal  = ParagraphStyle("normal", parent=styles["Normal"], fontSize=9, spaceAfter=4)
    bold    = ParagraphStyle("bold", parent=styles["Normal"], fontSize=9,
                              fontName="Helvetica-Bold", spaceAfter=4)

    if os.path.exists("IPVUMODELO.png"):
        elementos.append(Image("IPVUMODELO.png", width=3*cm, height=3*cm))
    elementos.append(Paragraph("Sistema de Detección de Inconsistencias", titulo))
    elementos.append(Paragraph("Instituto Provincial de Vivienda y Urbanismo — Santiago del Estero", sub))
    elementos.append(Paragraph(f"Análisis realizado el {ahora}", sub))
    if analista:
        elementos.append(Paragraph(f"Analista: {analista}", sub))
    elementos.append(Spacer(1, 0.4*cm))

    adv = Table([[Paragraph(
        "Todos los documentos y datos analizados son ficticios y de uso exclusivamente académico.",
        ParagraphStyle("adv", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#856404"))
    )]], colWidths=[17*cm])
    adv.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#FFF3CD")),
        ("BOX",(0,0),(-1,-1),0.5,colors.HexColor("#856404")),
        ("LEFTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
    ]))
    elementos.append(adv)
    elementos.append(Spacer(1, 0.4*cm))

    elementos.append(Paragraph("Datos del titular", bold))
    dt = Table([
        [Paragraph("<b>DJ N°:</b>", normal), Paragraph(str(ddjj.get("dj_numero") or ""), normal),
         Paragraph("<b>DNI:</b>", normal), Paragraph(str(ddjj.get("dni_titular") or ""), normal)],
        [Paragraph("<b>Nombre:</b>", normal), Paragraph(str(ddjj.get("nombre_titular") or ""), normal),
         Paragraph("<b>Integrantes:</b>", normal), Paragraph(str(ddjj.get("cantidad_integrantes") or ""), normal)],
    ], colWidths=[3*cm, 5*cm, 3*cm, 6*cm])
    dt.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.5,colors.grey),("INNERGRID",(0,0),(-1,-1),0.25,colors.lightgrey),
        ("LEFTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]))
    elementos.append(dt)
    elementos.append(Spacer(1, 0.4*cm))

    elementos.append(Paragraph("Resultado por campo", bold))
    enc = [Paragraph(f"<b>{c}</b>", normal) for c in ["Campo","DDJJ","Informe","Resultado","Detalle"]]
    filas = [enc]
    cfila = [colors.HexColor("#1B5E20")]
    for r in resultados:
        cf = colors.HexColor("#E8F5E9") if r["resultado"]==VERDE else \
             colors.HexColor("#FFF8E1") if r["resultado"]==AMARILLO else \
             colors.HexColor("#FFEBEE") if r["resultado"]==ROJO else colors.white
        cfila.append(cf)
        filas.append([Paragraph(str(r[k] or ""), normal) for k in ["campo","ddjj","informe","resultado","detalle"]])

    ts = Table(filas, colWidths=[3*cm,3*cm,3.5*cm,2.5*cm,5*cm])
    est = [
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1B5E20")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),
        ("BOX",(0,0),(-1,-1),0.5,colors.grey),("INNERGRID",(0,0),(-1,-1),0.25,colors.lightgrey),
        ("LEFTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),4),
        ("BOTTOMPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]
    for i, cf in enumerate(cfila[1:], start=1):
        est.append(("BACKGROUND",(0,i),(-1,i),cf))
    ts.setStyle(TableStyle(est))
    elementos.append(ts)
    elementos.append(Spacer(1, 0.4*cm))

    cv = colors.HexColor("#E8F5E9") if veredicto==VERDE else \
         colors.HexColor("#FFF8E1") if veredicto==AMARILLO else colors.HexColor("#FFEBEE")
    tv = "✅ SIN INCONSISTENCIAS" if veredicto==VERDE else \
         "⚠️ REVISAR CAMPOS AMARILLOS" if veredicto==AMARILLO else "❌ SE DETECTARON INCONSISTENCIAS"
    vt = Table([[Paragraph(f"Veredicto general: {tv}",
        ParagraphStyle("verd", parent=styles["Normal"], fontSize=10, fontName="Helvetica-Bold")
    )]], colWidths=[17*cm])
    vt.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),cv),("BOX",(0,0),(-1,-1),0.5,colors.grey),
        ("LEFTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),
    ]))
    elementos.append(vt)

    if observaciones:
        elementos.append(Spacer(1, 0.4*cm))
        elementos.append(Paragraph("Observaciones del analista", bold))
        elementos.append(Paragraph(observaciones, normal))

    doc.build(elementos)
    buffer.seek(0)
    return buffer


def generar_pdf_multiple(resumen, ahora):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles   = getSampleStyleSheet()
    normal_m = ParagraphStyle("nm", parent=styles["Normal"], fontSize=9, spaceAfter=4)
    bold_m   = ParagraphStyle("bm", parent=styles["Normal"], fontSize=10, fontName="Helvetica-Bold", spaceAfter=4)
    titulo_m = ParagraphStyle("tm", parent=styles["Title"], fontSize=13,
                               textColor=colors.HexColor("#1B5E20"), alignment=TA_CENTER, spaceAfter=6)
    sub_m    = ParagraphStyle("sm", parent=styles["Normal"], fontSize=8, alignment=TA_CENTER, textColor=colors.grey)

    elems = []
    if os.path.exists("IPVUMODELO.png"):
        elems.append(Image("IPVUMODELO.png", width=3*cm, height=3*cm))
    elems.append(Paragraph("Informe de Análisis Múltiple", titulo_m))
    elems.append(Paragraph(f"Instituto Provincial de Vivienda y Urbanismo — {ahora}", sub_m))
    elems.append(Spacer(1, 0.5*cm))

    for item in resumen:
        elems.append(Paragraph(f"Caso {item['Caso']} — {item['Titular']} (DJ N°: {item['DJ N°']})", bold_m))
        elems.append(Paragraph(f"Veredicto: {item['Veredicto']}", normal_m))
        if item["resultados_detalle"]:
            enc = [Paragraph(f"<b>{c}</b>", normal_m) for c in ["Campo","DDJJ","Informe","Resultado","Detalle"]]
            filas_m = [enc]
            cols_m  = [colors.HexColor("#1B5E20")]
            for r in item["resultados_detalle"]:
                cf = colors.HexColor("#E8F5E9") if r["resultado"]==VERDE else \
                     colors.HexColor("#FFF8E1") if r["resultado"]==AMARILLO else \
                     colors.HexColor("#FFEBEE") if r["resultado"]==ROJO else colors.white
                cols_m.append(cf)
                filas_m.append([Paragraph(str(r[k] or ""), normal_m) for k in ["campo","ddjj","informe","resultado","detalle"]])
            t = Table(filas_m, colWidths=[3*cm,3*cm,3.5*cm,2.5*cm,5*cm])
            est = [
                ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1B5E20")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),
                ("BOX",(0,0),(-1,-1),0.5,colors.grey),("INNERGRID",(0,0),(-1,-1),0.25,colors.lightgrey),
                ("LEFTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),4),
                ("BOTTOMPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ]
            for idx, cf in enumerate(cols_m[1:], start=1):
                est.append(("BACKGROUND",(0,idx),(-1,idx),cf))
            t.setStyle(TableStyle(est))
            elems.append(t)
        elems.append(Spacer(1, 0.3*cm))
        elems.append(PageBreak())

    doc.build(elems)
    buffer.seek(0)
    return buffer


def generar_pdf_historial(historial):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles   = getSampleStyleSheet()
    normal_h = ParagraphStyle("nh", parent=styles["Normal"], fontSize=8, spaceAfter=4)
    titulo_h = ParagraphStyle("th", parent=styles["Title"], fontSize=13,
                               textColor=colors.HexColor("#1B5E20"), alignment=TA_CENTER, spaceAfter=6)
    sub_h    = ParagraphStyle("sh", parent=styles["Normal"], fontSize=8,
                               alignment=TA_CENTER, textColor=colors.grey, spaceAfter=4)

    elems_h = []
    if os.path.exists("IPVUMODELO.png"):
        elems_h.append(Image("IPVUMODELO.png", width=3*cm, height=3*cm))
    elems_h.append(Paragraph("Historial de Análisis", titulo_h))
    elems_h.append(Paragraph("Instituto Provincial de Vivienda y Urbanismo — Santiago del Estero", sub_h))
    elems_h.append(Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}", sub_h))
    elems_h.append(Spacer(1, 0.5*cm))

    enc_h = [Paragraph(f"<b>{c}</b>", normal_h)
             for c in ["Fecha","Titular","DJ N°","Analista","Estado","Veredicto","🔴","🟡","🟢"]]
    filas_h = [enc_h]
    for r in historial:
        filas_h.append([
            Paragraph(str(r.get("fecha","") or ""), normal_h),
            Paragraph(str(r.get("nombre_titular","") or ""), normal_h),
            Paragraph(str(r.get("dj_numero","") or ""), normal_h),
            Paragraph(str(r.get("analista","") or ""), normal_h),
            Paragraph(str(r.get("estado","") or ""), normal_h),
            Paragraph(str(r.get("veredicto","") or ""), normal_h),
            Paragraph(str(r.get("cant_rojo","") or ""), normal_h),
            Paragraph(str(r.get("cant_amarillo","") or ""), normal_h),
            Paragraph(str(r.get("cant_verde","") or ""), normal_h),
        ])

    t_hist = Table(filas_h, colWidths=[3*cm,3.5*cm,1.5*cm,2.5*cm,2*cm,2*cm,0.8*cm,0.8*cm,0.8*cm])
    t_hist.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1B5E20")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),7),
        ("BOX",(0,0),(-1,-1),0.5,colors.grey),
        ("INNERGRID",(0,0),(-1,-1),0.25,colors.lightgrey),
        ("LEFTPADDING",(0,0),(-1,-1),4),
        ("TOPPADDING",(0,0),(-1,-1),3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#F9F9F9")]),
    ]))
    elems_h.append(t_hist)
    doc.build(elems_h)
    buffer.seek(0)
    return buffer


if "bienvenida_vista" not in st.session_state:
    st.session_state.bienvenida_vista = False
if "confirmar_limpieza" not in st.session_state:
    st.session_state.confirmar_limpieza = False


# ══════════════════════════════════════════
#  PANTALLA DE BIENVENIDA
# ══════════════════════════════════════════
if not st.session_state.bienvenida_vista:
    col_iz, col_centro, col_der = st.columns([1, 2, 1])
    with col_centro:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if os.path.exists("IPVUMODELO.png"):
            col_l, col_img, col_r = st.columns([1, 1, 1])
            with col_img:
                st.image("IPVUMODELO.png", width=180)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="main-title">Sistema de Detección de Inconsistencias</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title">Instituto Provincial de Vivienda y Urbanismo<br>Santiago del Estero</div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="color:#555;font-size:0.95rem;margin:20px 0;line-height:1.8;text-align:center;">
            Este sistema compara automáticamente las <strong style="color:#1B5E20;">Declaraciones Juradas</strong>
            con los <strong style="color:#1B5E20;">Informes Sociohabitacionales</strong> del IPVU,
            detectando inconsistencias campo por campo mediante un modelo de semáforo.
        </div>""", unsafe_allow_html=True)
        st.markdown('<div class="custom-warning">⚠️ Todos los documentos y datos analizados son ficticios y de uso exclusivamente académico.</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        col_btn = st.columns([1, 2, 1])[1]
        with col_btn:
            if st.button("🏠  Ingresar al sistema", use_container_width=True):
                st.session_state.bienvenida_vista = True
                st.rerun()
        st.markdown("""
        <div style="margin-top:40px;padding:20px;border:1px solid #C9A84C;border-radius:12px;
                    background-color:#F9F9F9;text-align:center;box-shadow:0 4px 15px rgba(0,0,0,0.08);">
            <div style="color:#1B5E20;font-size:0.85rem;font-weight:700;letter-spacing:1px;margin-bottom:10px;">
                PRÁCTICA PROFESIONALIZANTE</div>
            <div style="color:#1A1A1A;font-size:1.05rem;font-weight:600;margin-bottom:4px;">
                Daniela Fernández &nbsp;·&nbsp; Julio Nahuel Gómez</div>
            <div style="color:#555;font-size:0.85rem;margin-bottom:4px;">
                Tecnicatura Superior en Ciencia de Datos e Inteligencia Artificial</div>
            <div style="color:#555;font-size:0.85rem;">Instituto Tecnológico de Santiago del Estero — 2026</div>
        </div>""", unsafe_allow_html=True)
        st.markdown("<br><br>", unsafe_allow_html=True)


# ══════════════════════════════════════════
#  SISTEMA PRINCIPAL
# ══════════════════════════════════════════
else:
    col_logo, col_titulo = st.columns([1, 5])
    with col_logo:
        if os.path.exists("IPVUMODELO.png"):
            st.image("IPVUMODELO.png", width=120)
    with col_titulo:
        st.markdown('<div class="main-title" style="text-align:left;font-size:1.6rem;">Sistema de Detección de Inconsistencias</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title" style="text-align:left;">Instituto Provincial de Vivienda y Urbanismo — Santiago del Estero</div>', unsafe_allow_html=True)

    st.markdown('<div class="header-line"></div>', unsafe_allow_html=True)
    st.markdown('<div class="custom-warning">⚠️ Todos los documentos y datos analizados en este sistema son ficticios y de uso exclusivamente académico. No corresponden a personas reales.</div>', unsafe_allow_html=True)
    st.markdown('<div class="header-line"></div>', unsafe_allow_html=True)

    pagina = st.sidebar.selectbox("Navegación",
        ["🔍 Analizar caso", "📦 Analizar múltiples casos", "📋 Historial", "📊 Estadísticas"])

    cant_hist = 0
    if os.path.exists("historial.json"):
        try:
            with open("historial.json","r",encoding="utf-8") as f:
                cant_hist = len(json.load(f))
        except:
            pass

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"""
    <div style="text-align:center;">
        <div style="background:#C9A84C;color:#1A237E;font-weight:700;
                    border-radius:8px;padding:8px 12px;font-size:0.9rem;">
            📋 {cant_hist} caso{'s' if cant_hist != 1 else ''} en historial
        </div>
    </div>""", unsafe_allow_html=True)
    st.sidebar.markdown("---")
    if st.sidebar.button("🏠 Volver a inicio"):
        st.session_state.bienvenida_vista = False
        st.rerun()

    # ════════════════════════════════════════
    #  PÁGINA 1 — ANALIZAR CASO
    # ════════════════════════════════════════
    if pagina == "🔍 Analizar caso":
        st.subheader("🔍 Analizar caso")
        st.markdown('<div class="sub-title" style="text-align:left;">Subí los dos documentos. La DDJJ es la fuente de verdad.</div>', unsafe_allow_html=True)

        nombre_analista = st.text_input("👤 Nombre del analista",
            placeholder="Ej: María López",
            help="Este nombre quedará registrado junto con el análisis.")

        col1, col2 = st.columns(2)
        with col1:
            archivo_ddjj = st.file_uploader("📄 Declaración Jurada (DDJJ)", type="pdf")
            if archivo_ddjj:
                try:
                    contenido_prev = archivo_ddjj.read()
                    archivo_ddjj.seek(0)
                    imgs = convert_from_bytes(contenido_prev, dpi=80, poppler_path=POPPLER_PATH)
                    st.image(imgs[0], caption="Vista previa DDJJ", use_container_width=True)
                except Exception:
                    st.caption("Vista previa no disponible.")
        with col2:
            archivo_informe = st.file_uploader("📋 Informe Sociohabitacional", type="pdf")
            if archivo_informe:
                try:
                    contenido_prev = archivo_informe.read()
                    archivo_informe.seek(0)
                    imgs = convert_from_bytes(contenido_prev, dpi=80, poppler_path=POPPLER_PATH)
                    st.image(imgs[0], caption="Vista previa Informe", use_container_width=True)
                except Exception:
                    st.caption("Vista previa no disponible.")

        if archivo_ddjj and archivo_informe:
            progreso = st.progress(0, text="Iniciando análisis...")
            time.sleep(0.3)
            progreso.progress(20, text="Leyendo DDJJ...")
            try:
                ddjj = extraer_ddjj(archivo_ddjj)
            except Exception as ex:
                st.error(f"Error al leer la DDJJ: {ex}")
                st.stop()

            progreso.progress(50, text="Leyendo Informe Sociohabitacional...")
            time.sleep(0.3)
            try:
                informe = extraer_informe(archivo_informe)
            except Exception as ex:
                st.error(f"Error al leer el Informe: {ex}")
                st.stop()

            progreso.progress(100, text="¡Extracción completada!")
            time.sleep(0.5)
            progreso.empty()

            ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            st.caption(f"🕐 Análisis realizado el {ahora} — Analista: {nombre_analista if nombre_analista else 'No especificado'}")

            with st.expander("✏️ Revisar y corregir datos extraídos (opcional)", expanded=False):
                st.markdown("Si el sistema leyó mal algún campo podés corregirlo acá antes de comparar.")
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    st.markdown("**DDJJ**")
                    ddjj["dj_numero"]           = st.text_input("DJ N°", value=str(ddjj.get("dj_numero") or ""), key="ed_dj")
                    ddjj["nombre_titular"]       = st.text_input("Nombre Titular", value=str(ddjj.get("nombre_titular") or ""), key="ed_nombre")
                    ddjj["dni_titular"]          = st.text_input("DNI Titular", value=str(ddjj.get("dni_titular") or ""), key="ed_dni")
                    ddjj["cantidad_integrantes"] = st.number_input("Integrantes", value=int(ddjj.get("cantidad_integrantes") or 0), key="ed_integ", min_value=0)
                    ddjj["ingresos_total"]       = st.number_input("Ingresos", value=float(ddjj.get("ingresos_total") or 0), key="ed_ing", min_value=0.0)
                with col_e2:
                    st.markdown("**Informe**")
                    informe["dj_numero"]           = st.text_input("DJ N°", value=str(informe.get("dj_numero") or ""), key="ei_dj")
                    informe["nombre_titular"]       = st.text_input("Nombre Titular", value=str(informe.get("nombre_titular") or ""), key="ei_nombre")
                    informe["dni_titular"]          = st.text_input("DNI Titular", value=str(informe.get("dni_titular") or ""), key="ei_dni")
                    informe["cantidad_integrantes"] = st.number_input("Integrantes", value=int(informe.get("cantidad_integrantes") or 0), key="ei_integ", min_value=0)
                    informe["ingresos_total"]       = st.number_input("Ingresos", value=float(informe.get("ingresos_total") or 0), key="ei_ing", min_value=0.0)

            fecha_insc = ddjj.get("fecha_inscripcion")
            if fecha_insc:
                try:
                    fecha_insc_dt = datetime.strptime(fecha_insc, "%d/%m/%Y")
                    dias = (datetime.now() - fecha_insc_dt).days
                    st.info(f"📅 Días transcurridos desde la inscripción ({fecha_insc}): **{dias} días** ({dias // 365} años y {dias % 365} días)")
                except:
                    pass

            with st.expander("🔍 Ver datos extraídos", expanded=False):
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("DDJJ")
                    st.json({k: v for k, v in ddjj.items() if k != "integrantes"})
                with c2:
                    st.subheader("Informe")
                    st.json(informe)

            resultados, veredicto, alerta_dj = comparar(ddjj, informe)

            if alerta_dj:
                st.error("⚠️ Los DJ N° no coinciden. Verificar que sean documentos del mismo caso.")

            cant_rojo     = sum(1 for r in resultados if r["resultado"] == ROJO)
            cant_amarillo = sum(1 for r in resultados if r["resultado"] == AMARILLO)
            cant_verde    = sum(1 for r in resultados if r["resultado"] == VERDE)

            m1, m2, m3 = st.columns(3)
            m1.metric("🟢 Sin inconsistencia", cant_verde)
            m2.metric("🟡 Revisar", cant_amarillo)
            m3.metric("🔴 Con inconsistencia", cant_rojo)

            st.subheader("📊 Resultado por campo")
            df = pd.DataFrame(resultados)[["campo","ddjj","informe","resultado","detalle"]]
            df.columns = ["Campo","DDJJ","Informe","Resultado","Detalle"]
            st.dataframe(df.style.apply(color_fila, axis=1), use_container_width=True, hide_index=True)

            st.subheader("📈 Distribución de resultados")
            fig = px.pie(
                pd.DataFrame({"Estado":["Verde","Amarillo","Rojo"],"Cantidad":[cant_verde,cant_amarillo,cant_rojo]}),
                values="Cantidad", names="Estado", color="Estado",
                color_discrete_map={"Verde":"#2E7D32","Amarillo":"#C9A84C","Rojo":"#B71C1C"}, hole=0.4)
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#1A1A1A", legend=dict(font=dict(color="#1A1A1A")))
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("📝 Observaciones del analista")
            observaciones = st.text_area("Escribí tus observaciones:", height=100,
                placeholder="Ej: El titular declaró ingresos distintos en ambos documentos.")

            st.divider()

            if veredicto == VERDE:
                st.success(f"✅ Veredicto general: {veredicto} — Sin inconsistencias detectadas.")
            elif veredicto == AMARILLO:
                st.warning(f"⚠️ Veredicto general: {veredicto} — Revisar campos amarillos.")
            else:
                st.error(f"❌ Veredicto general: {veredicto} — Se detectaron inconsistencias.")

            st.subheader("⬇️ Descargar resultado")
            col_excel, col_pdf = st.columns(2)
            with col_excel:
                buffer_excel = io.BytesIO()
                with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="Semaforo")
                st.download_button("📥 Descargar como Excel", data=buffer_excel.getvalue(),
                    file_name=f"semaforo_{ddjj.get('dj_numero','caso')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            with col_pdf:
                buffer_pdf = generar_pdf(ddjj, informe, resultados, veredicto, observaciones, ahora, nombre_analista)
                st.download_button("📄 Descargar informe PDF", data=buffer_pdf,
                    file_name=f"informe_{ddjj.get('dj_numero','caso')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf")

            registro = {
                "fecha": ahora, "dj_numero": ddjj.get("dj_numero"),
                "nombre_titular": ddjj.get("nombre_titular"), "veredicto": veredicto,
                "cant_rojo": cant_rojo, "cant_amarillo": cant_amarillo, "cant_verde": cant_verde,
                "observaciones": observaciones, "resultados": resultados,
                "analista": nombre_analista if nombre_analista else "No especificado",
                "estado": "⏳ Pendiente",
                "fecha_inscripcion": ddjj.get("fecha_inscripcion")
            }
            historial = []
            if os.path.exists("historial.json"):
                with open("historial.json","r",encoding="utf-8") as f:
                    historial = json.load(f)
            historial.append(registro)
            with open("historial.json","w",encoding="utf-8") as f:
                json.dump(historial, f, ensure_ascii=False, indent=2)

        else:
            st.markdown("""
            <div class="card" style="text-align:center;padding:40px;">
                <div style="font-size:3rem;margin-bottom:15px;">📂</div>
                <div style="color:#1B5E20;font-size:1.1rem;font-weight:600;">Subí los dos PDFs para comenzar el análisis</div>
                <div style="color:#555;font-size:0.9rem;margin-top:8px;">El sistema comparará automáticamente los campos de ambos documentos</div>
            </div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════
    #  PÁGINA 2 — MÚLTIPLES CASOS
    # ════════════════════════════════════════
    elif pagina == "📦 Analizar múltiples casos":
        st.subheader("📦 Analizar múltiples casos")
        st.markdown('<div class="sub-title" style="text-align:left;">El sistema empareja por orden: primera DDJJ con primer Informe.</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            archivos_ddjj = st.file_uploader("📄 Declaraciones Juradas (DDJJ)", type="pdf", accept_multiple_files=True)
        with col2:
            archivos_informe = st.file_uploader("📋 Informes Sociohabitacionales", type="pdf", accept_multiple_files=True)

        if archivos_ddjj and archivos_informe:
            if len(archivos_ddjj) != len(archivos_informe):
                st.error(f"⚠️ Subiste {len(archivos_ddjj)} DDJJ y {len(archivos_informe)} Informes. Tienen que ser la misma cantidad.")
            else:
                st.success(f"✅ {len(archivos_ddjj)} pares detectados. Listo para analizar.")
                if st.button("🚀 Analizar todos los casos"):
                    ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    resumen = []
                    historial = []
                    if os.path.exists("historial.json"):
                        with open("historial.json","r",encoding="utf-8") as f:
                            historial = json.load(f)

                    progreso = st.progress(0, text="Iniciando análisis múltiple...")
                    for i, (arch_ddjj, arch_inf) in enumerate(zip(archivos_ddjj, archivos_informe)):
                        pct = int((i / len(archivos_ddjj)) * 100)
                        progreso.progress(pct, text=f"Procesando caso {i+1} de {len(archivos_ddjj)}...")
                        try:
                            ddjj    = extraer_ddjj(arch_ddjj)
                            informe = extraer_informe(arch_inf)
                            resultados, veredicto, alerta_dj = comparar(ddjj, informe)
                            cant_rojo     = sum(1 for r in resultados if r["resultado"] == ROJO)
                            cant_amarillo = sum(1 for r in resultados if r["resultado"] == AMARILLO)
                            cant_verde    = sum(1 for r in resultados if r["resultado"] == VERDE)
                            resumen.append({
                                "Caso": i+1, "Archivo DDJJ": arch_ddjj.name,
                                "Archivo Informe": arch_inf.name,
                                "DJ N°": ddjj.get("dj_numero"),
                                "Titular": ddjj.get("nombre_titular"),
                                "Veredicto": veredicto,
                                "🟢 Verdes": cant_verde, "🟡 Amarillos": cant_amarillo, "🔴 Rojos": cant_rojo,
                                "resultados_detalle": resultados
                            })
                            historial.append({
                                "fecha": ahora, "dj_numero": ddjj.get("dj_numero"),
                                "nombre_titular": ddjj.get("nombre_titular"),
                                "veredicto": veredicto, "cant_rojo": cant_rojo,
                                "cant_amarillo": cant_amarillo, "cant_verde": cant_verde,
                                "observaciones": "", "resultados": resultados,
                                "analista": "Análisis múltiple", "estado": "⏳ Pendiente",
                                "fecha_inscripcion": ddjj.get("fecha_inscripcion")
                            })
                        except Exception as ex:
                            resumen.append({
                                "Caso": i+1, "Archivo DDJJ": arch_ddjj.name,
                                "Archivo Informe": arch_inf.name,
                                "DJ N°": "ERROR", "Titular": str(ex),
                                "Veredicto": "⚪ ERROR",
                                "🟢 Verdes": 0, "🟡 Amarillos": 0, "🔴 Rojos": 0,
                                "resultados_detalle": []
                            })

                    progreso.progress(100, text="¡Análisis completado!")
                    time.sleep(0.5)
                    progreso.empty()

                    with open("historial.json","w",encoding="utf-8") as f:
                        json.dump(historial, f, ensure_ascii=False, indent=2)

                    st.subheader("📊 Resumen de todos los casos")
                    df_resumen = pd.DataFrame([{k: v for k, v in r.items() if k != "resultados_detalle"} for r in resumen])

                    def color_veredicto(row):
                        if VERDE in str(row["Veredicto"]):      return ["background-color: #E8F5E9; color: #1B5E20"] * len(row)
                        elif AMARILLO in str(row["Veredicto"]): return ["background-color: #FFF8E1; color: #856404"] * len(row)
                        elif ROJO in str(row["Veredicto"]):     return ["background-color: #FFEBEE; color: #B71C1C"] * len(row)
                        return [""] * len(row)

                    st.dataframe(df_resumen.style.apply(color_veredicto, axis=1),
                                 use_container_width=True, hide_index=True)

                    st.subheader("🔍 Detalle por caso")
                    for item in resumen:
                        with st.expander(f"Caso {item['Caso']} — {item['Titular']} — {item['Veredicto']}"):
                            if item["resultados_detalle"]:
                                df_det = pd.DataFrame(item["resultados_detalle"])[["campo","ddjj","informe","resultado","detalle"]]
                                df_det.columns = ["Campo","DDJJ","Informe","Resultado","Detalle"]
                                st.dataframe(df_det.style.apply(color_fila, axis=1),
                                            use_container_width=True, hide_index=True)
                            else:
                                st.error("No se pudo procesar este caso.")

                    total     = len(resumen)
                    casos_ok  = sum(1 for r in resumen if VERDE in str(r["Veredicto"]))
                    casos_mal = sum(1 for r in resumen if ROJO in str(r["Veredicto"]))
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total analizados", total)
                    m2.metric("🟢 Sin inconsistencias", casos_ok)
                    m3.metric("🔴 Con inconsistencias", casos_mal)

                    st.subheader("⬇️ Descargar resultados")
                    col_dl1, col_dl2 = st.columns(2)
                    with col_dl1:
                        buffer_excel = io.BytesIO()
                        with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
                            df_resumen.to_excel(writer, index=False, sheet_name="Resumen")
                        st.download_button("📥 Descargar resumen como Excel",
                            data=buffer_excel.getvalue(),
                            file_name=f"resumen_multiple_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    with col_dl2:
                        buffer_pdf_multi = generar_pdf_multiple(resumen, ahora)
                        st.download_button("📄 Descargar informe PDF",
                            data=buffer_pdf_multi,
                            file_name=f"informe_multiple_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                            mime="application/pdf")
        else:
            st.markdown("""
            <div class="card" style="text-align:center;padding:40px;">
                <div style="font-size:3rem;margin-bottom:15px;">📦</div>
                <div style="color:#1B5E20;font-size:1.1rem;font-weight:600;">Subí los pares de PDFs para comenzar</div>
                <div style="color:#555;font-size:0.9rem;margin-top:8px;">Seleccioná múltiples archivos con Ctrl + clic</div>
            </div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════
    #  PÁGINA 3 — HISTORIAL
    # ════════════════════════════════════════
    elif pagina == "📋 Historial":
        st.subheader("📋 Historial de análisis")

        if not os.path.exists("historial.json"):
            st.markdown("""
            <div class="card" style="text-align:center;padding:40px;">
                <div style="font-size:3rem;margin-bottom:15px;">📋</div>
                <div style="color:#1B5E20;">Todavía no hay casos analizados.</div>
            </div>""", unsafe_allow_html=True)
        else:
            with open("historial.json","r",encoding="utf-8") as f:
                historial = json.load(f)

            if not historial:
                st.info("Todavía no hay casos analizados.")
            else:
                st.markdown("**🔎 Filtros**")
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    filtro_veredicto = st.selectbox("Veredicto", ["Todos","🟢 VERDE","🟡 AMARILLO","🔴 ROJO"])
                with col_f2:
                    filtro_estado = st.selectbox("Estado", ["Todos","⏳ Pendiente","✅ Revisado"])
                with col_f3:
                    filtro_busqueda = st.text_input("Buscar por titular o DJ N°", placeholder="Ej: Juan Pérez o 12345")

                st.divider()

                for idx, r in enumerate(historial):
                    estado_actual = r.get("estado", "⏳ Pendiente")
                    veredicto_ok  = filtro_veredicto == "Todos" or filtro_veredicto.split(" ", 1)[-1] in r["veredicto"]
                    estado_ok     = filtro_estado == "Todos" or filtro_estado == estado_actual
                    busqueda_ok   = (filtro_busqueda == "" or
                                     filtro_busqueda.lower() in str(r.get("nombre_titular","")).lower() or
                                     filtro_busqueda.lower() in str(r.get("dj_numero","")).lower())

                    if not (veredicto_ok and estado_ok and busqueda_ok):
                        continue

                    color_borde = "#2E7D32" if "VERDE" in r["veredicto"] else \
                                  "#C9A84C" if "AMARILLO" in r["veredicto"] else "#B71C1C"

                    dias_str = ""
                    fecha_insc = r.get("fecha_inscripcion")
                    if fecha_insc:
                        try:
                            fecha_insc_dt = datetime.strptime(fecha_insc, "%d/%m/%Y")
                            dias = (datetime.now() - fecha_insc_dt).days
                            dias_str = f"&nbsp;|&nbsp; 📅 {dias} días desde inscripción"
                        except:
                            pass

                    with st.container():
                        st.markdown(f"""
                        <div style="border-left:4px solid {color_borde};padding:10px 16px;
                                    background:#F9F9F9;border-radius:8px;margin-bottom:8px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <div>
                                    <span style="font-weight:700;color:#1A1A1A;font-size:1rem;">
                                        {r.get('nombre_titular','—')}</span>
                                    <span style="color:#555;font-size:0.85rem;margin-left:10px;">
                                        DJ N°: {r.get('dj_numero','—')}</span>
                                </div>
                                <div style="font-size:0.8rem;color:#888;">{r['fecha']}</div>
                            </div>
                            <div style="margin-top:4px;font-size:0.85rem;">
                                {r['veredicto']} &nbsp;|&nbsp;
                                Analista: {r.get('analista','No especificado')} &nbsp;|&nbsp;
                                🔴 {r['cant_rojo']} &nbsp; 🟡 {r['cant_amarillo']} &nbsp; 🟢 {r['cant_verde']}
                                {dias_str}
                            </div>
                        </div>""", unsafe_allow_html=True)

                        col_est, col_obs = st.columns([1, 3])
                        with col_est:
                            nuevo_estado = st.selectbox(
                                "Estado",
                                ["⏳ Pendiente", "✅ Revisado"],
                                index=0 if estado_actual == "⏳ Pendiente" else 1,
                                key=f"estado_{idx}"
                            )
                            if nuevo_estado != estado_actual:
                                historial[idx]["estado"] = nuevo_estado
                                with open("historial.json","w",encoding="utf-8") as f:
                                    json.dump(historial, f, ensure_ascii=False, indent=2)
                                st.rerun()
                        with col_obs:
                            if r.get("observaciones"):
                                st.caption(f"📝 {r['observaciones']}")

                # ── Línea de tiempo ──
                st.divider()
                st.subheader("🕐 Línea de tiempo")
                historial_ordenado = sorted(historial, key=lambda x: x["fecha"], reverse=False)
                for r in historial_ordenado:
                    if "VERDE" in r["veredicto"]:
                        color_punto = "#2E7D32"; icono = "🟢"
                    elif "AMARILLO" in r["veredicto"]:
                        color_punto = "#C9A84C"; icono = "🟡"
                    else:
                        color_punto = "#B71C1C"; icono = "🔴"

                    st.markdown(f"""
                    <div style="display:flex;align-items:flex-start;margin-bottom:8px;">
                        <div style="display:flex;flex-direction:column;align-items:center;margin-right:16px;">
                            <div style="width:16px;height:16px;border-radius:50%;
                                        background:{color_punto};margin-top:4px;flex-shrink:0;"></div>
                            <div style="width:2px;background:#E0E0E0;flex:1;margin-top:4px;min-height:30px;"></div>
                        </div>
                        <div style="background:#F9F9F9;border-radius:8px;padding:8px 14px;
                                    flex:1;border:1px solid #E0E0E0;margin-bottom:4px;">
                            <div style="font-size:0.8rem;color:#888;margin-bottom:2px;">{r['fecha']}</div>
                            <div style="font-weight:600;color:#1A1A1A;font-size:0.95rem;">
                                {icono} {r.get('nombre_titular','—')}
                                <span style="font-weight:400;color:#555;font-size:0.85rem;margin-left:8px;">
                                    DJ N°: {r.get('dj_numero','—')}
                                </span>
                            </div>
                            <div style="font-size:0.8rem;color:#555;margin-top:2px;">
                                Analista: {r.get('analista','No especificado')} &nbsp;|&nbsp;
                                Estado: {r.get('estado','⏳ Pendiente')}
                            </div>
                        </div>
                    </div>""", unsafe_allow_html=True)

                st.divider()

                # ── Limpiar historial ──
                col_limpiar = st.columns([3, 1])[1]
                with col_limpiar:
                    if st.button("🗑️ Limpiar historial"):
                        st.session_state.confirmar_limpieza = True

                if st.session_state.get("confirmar_limpieza"):
                    st.warning("⚠️ ¿Estás segura de que querés borrar todo el historial? Esta acción no se puede deshacer.")
                    col_si, col_no = st.columns(2)
                    with col_si:
                        if st.button("✅ Sí, borrar todo"):
                            with open("historial.json","w",encoding="utf-8") as f:
                                json.dump([], f)
                            st.session_state.confirmar_limpieza = False
                            st.rerun()
                    with col_no:
                        if st.button("❌ Cancelar"):
                            st.session_state.confirmar_limpieza = False
                            st.rerun()

                df_hist = pd.DataFrame([{
                    "Fecha": r["fecha"], "DJ N°": r["dj_numero"],
                    "Titular": r["nombre_titular"],
                    "Analista": r.get("analista","No especificado"),
                    "Estado": r.get("estado","⏳ Pendiente"),
                    "Veredicto": r["veredicto"],
                    "🔴 Rojos": r["cant_rojo"], "🟡 Amarillos": r["cant_amarillo"],
                    "🟢 Verdes": r["cant_verde"], "Observaciones": r.get("observaciones",""),
                    "Fecha Inscripción": r.get("fecha_inscripcion","")
                } for r in historial])

                buffer_hist = io.BytesIO()
                with pd.ExcelWriter(buffer_hist, engine="openpyxl") as writer:
                    df_hist.to_excel(writer, index=False, sheet_name="Historial")

                col_h1, col_h2 = st.columns(2)
                with col_h1:
                    st.download_button("📥 Descargar historial como Excel",
                        data=buffer_hist.getvalue(),
                        file_name=f"historial_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                with col_h2:
                    buffer_hist_pdf = generar_pdf_historial(historial)
                    st.download_button("📄 Descargar historial como PDF",
                        data=buffer_hist_pdf,
                        file_name=f"historial_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf")

    # ════════════════════════════════════════
    #  PÁGINA 4 — ESTADÍSTICAS
    # ════════════════════════════════════════
    elif pagina == "📊 Estadísticas":
        st.subheader("📊 Estadísticas generales")

        if not os.path.exists("historial.json"):
            st.markdown("""
            <div class="card" style="text-align:center;padding:40px;">
                <div style="font-size:3rem;margin-bottom:15px;">📊</div>
                <div style="color:#1B5E20;">Todavía no hay datos para mostrar.</div>
            </div>""", unsafe_allow_html=True)
        else:
            with open("historial.json","r",encoding="utf-8") as f:
                historial = json.load(f)

            if not historial:
                st.info("Todavía no hay casos analizados para mostrar estadísticas.")
            else:
                total           = len(historial)
                casos_con_error = sum(1 for r in historial if r["veredicto"] == ROJO)
                casos_ok        = sum(1 for r in historial if r["veredicto"] == VERDE)

                m1, m2, m3 = st.columns(3)
                m1.metric("Total de casos analizados", total)
                m2.metric("Casos sin inconsistencias", casos_ok)
                m3.metric("Casos con inconsistencias", casos_con_error)

                st.divider()

                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.subheader("Veredictos generales")
                    fig_ver = px.bar(
                        pd.DataFrame({"Veredicto":["Sin inconsistencias","Con inconsistencias"],"Cantidad":[casos_ok,casos_con_error]}),
                        x="Veredicto", y="Cantidad", color="Veredicto",
                        color_discrete_map={"Sin inconsistencias":"#2E7D32","Con inconsistencias":"#B71C1C"})
                    fig_ver.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#1A1A1A", showlegend=False)
                    st.plotly_chart(fig_ver, use_container_width=True)

                with col_g2:
                    st.subheader("Campo que falla más")
                    conteo_campos = {}
                    for r in historial:
                        for res in r.get("resultados",[]):
                            if res["resultado"] == ROJO:
                                conteo_campos[res["campo"]] = conteo_campos.get(res["campo"], 0) + 1

                    if conteo_campos:
                        df_campos = pd.DataFrame(list(conteo_campos.items()),
                            columns=["Campo","Veces con error"]).sort_values("Veces con error", ascending=False)
                        fig_campos = px.bar(df_campos, x="Campo", y="Veces con error",
                            color_discrete_sequence=["#C9A84C"])
                        fig_campos.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#1A1A1A", showlegend=False)
                        st.plotly_chart(fig_campos, use_container_width=True)
                    else:
                        st.success("No se registraron campos con error.")

                # ── Métricas del modelo ──
                st.divider()
                st.subheader("🎯 Métricas del modelo")

                total_campos    = sum(len(r.get("resultados",[])) for r in historial)
                total_rojos     = sum(r["cant_rojo"] for r in historial)
                total_amarillos = sum(r["cant_amarillo"] for r in historial)
                total_verdes    = sum(r["cant_verde"] for r in historial)

                tasa_inconsistencia = round((casos_con_error / total) * 100, 1) if total > 0 else 0
                tasa_ok             = round((casos_ok / total) * 100, 1) if total > 0 else 0
                tasa_error_campo    = round((total_rojos / total_campos) * 100, 1) if total_campos > 0 else 0

                dias_lista = []
                for r in historial:
                    fi = r.get("fecha_inscripcion")
                    if fi:
                        try:
                            dias_lista.append((datetime.now() - datetime.strptime(fi, "%d/%m/%Y")).days)
                        except:
                            pass
                promedio_dias = round(sum(dias_lista) / len(dias_lista)) if dias_lista else None

                conteo_analistas = {}
                for r in historial:
                    a = r.get("analista","No especificado")
                    conteo_analistas[a] = conteo_analistas.get(a, 0) + 1
                analista_top = max(conteo_analistas, key=conteo_analistas.get) if conteo_analistas else "—"
                campo_top    = max(conteo_campos, key=conteo_campos.get) if conteo_campos else "—"

                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("📊 Tasa de inconsistencia", f"{tasa_inconsistencia}%",
                              help="Porcentaje de casos con al menos un campo en ROJO")
                col_m2.metric("✅ Tasa de conformidad", f"{tasa_ok}%",
                              help="Porcentaje de casos completamente en VERDE")
                col_m3.metric("🔴 Tasa de error por campo", f"{tasa_error_campo}%",
                              help="Porcentaje de campos individuales que resultaron en ROJO")

                col_m4, col_m5, col_m6 = st.columns(3)
                col_m4.metric("📅 Promedio días desde inscripción",
                              f"{promedio_dias} días" if promedio_dias else "Sin datos")
                col_m5.metric("⚠️ Campo más conflictivo", campo_top)
                col_m6.metric("👤 Analista más activo",
                              f"{analista_top} ({conteo_analistas.get(analista_top,0)} casos)")

                st.markdown("<br>", unsafe_allow_html=True)
                col_dist1, col_dist2 = st.columns(2)
                with col_dist1:
                    st.subheader("Distribución total de resultados")
                    fig_dist = px.pie(
                        pd.DataFrame({
                            "Estado": ["🟢 Verde","🟡 Amarillo","🔴 Rojo"],
                            "Cantidad": [total_verdes, total_amarillos, total_rojos]
                        }),
                        values="Cantidad", names="Estado", color="Estado",
                        color_discrete_map={
                            "🟢 Verde":"#2E7D32",
                            "🟡 Amarillo":"#C9A84C",
                            "🔴 Rojo":"#B71C1C"
                        }, hole=0.4)
                    fig_dist.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#1A1A1A")
                    st.plotly_chart(fig_dist, use_container_width=True)

                with col_dist2:
                    st.subheader("Casos por analista")
                    if conteo_analistas:
                        df_analistas = pd.DataFrame(list(conteo_analistas.items()),
                            columns=["Analista","Casos"]).sort_values("Casos", ascending=False)
                        fig_analistas = px.bar(df_analistas, x="Analista", y="Casos",
                            color_discrete_sequence=["#1A237E"])
                        fig_analistas.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#1A1A1A", showlegend=False)
                        st.plotly_chart(fig_analistas, use_container_width=True)

                # ── Mapa de calor ──
                st.divider()
                st.subheader("🗓️ Mapa de calor — errores por campo y mes")
                datos_calor = {}
                for r in historial:
                    try:
                        mes = datetime.strptime(r["fecha"], "%d/%m/%Y %H:%M:%S").strftime("%Y-%m")
                    except:
                        continue
                    for res in r.get("resultados", []):
                        if res["resultado"] == ROJO:
                            campo = res["campo"]
                            if campo not in datos_calor:
                                datos_calor[campo] = {}
                            datos_calor[campo][mes] = datos_calor[campo].get(mes, 0) + 1

                if datos_calor:
                    df_calor = pd.DataFrame(datos_calor).T.fillna(0).astype(int)
                    df_calor = df_calor.sort_index(axis=1)
                    fig_calor = px.imshow(
                        df_calor,
                        labels=dict(x="Mes", y="Campo", color="Errores"),
                        color_continuous_scale=["#E8F5E9","#FFF8E1","#FFEBEE","#B71C1C"],
                        aspect="auto", text_auto=True)
                    fig_calor.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#1A1A1A", coloraxis_showscale=True)
                    st.plotly_chart(fig_calor, use_container_width=True)
                else:
                    st.info("Todavía no hay suficientes datos para mostrar el mapa de calor.")