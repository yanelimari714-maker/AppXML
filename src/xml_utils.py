"""
Utilidades y Parseo XML. Procesa las etiquetas específicas de los comprobantes del SRI 
(extracción de RUC del emisor/receptor, clave de acceso, fecha de emisión, valores de impuestos, detalle de productos, etc.).

"""
import xml.etree.ElementTree as ET

TIPO_FOLDER = {
    "factura": "Facturas",
    "notaCredito": "NotasCredito",
    "notaDebito": "NotasDebito",
    "comprobanteRetencion": "Retenciones",
    "guiaRemision": "GuiasRemision",
    "liquidacionCompra": "LiquidacionesCompra",
}


CONTRAPARTE_ID_TAGS = [
    "identificacionComprador",       # factura, notaCredito, notaDebito
    "identificacionSujetoRetenido",  # comprobanteRetencion
    "identificacionDestinatario",    # guiaRemision
    "identificacionProveedor",       # liquidacionCompra
]

CONTRAPARTE_RAZON_TAGS = [
    "razonSocialComprador",
    "razonSocialSujetoRetenido",
    "razonSocialDestinatario",
    "razonSocialProveedor",
]


def strip_ns(tag):
    """Quita el namespace de un tag XML dejando solo 'factura'."""
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _local_findall(root, tagname):
    return [el for el in root.iter() if strip_ns(el.tag) == tagname]


def parse_comprobante(xml_text):
    """
    Parsea el XML de un comprobante y devuelve un
    diccionario con la información necesaria para clasificarlo y guardarlo
    El fromstring, convierte el texto XML en una extructura manipulable por Python
    """

    root = ET.fromstring(xml_text)
    tipo = strip_ns(root.tag)

    def first_text(tagnames):
        for t in tagnames:
            found = _local_findall(root, t)
            if found and found[0].text:
                return found[0].text.strip()
        return None

    ruc_emisor = first_text(["ruc"])
    razon_social_emisor = first_text(["razonSocial"])
    clave_acceso = first_text(["claveAcceso"])
    contraparte_id = first_text(CONTRAPARTE_ID_TAGS)
    contraparte_razon = first_text(CONTRAPARTE_RAZON_TAGS)

    return {
        "tipo": tipo,
        "tipo_carpeta": TIPO_FOLDER.get(tipo, tipo or "Otros"),
        "ruc_emisor": ruc_emisor,
        "razon_social_emisor": razon_social_emisor,
        "clave_acceso": clave_acceso,
        "contraparte_id": contraparte_id,
        "contraparte_razon_social": contraparte_razon,
    }
