# -*- coding: utf-8 -*-
"""
file_reader.py	Lector de archivos.
 Se encarga de buscar, abrir y leer los archivos del 
 sistema de archivos local o de directorios específicos.
Lectura de los archivos TXT (delimitados por tabulador) que exporta el portal
del SRI: tanto el listado de "Emitidos Autorizados" como el de "Recibidos"
"""
import csv

POSSIBLE_ENCODINGS = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]


def _read_text(path):
    for enc in POSSIBLE_ENCODINGS:
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                return f.read(), enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(path, "r", encoding="latin-1", errors="replace", newline="") as f:
        return f.read(), "latin-1 (con reemplazo de caracteres inválidos)"


def leer_txt_sri(path):
    """
    Devuelve (filas, encoding_usado). Cada fila es un dict con
    """
    text, enc = _read_text(path)
    text = text.lstrip("\ufeff")
    lines = text.splitlines()
    if not lines:
        return [], enc

    reader = csv.DictReader(lines, delimiter="\t")
    if not reader.fieldnames:
        raise ValueError(f"No se pudo leer el encabezado de: {path}")

    fieldmap = {name.strip().upper(): name for name in reader.fieldnames}

    def col(*names):
        for n in names:
            if n in fieldmap:
                return fieldmap[n]
        return None

    c_clave = col("CLAVE_ACCESO")
    c_tipo = col("TIPO_COMPROBANTE", "COMPROBANTE")
    c_serie = col("SERIE_COMPROBANTE")
    c_ruc_emisor = col("RUC_EMISOR")
    c_receptor = col("IDENTIFICACION_RECEPTOR")
    c_razon_emisor = col("RAZON_SOCIAL_EMISOR")

    if not c_clave:
        raise ValueError(f"El archivo {path} no tiene columna CLAVE_ACCESO")

    filas = []
    for row in reader:
        clave = (row.get(c_clave) or "").strip()
        if not clave:
            continue
        filas.append({
            "clave_acceso": clave,
            "tipo_comprobante_txt": (row.get(c_tipo) or "").strip() if c_tipo else "",
            "serie": (row.get(c_serie) or "").strip() if c_serie else "",
            "ruc_emisor_txt": (row.get(c_ruc_emisor) or "").strip() if c_ruc_emisor else None,
            "identificacion_receptor_txt": (row.get(c_receptor) or "").strip() if c_receptor else None,
            "razon_social_emisor_txt": (row.get(c_razon_emisor) or "").strip() if c_razon_emisor else None,
        })
    return filas, enc
