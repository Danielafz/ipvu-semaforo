from rapidfuzz import fuzz

VERDE    = "🟢 VERDE"
AMARILLO = "🟡 AMARILLO"
ROJO     = "🔴 ROJO"
SIN_DATO = "⚪ SIN DATO"

def comparar_exacto(val_ddjj, val_informe, campo):
    if val_ddjj is None or val_informe is None:
        return {"campo": campo, "ddjj": val_ddjj, "informe": val_informe,
                "resultado": SIN_DATO, "detalle": "No se pudo extraer el dato."}
    ok = str(val_ddjj).strip() == str(val_informe).strip()
    return {"campo": campo, "ddjj": val_ddjj, "informe": val_informe,
            "resultado": VERDE if ok else ROJO,
            "detalle": "Coinciden." if ok else f"'{val_ddjj}' no coincide con '{val_informe}'."}

def comparar_fuzzy(val_ddjj, val_informe, campo, vok=90, vam=75):
    if val_ddjj is None or val_informe is None:
        return {"campo": campo, "ddjj": val_ddjj, "informe": val_informe,
                "resultado": SIN_DATO, "detalle": "No se pudo extraer el dato."}
    sim = fuzz.token_sort_ratio(str(val_ddjj).lower(), str(val_informe).lower())
    if sim >= vok:
        res, det = VERDE, f"Similitud alta ({sim:.1f}%)."
    elif sim >= vam:
        res, det = AMARILLO, f"Similitud media ({sim:.1f}%). Revisar manualmente."
    else:
        res, det = ROJO, f"Similitud baja ({sim:.1f}%). Probable inconsistencia."
    return {"campo": campo, "ddjj": val_ddjj, "informe": val_informe,
            "resultado": res, "detalle": det}

def comparar_numerico(val_ddjj, val_informe, campo, tv=0.10, ta=0.25):
    if val_ddjj is None or val_informe is None:
        return {"campo": campo, "ddjj": val_ddjj, "informe": val_informe,
                "resultado": SIN_DATO, "detalle": "No se pudo extraer el dato."}
    a, b = float(val_ddjj), float(val_informe)
    pct = 0.0 if a == 0 and b == 0 else (1.0 if a == 0 else abs(a - b) / a)
    if pct <= tv:
        res, det = VERDE, f"Diferencia de {pct*100:.1f}% — dentro del margen."
    elif pct <= ta:
        res, det = AMARILLO, f"Diferencia de {pct*100:.1f}%. Revisar."
    else:
        res, det = ROJO, f"Diferencia de {pct*100:.1f}%. Inconsistencia importante."
    return {"campo": campo, "ddjj": f"${a:,.0f}", "informe": f"${b:,.0f}",
            "resultado": res, "detalle": det}

def comparar_discapacidad(val_ddjj, texto_informe, campo="Discapacidad"):
    if val_ddjj is None or texto_informe is None:
        return {"campo": campo, "ddjj": val_ddjj, "informe": texto_informe,
                "resultado": SIN_DATO, "detalle": "No se pudo extraer el dato."}
    ddjj_sin_disc = str(val_ddjj).strip().upper() in ("NO", "SD", "N", "NO DISC")
    informe_sin_disc = "no se registran" in str(texto_informe).lower()
    if ddjj_sin_disc and informe_sin_disc:
        return {"campo": campo, "ddjj": val_ddjj, "informe": "Sin discapacidad",
                "resultado": VERDE, "detalle": "Ambos documentos indican sin discapacidad."}
    elif not ddjj_sin_disc and not informe_sin_disc:
        return {"campo": campo, "ddjj": val_ddjj, "informe": texto_informe,
                "resultado": AMARILLO, "detalle": "Ambos mencionan discapacidad. Revisar si coinciden."}
    else:
        return {"campo": campo, "ddjj": val_ddjj, "informe": texto_informe,
                "resultado": ROJO, "detalle": "Discrepancia en situación de discapacidad."}

def comparar(ddjj, informe):
    resultados = []

    resultados.append(comparar_exacto(
        ddjj.get("dj_numero"), informe.get("dj_numero"), "DJ N°"))

    resultados.append(comparar_exacto(
        ddjj.get("dni_titular"), informe.get("dni_titular"), "DNI Titular"))

    resultados.append(comparar_fuzzy(
        ddjj.get("nombre_titular"), informe.get("nombre_titular"), "Nombre Titular"))

    resultados.append(comparar_fuzzy(
        ddjj.get("domicilio"), informe.get("domicilio"), "Domicilio", vok=70, vam=50))

    resultados.append(comparar_exacto(
        ddjj.get("cantidad_integrantes"), informe.get("cantidad_integrantes"), "Cantidad de Integrantes"))

    resultados.append(comparar_numerico(
        ddjj.get("ingresos_total"), informe.get("ingresos_total"), "Ingresos Totales"))

    resultados.append(comparar_discapacidad(
        ddjj.get("discapacidad"), informe.get("discapacidad"), "Discapacidad"))

    orden = {ROJO: 3, AMARILLO: 2, VERDE: 1, SIN_DATO: 0}
    veredicto = max(resultados, key=lambda r: orden.get(r["resultado"], 0))["resultado"]
    alerta_dj = resultados[0]["resultado"] == ROJO
    return resultados, veredicto, alerta_dj