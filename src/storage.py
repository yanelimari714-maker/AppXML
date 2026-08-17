"""
Capa de Almacenamiento. Gestiona el guardado final de la información procesada (ya sea guardando metadatos en una Base de Datos como MySQL/SQLite o archivando ordenadamente en el disco).
__init__.py	Convierte el directorio src/ en un paquete reutilizable de Python.
Decide dónde guardar cada XML descargado  
os: modulo standar de Python interactua con el sitema operativo.
re: modulo standar de Python para trabajar con expresiones 

"""
import os
import re
"""
INVALID_CHARS 
es un patrón compilado de Expresión Regular 
que agrupa caracteres no permitidos en 
nombres de archivos
"""
from src.xml_utils import parse_comprobante

INVALID_CHARS = re.compile(r'[<>:"/\\|?*\r\n\t]')


def safe_name(name):
    if not name:
        return "SIN_IDENTIFICAR"
    name = INVALID_CHARS.sub("_", name).strip()
    return name or "SIN_IDENTIFICAR"


def guardar_xml(base_dir, xml_text, own_ruc, clave_acceso):
    """
    Parsea xml_text, decide EMITIDOS/RECIBIDOS según si el RUC emisor del
    comprobante coincide con own_ruc, arma la carpeta con la cédula/RUC
    de la contraparte y guarda el XML en la carpeta correspondiente
    """
    info = parse_comprobante(xml_text)
    ruc_emisor = info["ruc_emisor"] or "SIN_RUC_EMISOR"

    if own_ruc and ruc_emisor.strip() == own_ruc.strip():
        categoria = "EMITIDOS"
        carpeta_id = safe_name(info["contraparte_id"])
    else:
        categoria = "RECIBIDOS"
        carpeta_id = safe_name(ruc_emisor)
     
    """
    Construye la ruta jerárquica uniendo
    """
    tipo_carpeta = info["tipo_carpeta"]
    folder = os.path.join(base_dir, categoria, carpeta_id, tipo_carpeta)
    os.makedirs(folder, exist_ok=True)

    filepath = os.path.join(folder, f"{clave_acceso}.xml")
    contenido = xml_text
    """
    Verifica si el XML incluye la declaración de encabezado requerida 
    (<?xml version="1.0"...). Si carece de ella, 
    la antepone automáticamente para asegurar un XML válido.
    """

    if not contenido.lstrip().startswith("<?xml"):
        contenido = '<?xml version="1.0" encoding="UTF-8"?>\n' + contenido
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(contenido)

    info["categoria"] = categoria
    info["carpeta_id"] = carpeta_id
    info["ruta"] = filepath
    return info
