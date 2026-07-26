import pdfplumber
import re
import pytesseract
from pdf2image import convert_from_bytes
import io

pytesseract.pytesseract.tesseract_cmd = r"D:\PROGRAMAS\TESSERACT OCR\tesseract.exe"
POPPLER_PATH = r"D:\PROGRAMAS\poppler-26.02.0\Library\bin"

def limpiar_dni(texto):
    return re.sub(r"\.", "", texto).strip()

def limpiar_monto(texto):
    texto = re.sub(r"[$\s]", "", texto)
    if re.match(r"^\d{1,3}(\.\d{3})+(,\d+)?$", texto):
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", "")
    return float(texto)

def palabras_en_numero(texto):
    m = re.search(r"\((\d+)\)", texto)
    if m:
        return int(m.group(1))
    tabla = {"uno":1,"dos":2,"tres":3,"cuatro":4,"cinco":5,
             "seis":6,"siete":7,"ocho":8,"nueve":9,"diez":10}
    for pal, num in tabla.items():
        if pal in texto.lower():
            return num
    return None

def extraer_texto_pdf(contenido_bytes):
    with pdfplumber.open(io.BytesIO(contenido_bytes)) as pdf:
        texto = pdf.pages[0].extract_text() or ""
    if len(texto.strip()) < 50:
        imagenes = convert_from_bytes(contenido_bytes, dpi=300, poppler_path=POPPLER_PATH)
        texto = pytesseract.image_to_string(imagenes[0], lang="spa")
    return texto

def extraer_ddjj(archivo_pdf):
    contenido = archivo_pdf.read()

    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        pagina = pdf.pages[0]
        texto = pagina.extract_text() or ""
        tablas = pagina.extract_tables()

    if len(texto.strip()) < 50:
        imagenes = convert_from_bytes(contenido, dpi=300, poppler_path=POPPLER_PATH)
        texto = pytesseract.image_to_string(imagenes[0], lang="spa")
        tablas = []

    datos = {}

    m = re.search(r"DDJJ N[°o]?:?\s*(\d+)", texto, re.IGNORECASE)
    datos["dj_numero"] = m.group(1).strip() if m else None

    # ── Fecha de inscripción — busca el primer formato dd/mm/aaaa en el doc ──
    m = re.search(r"(\d{2}/\d{2}/\d{4})", texto)
    datos["fecha_inscripcion"] = m.group(1).strip() if m else None

    m = re.search(r"NOMBRE TITULAR:\s*(.+?)\s+DNI TITULAR:", texto, re.IGNORECASE)
    if not m:
        m = re.search(r"NOMBRE TITULAR:\s*(.+?)[\n\r]", texto, re.IGNORECASE)
    datos["nombre_titular"] = m.group(1).strip() if m else None

    m = re.search(r"DNI TITULAR:\s*([\d.]+)", texto, re.IGNORECASE)
    datos["dni_titular"] = limpiar_dni(m.group(1)) if m else None

    m = re.search(r"DOMICILIO:\s*(.+?)(?:TO \d|BARRIO:|LOCALIDAD:|$)", texto, re.DOTALL | re.IGNORECASE)
    datos["domicilio"] = m.group(1).replace("\n", " ").strip() if m else None

    tabla_fam = None
    for t in tablas:
        if t and t[0] and "Nombre" in str(t[0]):
            tabla_fam = t
            break

    integrantes = []
    ingresos_total = None
    discapacidad_valores = []

    if tabla_fam:
        encabezado = [str(c).strip() if c else "" for c in tabla_fam[0]]
        idx_disc = next((i for i, c in enumerate(encabezado) if "Disc" in c), None)

        for fila in tabla_fam[1:]:
            if not fila:
                continue
            fila_str = " ".join(str(c) for c in fila if c)
            if "Totales" in fila_str:
                for celda in reversed(fila):
                    if celda and str(celda).strip() not in ("", "Totales:"):
                        try:
                            ingresos_total = limpiar_monto(str(celda))
                        except Exception:
                            pass
                        break
                continue
            nombre = str(fila[0]).strip() if fila[0] else ""
            if nombre:
                integrantes.append({
                    "nombre": nombre,
                    "dni": limpiar_dni(str(fila[1]).strip() if fila[1] else ""),
                    "rol": str(fila[2]).strip() if fila[2] else "",
                })
                if idx_disc is not None and len(fila) > idx_disc:
                    disc_val = str(fila[idx_disc]).strip() if fila[idx_disc] else "SD"
                    discapacidad_valores.append(disc_val)

    if not ingresos_total:
        m = re.search(r"Totales?:?\s*([\d.,]+)", texto, re.IGNORECASE)
        if m:
            try:
                ingresos_total = limpiar_monto(m.group(1))
            except Exception:
                pass

    datos["integrantes"] = integrantes
    datos["cantidad_integrantes"] = len(integrantes)
    datos["ingresos_total"] = ingresos_total

    tiene_disc = any(v.upper() not in ("NO", "SD", "") for v in discapacidad_valores)
    datos["discapacidad"] = "SI" if tiene_disc else "NO"

    return datos

def extraer_informe(archivo_pdf):
    contenido = archivo_pdf.read()
    texto = extraer_texto_pdf(contenido)
    datos = {}

    m = re.search(r"DJ\s*N[°o]?:?\s*(\d+)", texto, re.IGNORECASE)
    datos["dj_numero"] = m.group(1).strip() if m else None

    m = re.search(r"Domicilio:\s*(.+)", texto)
    datos["domicilio"] = m.group(1).strip() if m else None

    m = re.search(r"constituido por\s+(.+?)\s+integrantes", texto, re.IGNORECASE)
    datos["cantidad_integrantes"] = palabras_en_numero(m.group(1)) if m else None

    m = re.search(r"Titular:\s*(.+?),\s*DNI\s*([\d.]+)", texto, re.IGNORECASE)
    if m:
        datos["nombre_titular"] = m.group(1).strip()
        datos["dni_titular"] = limpiar_dni(m.group(2))
    else:
        datos["nombre_titular"] = None
        datos["dni_titular"] = None

    m = re.search(r"Ingresos familiares mensuales:\s*\$\s*([\d.,]+)", texto, re.IGNORECASE)
    datos["ingresos_total"] = limpiar_monto(m.group(1)) if m else None

    m = re.search(r"SITUACI[OÓ]N DE SALUD.+?Discapacidad.+?\n(.+?)(?:\n\n|\Z)",
                  texto, re.IGNORECASE | re.DOTALL)
    datos["discapacidad"] = m.group(1).strip() if m else None

    return datos