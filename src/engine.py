# -*- coding: utf-8 -*-
"""
Motor principal del sistema. Coordina la orquestación entre la lectura de archivos, 
consultas al webservice y el almacenamiento. Maneja el flujo secuencial o iterativo de procesamiento.
Orquesta el proceso completo:
 Lee los TXT (emitidos / recibidos)
 Extrae y deduplica claves de acceso
 Consulta cada clave en el web service del SRI (en paralelo, con límite)
 Guarda el XML resultante clasificado por EMITIDOS/RECIBIDOS, tipo de documento
 y cédula/RUC de la contraparte
Genera un resumen: enviadas, descargadas, no descargadas, por tipo

"""
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.file_reader import leer_txt_sri
from src.sri_client import consultar_clave
from src.storage import guardar_xml
def extraer_fecha_emision(clave_acceso):

    """
    Extrae la fecha de emisión desde la clave de acceso del SRI.
    Los primeros 8 dígitos de la clave siempre tienen el formato ddMMaaaa
    (documentado en la ficha técnica de comprobantes electrónicos del SRI).
    Devuelve la fecha como texto 'dd/mm/aaaa', o '' si la clave no es válida.
    """
    if not clave_acceso or len(clave_acceso) < 8:
        return ""
    bloque = clave_acceso[:8]
    if not bloque.isdigit():
        return ""
    dia, mes, anio = bloque[0:2], bloque[2:4], bloque[4:8]
    # Validación simple de rango, por si la clave viene corrupta
    if not (1 <= int(dia) <= 31 and 1 <= int(mes) <= 12):
        return ""
    return f"{dia}/{mes}/{anio}"

class ItemResultado:
    def __init__(self, clave_acceso, origen):
        self.clave_acceso = clave_acceso
        self.origen = origen  # "Emitidos" o "Recibidos" (según archivo de origen)
        self.ok = False
        self.tipo = None
        self.categoria = None
        self.carpeta_id = None
        self.fecha_emision = extraer_fecha_emision(clave_acceso)
        self.error = None


def cargar_claves(ruta_emitidos=None, ruta_recibidos=None):
    """
    Lee los TXT indicados y devuelve una lista de dicts únicos por clave de
    acceso: {clave_acceso, origen, tipo_comprobante_txt, ...}
    También devuelve una lista de mensajes informativos (encoding usado, etc).
    """
    claves = {}
    mensajes = []

    if ruta_emitidos:
        filas, enc = leer_txt_sri(ruta_emitidos)
        mensajes.append(f"Emitidos: {len(filas)} filas leídas de '{os.path.basename(ruta_emitidos)}' (encoding: {enc})")
        for fila in filas:
            fila["origen"] = "Emitidos"
            claves[fila["clave_acceso"]] = fila

    if ruta_recibidos:
        filas, enc = leer_txt_sri(ruta_recibidos)
        mensajes.append(f"Recibidos: {len(filas)} filas leídas de '{os.path.basename(ruta_recibidos)}' (encoding: {enc})")
        for fila in filas:
            fila["origen"] = "Recibidos"
            # Si la misma clave aparece en ambos archivos (no debería), prevalece
            # la que ya estaba para no perder info, solo agregamos si es nueva.
            claves.setdefault(fila["clave_acceso"], fila)

    return list(claves.values()), mensajes


def procesar(
    filas,
    carpeta_destino,
    own_ruc,
    hilos=4,
    pausa=0.0,
    timeout=30,
    reintentos=2,
    on_item_done=None,
    should_stop=None,
):
    """
    Descarga y guarda cada clave de acceso en `filas`.
    Devuelve la lista de ItemResultado.
    """
    os.makedirs(carpeta_destino, exist_ok=True)
    resultados = []
    total = len(filas)

    def trabajar(fila, idx):
        if pausa:
            time.sleep(pausa)
        clave = fila["clave_acceso"]
        item = ItemResultado(clave, fila.get("origen", "?"))
        sri_res = consultar_clave(clave, timeout=timeout, reintentos=reintentos)
        if not sri_res.ok:
            item.ok = False
            item.error = sri_res.error or f"No autorizado (estado={sri_res.estado})"
            return item
        try:
            info = guardar_xml(carpeta_destino, sri_res.xml_content, own_ruc, clave)
            item.ok = True
            item.tipo = info["tipo_carpeta"]
            item.categoria = info["categoria"]
            item.carpeta_id = info["carpeta_id"]
            item.ruta = info["ruta"]
        except Exception as e:
            item.ok = False
            item.error = f"Descargado pero no se pudo guardar/parsear: {e}"
        return item

    with ThreadPoolExecutor(max_workers=max(1, hilos)) as pool:
        futuros = {}
        for idx, fila in enumerate(filas):
            if should_stop and should_stop():
                break
            fut = pool.submit(trabajar, fila, idx)
            futuros[fut] = idx

        completados = 0
        for fut in as_completed(futuros):
            completados += 1
            item = fut.result()
            resultados.append(item)
            if on_item_done:
                on_item_done(item, completados, total)

    return resultados


def resumir(resultados):
    """
    Genera un resumen de los resultados de descarga.
    """
    total = len(resultados)
    descargados = [r for r in resultados if r.ok]
    no_descargados = [r for r in resultados if not r.ok]

    por_tipo = {}
    for r in descargados:
        clave = f"{r.categoria or '?'} / {r.tipo or 'Desconocido'}"
        por_tipo[clave] = por_tipo.get(clave, 0) + 1

    return {
        "total_enviadas": total,
        "total_descargadas": len(descargados),
        "total_no_descargadas": len(no_descargados),
        "por_tipo": por_tipo,
        "errores": [(r.clave_acceso, r.origen, r.error) for r in no_descargados],
    }
