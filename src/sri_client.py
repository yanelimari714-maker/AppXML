# -*- coding: utf-8 -*-
"""
Cliente Web Service del SRI. Implementa las peticiones SOAP/REST a los servidores del SRI
 (por ejemplo, para consultar el estado de autorización de claves de acceso de facturas en línea).
Cliente para el web service público de autorización de comprobantes
electrónicos del SRI (Ecuador), basado en la colección Postman entregada:

POST https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl
import urllib.error / import urllib.request: Módulos de la librería estándar de Python para enviar
 peticiones HTTP/HTTPS
 POST al servicio web del SRI sin necesidad de librerías externas.
import xml.etree.ElementTree as ET: Utilizado para procesar la respuesta en formato XML 

from src.xml_utils import strip_ns: Función traída del módulo xml_utils.py que remueve los namespaces XML 
"""
import ssl
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from src.xml_utils import strip_ns

SRI_URL = (
    "https://cel.sri.gob.ec/comprobantes-electronicos-ws/"
    "AutorizacionComprobantesOffline?wsdl"
)

SOAP_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="http://ec.gob.sri.ws.autorizacion">
   <soapenv:Header/>
   <soapenv:Body>
      <ec:autorizacionComprobante>
         <claveAccesoComprobante>{clave}</claveAccesoComprobante>
      </ec:autorizacionComprobante>
   </soapenv:Body>
</soapenv:Envelope>"""


class SriResult:
    def __init__(self, clave, ok, estado=None, xml_content=None, error=None,
                 numero_autorizacion=None, fecha_autorizacion=None):
        self.clave = clave
        self.ok = ok
        self.estado = estado
        self.xml_content = xml_content
        self.error = error
        self.numero_autorizacion = numero_autorizacion
        self.fecha_autorizacion = fecha_autorizacion

"""consultar clave es la función pública principal para consultar un comprobante 
con un mecanismo de reintentos automáticos ante fallas temporales de red.
 """
def consultar_clave(clave_acceso, timeout=30, reintentos=2, espera_reintento=2.0,
                     url=None):
    """
    Consulta una clave de acceso en el web service del SRI y devuelve un
    SriResult.
    """
    url = url or SRI_URL
    ultimo_error = None
    for intento in range(reintentos + 1):
        resultado = _consultar_una_vez(clave_acceso, url, timeout)
        if resultado.ok or resultado.estado is not None:
            # respuesta válida del SRI (autorizado o no autorizado)
            return resultado
        ultimo_error = resultado.error
        if intento < reintentos:
            time.sleep(espera_reintento)
    return SriResult(clave_acceso, False, error=ultimo_error)

""" Realiza una única solicitud HTTP POST al servidor del SRI,
 analiza la respuesta SOAP y retorna un objeto
"""

def _consultar_una_vez(clave_acceso, url, timeout):
    body = SOAP_TEMPLATE.format(clave=clave_acceso).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "text/xml;charset=UTF-8",
            "SOAPAction": "",
        },
        method="POST",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        try:
            raw = e.read()
            if not raw:
                return SriResult(clave_acceso, False, error=f"HTTPError {e.code}: {e.reason}")
        except Exception:
            return SriResult(clave_acceso, False, error=f"HTTPError {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        return SriResult(clave_acceso, False, error=f"Error de conexión: {e.reason}")
    except Exception as e:
        return SriResult(clave_acceso, False, error=str(e))

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        return SriResult(clave_acceso, False, error=f"Respuesta no es XML válido: {e}")

    fault = [el for el in root.iter() if strip_ns(el.tag) == "Fault"]
    if fault:
        faultstring = None
        for el in fault[0].iter():
            if strip_ns(el.tag) == "faultstring":
                faultstring = el.text
        return SriResult(clave_acceso, False, error=f"SOAP Fault: {faultstring}")

    autorizaciones = [el for el in root.iter() if strip_ns(el.tag) == "autorizacion"]
    if not autorizaciones:
        return SriResult(clave_acceso, False, estado="NO_ENCONTRADO",
                          error="La clave de acceso no existe en el SRI")

    chosen = None
    for a in autorizaciones:
        estado_el = [c for c in a if strip_ns(c.tag) == "estado"]
        estado = estado_el[0].text if estado_el else None
        if estado == "AUTORIZADO":
            chosen = a
            break
    if chosen is None:
        chosen = autorizaciones[0]

    def child_text(tag):
        for c in chosen:
            if strip_ns(c.tag) == tag:
                return c.text
        return None

    estado = child_text("estado")
    comprobante_xml = child_text("comprobante")
    numero_aut = child_text("numeroAutorizacion")
    fecha_aut = child_text("fechaAutorizacion")

    if estado != "AUTORIZADO" or not comprobante_xml:
        return SriResult(clave_acceso, False, estado=estado,
                          error=f"Comprobante no autorizado (estado={estado})")

    return SriResult(clave_acceso, True, estado=estado, xml_content=comprobante_xml,
                      numero_autorizacion=numero_aut, fecha_autorizacion=fecha_aut)
