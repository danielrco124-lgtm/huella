#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""huella 6.0.1 — mira qué llevan dentro tus archivos, qué tiene mala pinta y límpialo.

Se abre y pregunta. No hay rutas que escribir.

    python huella.py
    python huella.py --seco        (no escribe nada, solo enseña)

Antes de limpiar, cada archivo muestra qué se le va a quitar y qué se conserva.
Después, un informe de lo hecho, verificado releyendo el resultado, y una línea
en huella-registro.txt. Si la verificación falla, el original vuelve solo.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib
from datetime import datetime
from pathlib import Path

VERSION = "6.0.1"
SECO = False


def mostrar_banner():
    """Muestra el banner de bienvenida con la firma de autor."""
    banner = [
        "  _    _ _   _ _   _ _____ _        ___  ____ _ ",
        " | |  | | | | | | | | ____| |      / _ \\/ ___| |",
        " | |__| | |_| | |_| |  _| | |     | | | \\___ \\ |",
        " |  __  |  _  |  _  | |___| |___  | |_| |___) | |",
        " |_|  |_|_| |_|_| |_|_____|_____|  \\___/|____/|_|",
        "",
        "    [+] huella no wwweelos",
        "    [+] Created by danielrco124"
    ]
    print(col("\n".join(banner), "ok"))


EXTS = {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".pdf",
        ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt"}
IMG = {".jpg", ".jpeg", ".png"}
OLE = {".doc", ".xls", ".ppt"}
OOXML = {".docx", ".xlsx", ".pptx"}
VIDEO = {".mp4", ".mov"}

TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}
SEV_W = {"alto": 30, "medio": 12, "bajo": 5, "info": 0}
SEV_O = {"alto": 0, "medio": 1, "bajo": 2, "info": 3}

MAGIC = {".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".png": b"\x89PNG\r\n\x1a\n",
         ".pdf": b"%PDF", ".docx": b"PK\x03\x04", ".xlsx": b"PK\x03\x04",
         ".pptx": b"PK\x03\x04", ".doc": b"\xd0\xcf\x11\xe0", ".xls": b"\xd0\xcf\x11\xe0",
         ".ppt": b"\xd0\xcf\x11\xe0"}

FIRMAS = [
    (b"\xff\xd8\xff", "una imagen JPEG"),
    (b"\x89PNG\r\n\x1a\n", "una imagen PNG"),
    (b"GIF8", "un GIF"),
    (b"%PDF", "un PDF"),
    (b"PK\x03\x04", "un ZIP o un documento de Office"),
    (b"MZ", "un ejecutable de Windows"),
    (b"\x7fELF", "un binario de Linux"),
    (b"\xd0\xcf\x11\xe0", "un documento de Office antiguo (OLE)"),
    (b"Rar!", "un RAR"),
    (b"7z\xbc\xaf", "un 7z"),
    (b"\x1f\x8b", "un gzip"),
    (b"RIFF", "un contenedor RIFF (WAV, AVI, WebP)"),
    (b"<!DOCTYPE", "una página HTML"),
    (b"<html", "una página HTML"),
    (b"<?xml", "un XML"),
]

EXEC_EXT = {"exe", "scr", "bat", "cmd", "js", "vbs", "ps1", "lnk", "hta", "jar", "msi", "com", "pif"}

NOMBRES_SEG = {0xE0: "APP0 (JFIF)", 0xE1: "APP1 (EXIF o XMP)", 0xE2: "APP2 (perfil de color ICC)",
               0xE3: "APP3", 0xE4: "APP4", 0xE5: "APP5", 0xE6: "APP6", 0xE7: "APP7",
               0xE8: "APP8", 0xE9: "APP9", 0xEA: "APP10", 0xEB: "APP11",
               0xEC: "APP12", 0xED: "APP13 (IPTC/Photoshop)", 0xEE: "APP14 (Adobe)",
               0xEF: "APP15", 0xFE: "COM (comentario de texto)"}

NOMBRES_CHUNK = {b"tEXt": "texto tEXt", b"iTXt": "texto iTXt", b"zTXt": "texto zTXt",
                 b"eXIf": "bloque EXIF", b"tIME": "marca de tiempo", b"gAMA": "gamma",
                 b"sRGB": "perfil sRGB", b"iCCP": "perfil de color ICC",
                 b"pHYs": "resolución física", b"PLTE": "paleta",
                 b"IHDR": "cabecera", b"IDAT": "datos de imagen", b"IEND": "fin"}

if os.name == "nt":
    os.system("")

C = {"alto": "91", "medio": "93", "bajo": "94", "info": "90", "ok": "92",
     "t": "96", "raro": "95", "bien": "92", "pos": "90", "plan": "96", "quita": "91"}


def col(t, k):
    return f"\033[{C.get(k, '0')}m{t}\033[0m"


def limpia():
    os.system("cls" if os.name == "nt" else "clear")


def linea():
    print(col("-" * 64, "info"))


def nota(g, t, p=""):
    return {"g": g, "t": t, "p": p}


def identificar(raw):
    for firma, nombre in FIRMAS:
        if raw.startswith(firma):
            return nombre
    return "desconocido"


# --------------------------------------------------------------------------- #
# EXIF
# --------------------------------------------------------------------------- #
def _walk(buf, off, endian, out, depth=0):
    if depth > 3 or off + 2 > len(buf):
        return
    count = struct.unpack(endian + "H", buf[off:off + 2])[0]
    if count > 400:
        return
    p = off + 2
    for _ in range(count):
        if p + 12 > len(buf):
            return
        tag, typ, n = struct.unpack(endian + "HHI", buf[p:p + 8])
        size = TYPE_SIZE.get(typ, 0) * n
        if size and size <= len(buf):
            if size <= 4:
                out[tag] = (typ, n, buf[p + 8:p + 8 + size])
            else:
                voff = struct.unpack(endian + "I", buf[p + 8:p + 12])[0]
                if voff + size <= len(buf):
                    out[tag] = (typ, n, buf[voff:voff + size])
        p += 12


def _txt(t):
    return t[2].split(b"\x00")[0].decode("utf-8", "replace").strip()


def _rats(t, e):
    out = []
    for i in range(0, len(t[2]) - 7, 8):
        num, den = struct.unpack(e + "II", t[2][i:i + 8])
        out.append(num / den if den else 0.0)
    return out


def _coord(rats, ref):
    if len(rats) < 3:
        return None
    v = rats[0] + rats[1] / 60 + rats[2] / 3600
    return -v if ref in ("S", "W") else v


def parse_exif(payload):
    e = "<" if payload[:2] == b"II" else ">" if payload[:2] == b"MM" else None
    if not e or len(payload) < 8:
        return {}
    tags = {}
    _walk(payload, struct.unpack(e + "I", payload[4:8])[0], e, tags)
    for ptr in (0x8769, 0x8825):
        if ptr in tags:
            _walk(payload, struct.unpack(e + "I", tags[ptr][2][:4])[0], e, tags, 1)
    tags["_e"] = e
    return tags


def jpeg_segments(data):
    if data[:2] != b"\xff\xd8":
        return None
    segs, i = [], 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        m = data[i + 1]
        if m == 0xD9:
            segs.append((m, i, i + 2))
            break
        if m == 0xDA:
            ln = struct.unpack("!H", data[i + 2:i + 4])[0]
            segs.append((m, i, min(len(data), i + 2 + ln)))
            break
        if m == 0x01 or 0xD0 <= m <= 0xD7:
            segs.append((m, i, i + 2))
            i += 2
            continue
        ln = struct.unpack("!H", data[i + 2:i + 4])[0]
        segs.append((m, i, min(len(data), i + 2 + ln)))
        i = i + 2 + ln
    return segs


def strip_jpeg(data):
    segs = jpeg_segments(data)
    if not segs:
        return data
    keep, out, tail = {0xE0, 0xE2, 0xDB, 0xDD, 0xC4, 0xDA, 0xD9}, [data[:2]], len(data)
    for m, s, _e in segs:
        if 0xC0 <= m <= 0xCF:
            keep.add(m)
        if m == 0xDA:
            tail = s
            break
    for m, s, e in segs:
        if m in keep:
            out.append(data[s:e])
    out.append(data[tail:])
    salida = b"".join(out)
    fin = salida.rfind(b"\xff\xd9")
    if fin != -1:
        salida = salida[:fin + 2]
    return salida


# --------------------------------------------------------------------------- #
# PNG
# --------------------------------------------------------------------------- #
PNG_FIRMA = b"\x89PNG\r\n\x1a\n"
PNG_KEEP = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"sRGB",
            b"iCCP", b"cHRM", b"bKGD", b"pHYs", b"acTL", b"fcTL", b"fdAT"}


def png_chunks(data):
    out = []
    if data[:8] != PNG_FIRMA:
        return out
    i = 8
    while i + 12 <= len(data):
        n = struct.unpack("!I", data[i:i + 4])[0]
        tipo = data[i + 4:i + 8]
        out.append((tipo, i, min(len(data), i + 12 + n)))
        if tipo == b"IEND":
            break
        i += 12 + n
    return out


def strip_png(data):
    segs = png_chunks(data)
    if not segs:
        return data
    out = [PNG_FIRMA]
    for tipo, s, e in segs:
        if tipo in PNG_KEEP:
            out.append(data[s:e])
    return b"".join(out)


# --------------------------------------------------------------------------- #
# rarezas y aciertos
# --------------------------------------------------------------------------- #
def detectar(path, raw, tags=None):
    r = []
    nombre = path.name
    ext = path.suffix.lower()
    sufijos = [s.lower() for s in path.suffixes]

    if len(raw) == 0:
        r.append(nota("raro", "archivo vacío (0 bytes)",
                      "descarga cortada, archivo cebo o copia fallida"))
        return r

    if len(raw) < 200 and ext in IMG:
        r.append(nota("raro", f"archivo diminuto para una imagen ({len(raw)} bytes)",
                      "miniatura, marcador de posición o copia rota"))
    elif len(raw) < 64 and ext not in IMG:
        r.append(nota("aviso", f"archivo muy pequeño ({len(raw)} bytes)",
                      "puede faltarle contenido"))
    else:
        r.append(nota("bien", f"tamaño coherente ({len(raw) / 1024:.1f} KB)"))

    magic = MAGIC.get(ext)
    if magic and not raw.startswith(magic):
        real = identificar(raw)
        r.append(nota("raro", f"la extensión miente: por dentro es {real}",
                      "quien solo mire el nombre lo tratará como otra cosa; "
                      "si es un ejecutable, el sistema no lo abre con el visor"))
    elif magic:
        r.append(nota("bien", "la firma del archivo coincide con la extensión"))

    if len(sufijos) >= 3 and sufijos[-1] in EXEC_EXT:
        r.append(nota("raro", f"doble extensión: {'.'.join(sufijos[-2:])}",
                      "el nombre y el icono apuntan a un formato, el sistema ejecutará otro"))
    if "\u202e" in nombre:
        r.append(nota("raro", "el nombre lleva U+202E, el carácter que invierte el orden",
                      "lo que lees al final es en realidad el principio"))
    problemas_nombre = False
    if nombre != nombre.rstrip():
        r.append(nota("aviso", "el nombre acaba en espacio", "algunos sistemas lo recortan y el enlace se rompe"))
        problemas_nombre = True
    if len(re.findall(r"[^\x00-\x7F]", nombre)) > 6:
        r.append(nota("aviso", "el nombre mezcla muchos caracteres no latinos", "puede dar problemas al compartirlo"))
        problemas_nombre = True
    if not problemas_nombre and len(sufijos) < 3:
        r.append(nota("bien", "nombre sin trampas"))

    if ext in (".jpg", ".jpeg"):
        segs = jpeg_segments(raw) or []
        if not segs:
            r.append(nota("raro", "no se puede recorrer como JPEG", "cabecera rota o firma falsificada"))
        else:
            fin = raw.rfind(b"\xff\xd9")
            if fin != -1 and fin + 2 < len(raw):
                r.append(nota("raro", f"hay {len(raw) - fin - 2} bytes pegados después del final de la imagen",
                              "payload añadido a propósito, o una app que escribió sin recortar"))
                cola = raw[fin + 2:]
                for firma, nombre_f in FIRMAS:
                    if cola.startswith(firma):
                        r.append(nota("raro", f"lo pegado es {nombre_f}", "el archivo es a la vez dos cosas"))
                        break
            elif fin != -1:
                r.append(nota("bien", "termina justo donde debe, sin datos detrás"))
            else:
                r.append(nota("raro", "no tiene marcador de fin de imagen", "archivo truncado"))
            marcadores = {m for m, _s, _e in segs}
            if 0xE2 in marcadores:
                r.append(nota("bien", "lleva perfil de color (se verá igual en cualquier pantalla)"))
            if 0xE0 not in marcadores and 0xE1 not in marcadores:
                r.append(nota("aviso", "sin metadatos: ya pasó por una app que los borra",
                              "bueno para la privacidad, malo si querías conservar el original"))
            fecha = ""
            if tags:
                for t in (0x9003, 0x0132):
                    if t in tags:
                        fecha = _txt(tags[t])
                        break
            m = re.match(r"(\d{4})", fecha)
            if m:
                anio = int(m.group(1))
                if anio < 1990 or anio > 2100:
                    r.append(nota("raro", f"fecha imposible dentro del archivo ({fecha})",
                                  "reloj mal puesto o fecha editada a mano"))

    if ext == ".png":
        segs = png_chunks(raw)
        tipos = {t for t, _s, _e in segs}
        if not segs or b"IHDR" not in tipos:
            r.append(nota("raro", "no se puede recorrer como PNG", "cabecera rota o firma falsificada"))
        else:
            if b"IEND" in tipos:
                fin = next(e for t, _s, e in segs if t == b"IEND")
                if fin < len(raw):
                    r.append(nota("raro", f"hay {len(raw) - fin} bytes después del final de la imagen",
                                  "payload escondido o escritura sin recortar"))
                else:
                    r.append(nota("bien", "termina en su marcador de fin, sin nada detrás"))
            textos = [t for t in tipos if t in (b"tEXt", b"iTXt", b"zTXt")]
            if textos:
                r.append(nota("aviso", f"lleva {len(textos)} bloque(s) de texto libre",
                              "puede contener software, autor o comentarios"))
            if b"eXIf" in tipos:
                r.append(nota("aviso", "lleva EXIF dentro (puede traer GPS)", "cámara o móvil que lo escribió"))
            if b"iCCP" in tipos or b"sRGB" in tipos:
                r.append(nota("bien", "lleva perfil de color"))
            if not textos and b"eXIf" not in tipos:
                r.append(nota("bien", "sin bloques de texto ni EXIF"))

    if ext == ".pdf":
        if b"%%EOF" not in raw:
            r.append(nota("raro", "no tiene marca de fin de documento (%EOF)", "PDF truncado o generado a mano"))
        else:
            r.append(nota("bien", "documento cerrado correctamente"))
        for patron, texto, posible, grav in (
                (b"/JavaScript", "lleva JavaScript dentro", "puede ejecutar código en el lector", "raro"),
                (b"/OpenAction", "se ejecuta algo al abrirlo", "acción automática al abrir", "raro"),
                (b"/AA", "lleva acciones automáticas", "se disparan al abrir, cerrar o pasar página", "aviso"),
                (b"/Launch", "puede lanzar programas externos", "abre un ejecutable del sistema", "raro"),
                (b"/EmbeddedFiles", "lleva archivos incrustados", "puede esconder un ejecutable dentro", "aviso"),
                (b"/RichMedia", "lleva contenido multimedia incrustado", "flash o vídeo embebido", "aviso"),
                (b"/XFA", "lleva formulario XFA", "los XFA se ejecutan como plantilla", "aviso"),
                (b"/AcroForm", "es un formulario rellenable", "puede traer datos escritos", "info"),
                (b"/Encrypt", "está cifrado", "algunas herramientas no podrán leerlo", "aviso")):
            if patron in raw:
                r.append(nota(grav, texto, posible))
        if not any(p in raw for p in (b"/JavaScript", b"/OpenAction", b"/Launch")):
            r.append(nota("bien", "no se ejecuta nada al abrirlo"))

    if ext in OOXML:
        try:
            with zipfile.ZipFile(path) as z:
                infos = z.infolist()
                names = z.namelist()
                rels = b""
                for n in names:
                    if n.endswith(".rels"):
                        try:
                            rels += z.read(n)
                        except Exception:
                            pass
        except (zipfile.BadZipFile, OSError):
            r.append(nota("raro", "el documento está corrupto o no es un documento",
                          "ZIP inválido con extensión de Office"))
            infos, names, rels = [], [], b""
        if names:
            if any(n.endswith("vbaProject.bin") for n in names):
                r.append(nota("raro", "lleva macros (VBA)",
                              "vía clásica de infección; se ejecutan al habilitar contenido"))
            else:
                r.append(nota("bien", "sin macros"))
            if any("/embeddings/" in n for n in names):
                r.append(nota("raro", "lleva otros archivos incrustados",
                              "puede esconder un ejecutable dentro del documento"))
            else:
                r.append(nota("bien", "sin archivos incrustados"))
            if b'TargetMode="External"' in rels:
                r.append(nota("aviso", "tiene enlaces externos",
                              "al abrirlo puede pedir recursos a un servidor y delatarte"))
            if any(n.startswith("../") or "/../" in n for n in names):
                r.append(nota("raro", "hay rutas que se escapan del ZIP",
                              "al descomprimir puede escribir fuera de la carpeta"))
            comp = sum(i.compress_size for i in infos) or 1
            crudo = sum(i.file_size for i in infos)
            if crudo > 20 * 1024 * 1024 and crudo / comp > 100:
                r.append(nota("aviso", f"comprime {crudo / comp:.0f}:1", "posible bomba ZIP al descomprimir"))
            if "docProps/custom.xml" in names:
                r.append(nota("aviso", "lleva propiedades personalizadas",
                              "pares clave/valor que pueden identificar a alguien"))

    if ext in OLE:
        if b"VBA" in raw:
            r.append(nota("raro", "contiene cadenas de macro (VBA)", "formato antiguo con macros probables"))
        else:
            r.append(nota("bien", "sin rastro de macros"))

    if ext in VIDEO:
        if b"ftyp" not in raw[4:16]:
            r.append(nota("raro", "no parece un vídeo de verdad", "contenedor roto o renombrado"))
        else:
            r.append(nota("bien", "contenedor de vídeo correcto"))

    return r


# --------------------------------------------------------------------------- #
# metadatos
# --------------------------------------------------------------------------- #
def add(f, sev, campo, valor):
    f.append({"severidad": sev, "campo": campo, "valor": str(valor)[:110]})


def analyze_exif_tags(tags, f):
    en = tags.get("_e", "<")
    for tag, campo, sev in ((0x010F, "Fabricante", "bajo"),
                            (0x0110, "Modelo de cámara", "medio"),
                            (0x0131, "Software", "bajo"),
                            (0x0132, "Fecha", "bajo"),
                            (0x013B, "Autor", "medio"),
                            (0xA430, "Propietario", "medio"),
                            (0xA431, "Número de serie", "alto"),
                            (0x9286, "Comentario", "medio"),
                            (0x010E, "Descripción", "bajo"),
                            (0x8298, "Copyright", "medio")):
        if tag in tags:
            v = _txt(tags[tag]) or ", ".join(f"{x:g}" for x in _rats(tags[tag], en))
            if v:
                add(f, sev, campo, v)
    if 0x8825 in tags and 2 in tags and 4 in tags:
        la = _coord(_rats(tags[2], en), _txt(tags[1]) if 1 in tags else "N")
        lo = _coord(_rats(tags[4], en), _txt(tags[3]) if 3 in tags else "E")
        if la is not None and lo is not None:
            return {"lat": round(la, 6), "lon": round(lo, 6)}
    return {}


def analyze_jpeg(raw):
    f, info, tags = [], {}, {}
    segs = jpeg_segments(raw) or []
    if not any(m == 0xE1 for m, _s, _e in segs):
        return f, info, tags
    for m, s, e in segs:
        if m != 0xE1:
            continue
        body = raw[s + 4:e]
        if body[:6] != b"Exif\x00\x00":
            continue
        tags = parse_exif(body[6:])
        info = analyze_exif_tags(tags, f)
        if 0x0201 in tags or 0x0202 in tags:
            add(f, "medio", "Miniatura incrustada", "sí, copia de la propia foto")
        break
    return f, info, tags


def analyze_png(raw):
    f, info = [], {}
    for tipo, s, e in png_chunks(raw):
        if tipo in (b"tEXt", b"iTXt", b"zTXt"):
            cuerpo = raw[s + 8:e - 4]
            if tipo == b"tEXt" and b"\x00" in cuerpo:
                clave, valor = cuerpo.split(b"\x00", 1)
                clave = clave.decode("latin-1", "replace")
                valor = valor.decode("utf-8", "replace").strip()
                sev = "medio" if clave.lower() in ("author", "artist", "copyright") else "bajo"
                if valor:
                    add(f, sev, f"Texto: {clave}", valor)
            else:
                texto = cuerpo.decode("utf-8", "replace").strip()
                if len(texto) > 3:
                    add(f, "bajo", "Texto internacional", texto[:110])
        elif tipo == b"eXIf":
            tags = parse_exif(raw[s + 8:e - 4])
            if tags:
                gps = analyze_exif_tags(tags, f)
                if gps:
                    info.update(gps)
                    add(f, "alto", "Dónde se hizo la foto", f"{gps['lat']:.5f}, {gps['lon']:.5f}")
    return f, info


def analyze_pdf(raw):
    f = []
    for campo, sev in (("Author", "alto"), ("Creator", "medio"), ("Producer", "bajo"),
                       ("Title", "bajo"), ("Subject", "bajo"), ("Keywords", "bajo")):
        m = re.search(rb"/" + campo.encode() + rb"\s*\(([^)]{1,110})\)", raw)
        if m:
            add(f, sev, campo, m.group(1).decode("utf-8", "replace"))
    for campo in ("CreationDate", "ModDate"):
        m = re.search(rb"/" + campo.encode() + rb"\s*\(D:(\d{8})", raw)
        if m:
            add(f, "bajo", campo, m.group(1).decode())
    return f


def analyze_office(path):
    f, notas = [], []
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            core = z.read("docProps/core.xml").decode("utf-8", "replace") if "docProps/core.xml" in names else ""
            app = z.read("docProps/app.xml").decode("utf-8", "replace") if "docProps/app.xml" in names else ""
            doc = z.read("word/document.xml").decode("utf-8", "replace") if "word/document.xml" in names else ""
            cust = z.read("docProps/custom.xml").decode("utf-8", "replace") if "docProps/custom.xml" in names else ""
    except Exception:
        return f, notas
    for tag, campo, sev in (("dc:creator", "Lo escribió", "alto"),
                            ("cp:lastModifiedBy", "Lo tocó por última vez", "medio"),
                            ("dc:title", "Título", "bajo"),
                            ("dc:subject", "Asunto", "bajo")):
        m = re.search(r"<%s>([^<]{1,110})</%s>" % (tag, tag), core)
        if m:
            add(f, sev, campo, m.group(1))
    m = re.search(r"<Company>([^<]{1,110})</Company>", app)
    if m:
        add(f, "medio", "Empresa", m.group(1))
    m = re.search(r"<TotalTime>(\d+)</TotalTime>", app)
    if m and m.group(1) != "0":
        add(f, "bajo", "Minutos de edición", m.group(1))
    for m in re.finditer(r'name="([^"]{1,60})"[^>]*>\s*<vt:[^>]*>([^<]{1,110})<', cust):
        add(f, "bajo", f"Propiedad: {m.group(1)}", m.group(2))
    cambios = len(re.findall(r"<w:(?:ins|del)\b", doc))
    if cambios:
        add(f, "alto", "Cambios sin aceptar", str(cambios))
        borrado = re.findall(r"<w:delText[^>]*>([^<]{1,120})</w:delText>", doc)
        if borrado:
            add(f, "alto", "Texto que creías borrado", " / ".join(borrado[:3]))
    else:
        notas.append(nota("bien", "sin cambios pendientes de aceptar"))
    if any("comments" in n for n in names):
        add(f, "alto", "Comentarios", "sí")
    else:
        notas.append(nota("bien", "sin comentarios"))
    if not any(h["campo"] == "Lo escribió" for h in f):
        notas.append(nota("bien", "sin autor en los metadatos"))
    return f, notas


def analyze_mp4(raw):
    f, notas = [], []
    hallado = False
    for m in re.finditer(b"\xa9xyz", raw):
        size = struct.unpack("!I", raw[m.start() - 4:m.start()])[0]
        g = re.match(r"([+-]\d+\.\d+)([+-]\d+\.\d+)",
                     raw[m.start() + 4:m.start() - 4 + size].decode("utf-8", "replace").strip())
        if g:
            add(f, "alto", "Dónde se grabó", f"{g.group(1)}, {g.group(2)}")
            hallado = True
    if not hallado:
        notas.append(nota("bien", "sin coordenadas en el contenedor"))
    return f, notas


def analyze_file(path):
    ext = path.suffix.lower()
    vacio = {"fichero": path, "hallazgos": [], "score": 0, "info": {}, "rarezas": [],
             "plan": {"quita": [], "conserva": [], "nada": True}}
    try:
        raw = path.read_bytes()
    except OSError as exc:
        vacio["rarezas"] = [nota("raro", f"no se puede leer ({exc.__class__.__name__})",
                                 "permisos, unidad desconectada o archivo bloqueado")]
        return vacio

    info, tags, hallazgos, notas = {}, {}, [], []
    if ext in (".jpg", ".jpeg"):
        hallazgos, info, tags = analyze_jpeg(raw)
    elif ext == ".png":
        hallazgos, info = analyze_png(raw)
    elif ext == ".pdf":
        hallazgos = analyze_pdf(raw)
    elif ext in OOXML:
        hallazgos, notas = analyze_office(path)
    elif ext in VIDEO:
        hallazgos, notas = analyze_mp4(raw)
    elif ext in OLE:
        notas = [nota("aviso", "formato antiguo (OLE)", "la limpieza no puede reescribirlo; se copia tal cual")]

    rarezas = detectar(path, raw, tags) + notas
    if ext in IMG:
        if info.get("lat"):
            rarezas.append(nota("raro", "lleva las coordenadas de dónde se hizo", "con dos fotos se deduce tu casa"))
        else:
            rarezas.append(nota("bien", "sin coordenadas GPS"))

    score = min(100, sum(SEV_W[h["severidad"]] for h in hallazgos))
    if any(x["g"] == "raro" for x in rarezas):
        score = max(score, 40)

    try:
        plan = plan_limpieza(path, raw)
    except Exception:
        plan = {"quita": [{"t": "nada: no se puede planificar", "bytes": 0}],
                "conserva": ["el archivo tal cual"], "nada": True}

    return {"fichero": path, "hallazgos": hallazgos, "info": info,
            "rarezas": rarezas, "score": score, "plan": plan}


def veredicto(r):
    if any(x["g"] == "raro" for x in r["rarezas"]):
        return "SOSPECHOSO"
    if r["score"] >= 30 or any(x["g"] == "aviso" for x in r["rarezas"]):
        return "VIGILA"
    return "LIMPIO"


# --------------------------------------------------------------------------- #
# plan de limpieza: qué se va a quitar y qué se queda
# --------------------------------------------------------------------------- #
def _detalle_exif(tags):
    d = []
    en = tags.get("_e", "<")
    for tag, nombre in ((0x010F, "fabricante"), (0x0110, "modelo"), (0x0131, "software"),
                        (0x013B, "autor"), (0xA430, "propietario"), (0xA431, "número de serie"),
                        (0x9286, "comentario"), (0x8298, "copyright")):
        if tag in tags:
            v = _txt(tags[tag])
            if v:
                d.append(f"{nombre} «{v}»")
    if 0x8825 in tags and 2 in tags and 4 in tags:
        la = _coord(_rats(tags[2], en), _txt(tags[1]) if 1 in tags else "N")
        lo = _coord(_rats(tags[4], en), _txt(tags[3]) if 3 in tags else "E")
        if la is not None and lo is not None:
            d.append(f"GPS {la:.5f}, {lo:.5f}")
    if 0x0201 in tags:
        d.append("miniatura incrustada")
    return d


def plan_jpeg(raw):
    plan = {"quita": [], "conserva": [], "nada": False}
    segs = jpeg_segments(raw) or []
    if not segs:
        plan["nada"] = True
        plan["quita"].append({"t": "nada: el JPEG no se puede recorrer", "bytes": 0})
        return plan
    for m, s, e in segs:
        if m in (0xE0, 0xDB, 0xDD, 0xC4, 0xDA, 0xD9) or 0xC0 <= m <= 0xCF:
            continue
        if m == 0xE2:
            continue
        tam = e - s
        if m == 0xE1:
            body = raw[s + 4:e]
            if body[:6] == b"Exif\x00\x00":
                detalle = _detalle_exif(parse_exif(body[6:]))
                etiqueta = "bloque EXIF completo"
                if detalle:
                    etiqueta += " (" + ", ".join(detalle) + ")"
                plan["quita"].append({"t": etiqueta, "bytes": tam})
            elif b"ns.adobe.com/xap" in body:
                plan["quita"].append({"t": "bloque XMP (historial de edición de Adobe)", "bytes": tam})
            elif b"Photoshop" in body:
                plan["quita"].append({"t": "bloque APP1 con datos de edición", "bytes": tam})
            else:
                plan["quita"].append({"t": "bloque APP1 sin identificar", "bytes": tam})
        elif m == 0xFE:
            texto = raw[s + 4:e].decode("latin-1", "replace").strip()
            plan["quita"].append({"t": f"comentario de texto «{texto[:60]}»", "bytes": tam})
        else:
            plan["quita"].append({"t": NOMBRES_SEG.get(m, f"segmento 0x{m:02X}"), "bytes": tam})
    fin = raw.rfind(b"\xff\xd9")
    if fin != -1 and fin + 2 < len(raw):
        plan["quita"].append({"t": f"{len(raw) - fin - 2} bytes pegados tras el fin de imagen",
                              "bytes": len(raw) - fin - 2})
    if 0xE2 in {m for m, _s, _e in segs}:
        plan["conserva"].append("perfil de color ICC (APP2)")
    plan["conserva"] += ["imagen, tablas de cuantización y Huffman",
                         "cabecera JFIF (APP0)", "estructura del JPEG"]
    if not plan["quita"]:
        plan["nada"] = True
    return plan


def plan_png(raw):
    plan = {"quita": [], "conserva": [], "nada": False}
    segs = png_chunks(raw)
    if not segs:
        plan["nada"] = True
        plan["quita"].append({"t": "nada: el PNG no se puede recorrer", "bytes": 0})
        return plan
    for tipo, s, e in segs:
        if tipo in PNG_KEEP:
            continue
        nombre = NOMBRES_CHUNK.get(tipo, "bloque " + tipo.decode("latin-1", "replace"))
        plan["quita"].append({"t": nombre, "bytes": e - s})
        if tipo == b"tEXt":
            cuerpo = raw[s + 8:e - 4]
            if b"\x00" in cuerpo:
                k, v = cuerpo.split(b"\x00", 1)
                plan["quita"][-1]["t"] += (f" «{k.decode('latin-1', 'replace')}: "
                                           f"{v.decode('utf-8', 'replace')[:60]}»")
    fin = next((e for t, _s, e in segs if t == b"IEND"), None)
    if fin is not None and fin < len(raw):
        plan["quita"].append({"t": f"{len(raw) - fin} bytes tras el fin de imagen", "bytes": len(raw) - fin})
    for tipo, s, e in segs:
        if tipo in (b"iCCP", b"sRGB"):
            plan["conserva"].append(NOMBRES_CHUNK[tipo])
        elif tipo == b"pHYs":
            plan["conserva"].append("resolución física (pHYs)")
    plan["conserva"] += ["imagen y paleta", "cabecera y estructura"]
    if not plan["quita"]:
        plan["nada"] = True
    return plan


def plan_office(path):
    plan = {"quita": [], "conserva": [], "nada": False}
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            core = z.read("docProps/core.xml").decode("utf-8", "replace") if "docProps/core.xml" in names else ""
            app = z.read("docProps/app.xml").decode("utf-8", "replace") if "docProps/app.xml" in names else ""
            doc = z.read("word/document.xml").decode("utf-8", "replace") if "word/document.xml" in names else ""
            cust = z.read("docProps/custom.xml").decode("utf-8", "replace") if "docProps/custom.xml" in names else ""
            infos = {i.filename: i.file_size for i in z.infolist()}
    except Exception:
        plan["nada"] = True
        plan["quita"].append({"t": "nada: el documento no se puede abrir", "bytes": 0})
        return plan

    for tag, campo in (("dc:creator", "autor"), ("cp:lastModifiedBy", "último editor"),
                       ("dc:title", "título"), ("dc:subject", "asunto")):
        m = re.search(r"<%s>([^<]{1,110})</%s>" % (tag, tag), core)
        if m:
            plan["quita"].append({"t": f"{campo} «{m.group(1)}»", "bytes": len(m.group(1))})
    m = re.search(r"<Company>([^<]{1,110})</Company>", app)
    if m:
        plan["quita"].append({"t": f"empresa «{m.group(1)}»", "bytes": len(m.group(1))})
    if "docProps/custom.xml" in names:
        props = re.findall(r'name="([^"]{1,60})"', cust)
        if props:
            plan["quita"].append({"t": f"propiedades personalizadas: {', '.join(props[:5])}",
                                  "bytes": infos.get("docProps/custom.xml", 0)})
    cambios = re.findall(r"<w:delText[^>]*>([^<]{1,120})</w:delText>", doc)
    if cambios:
        plan["quita"].append({"t": f"{len(cambios)} fragmento(s) de texto borrado que pasarían a visibles: "
                                   + " / ".join(cambios[:3]), "bytes": 0})
    marcas = len(re.findall(r"<w:(?:ins|del)\b", doc))
    if marcas:
        plan["quita"].append({"t": f"{marcas} marca(s) de cambio sin aceptar (se aceptan)", "bytes": 0})
    comentarios = [n for n in names if n.startswith("word/comments") or n == "word/people.xml"]
    if comentarios:
        plan["quita"].append({"t": f"{len(comentarios)} parte(s) de comentarios y sus autores",
                              "bytes": sum(infos.get(n, 0) for n in comentarios)})
    if "docProps/thumbnail.jpeg" in names:
        plan["quita"].append({"t": "miniatura del documento", "bytes": infos.get("docProps/thumbnail.jpeg", 0)})

    plan["conserva"] += ["texto, formato y estilos", "imágenes incrustadas legítimas", "estructura del documento"]
    if not plan["quita"]:
        plan["nada"] = True
    return plan


def plan_limpieza(path, raw):
    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        return plan_jpeg(raw)
    if ext == ".png":
        return plan_png(raw)
    if ext in OOXML:
        return plan_office(path)
    return {"quita": [{"t": "nada: este formato no se reescribe, se copia idéntico", "bytes": 0}],
            "conserva": ["el archivo completo, byte a byte"], "nada": True}


# --------------------------------------------------------------------------- #
# verificación posterior
# --------------------------------------------------------------------------- #
def verificar(origen, destino, ext):
    res = {"ok": True, "bien": [], "problemas": []}
    try:
        raw = destino.read_bytes()
        orig = origen.read_bytes()
    except OSError:
        res["ok"] = False
        res["problemas"].append("no se puede releer el resultado")
        return res
    if len(raw) == 0:
        res["ok"] = False
        res["problemas"].append("el resultado está vacío")
        return res
    magic = MAGIC.get(ext)
    if magic and not raw.startswith(magic):
        res["ok"] = False
        res["problemas"].append("la firma del resultado ya no coincide")
    else:
        res["bien"].append("la firma sigue siendo válida")

    if ext in (".jpg", ".jpeg"):
        segs = jpeg_segments(raw)
        if not segs:
            res["ok"] = False
            res["problemas"].append("el JPEG resultante no se puede recorrer")
        else:
            m = {x for x, _s, _e in segs}
            if 0xE1 in m:
                res["problemas"].append("queda algún APP1 (EXIF o XMP)")
            else:
                res["bien"].append("sin EXIF ni XMP")
            if 0xED in m:
                res["problemas"].append("queda algún APP13 (IPTC)")
            if 0xFE in m:
                res["problemas"].append("queda algún comentario")
            if raw.rfind(b"\xff\xd9") != len(raw) - 2:
                res["problemas"].append("el resultado no termina exactamente en el marcador de fin")
            else:
                res["bien"].append("termina en el marcador de fin, sin cola")
            if 0xE2 in m:
                res["bien"].append("perfil de color conservado")

    if ext == ".png":
        segs = png_chunks(raw)
        tipos = {t for t, _s, _e in segs}
        if not segs or b"IEND" not in tipos:
            res["ok"] = False
            res["problemas"].append("el PNG resultante está incompleto")
        else:
            if tipos & {b"tEXt", b"iTXt", b"zTXt"}:
                res["problemas"].append("queda algún bloque de texto")
            else:
                res["bien"].append("sin bloques de texto")
            if b"eXIf" in tipos:
                res["problemas"].append("queda el bloque EXIF")
            else:
                res["bien"].append("sin EXIF")

    if ext in OOXML:
        try:
            with zipfile.ZipFile(destino) as z:
                names = z.namelist()
                core = z.read("docProps/core.xml").decode("utf-8", "replace") if "docProps/core.xml" in names else ""
                doc = z.read("word/document.xml").decode("utf-8", "replace") if "word/document.xml" in names else ""
        except (zipfile.BadZipFile, OSError):
            res["ok"] = False
            res["problemas"].append("el documento resultante no es un ZIP válido")
            return res
        if re.search(r"<dc:creator>[^<]+</dc:creator>", core):
            res["problemas"].append("el autor sigue escrito")
        else:
            res["bien"].append("sin autor")
        if re.search(r"<cp:lastModifiedBy>[^<]+</cp:lastModifiedBy>", core):
            res["problemas"].append("el último editor sigue escrito")
        if any("comments" in n for n in names):
            res["problemas"].append("quedan partes de comentarios")
        else:
            res["bien"].append("sin comentarios")
        if re.search(r"<w:(?:ins|del)\b", doc):
            res["problemas"].append("quedan marcas de cambio")
        else:
            res["bien"].append("sin marcas de cambio")

    if len(orig) != len(raw):
        res["bien"].append(f"{len(orig) - len(raw)} bytes menos que el original")
    if res["problemas"]:
        res["ok"] = False
    return res


# --------------------------------------------------------------------------- #
# limpieza
# --------------------------------------------------------------------------- #
def strip_docx(src, dst):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        names = zin.namelist()
        es_docx = "word/document.xml" in names
        for item in zin.infolist():
            n = item.filename
            if n == "docProps/thumbnail.jpeg":
                continue
            if es_docx and (n.startswith("word/comments") or n == "word/people.xml"):
                continue
            data = zin.read(n)
            if n == "docProps/core.xml":
                t = data.decode("utf-8", "replace")
                for tag in ("dc:creator", "cp:lastModifiedBy", "dc:title", "dc:subject"):
                    t = re.sub(r"(<%s>)[^<]*(</%s>)" % (tag, tag), r"\1\2", t)
                data = t.encode()
            elif n == "docProps/app.xml":
                t = data.decode("utf-8", "replace")
                data = re.sub(r"(<Company>)[^<]*(</Company>)", r"\1\2", t).encode()
            elif n == "docProps/custom.xml":
                t = data.decode("utf-8", "replace")
                data = re.sub(r"<property[^>]*>.*?</property>", "", t, flags=re.S).encode()
            elif n == "word/document.xml":
                t = data.decode("utf-8", "replace")
                t = re.sub(r"<w:(?:ins|del)\b[^>]*>|</w:(?:ins|del)>", "", t)
                t = re.sub(r"<w:commentRange(?:Start|End)\b[^>]*/>", "", t)
                t = re.sub(r"<w:commentReference\b[^>]*/>", "", t)
                data = t.replace("<w:delText", "<w:t").replace("</w:delText>", "</w:t>").encode()
            elif es_docx and n == "[Content_Types].xml":
                t = data.decode("utf-8", "replace")
                t = re.sub(r'<Override[^>]*PartName="/word/(?:comments[^"]*|people\.xml)"[^>]*/>', "", t)
                data = t.encode()
            zout.writestr(item, data)


def limpiar_a(src, dst):
    """Escribe siempre a un temporal de la misma carpeta y sustituye al final."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    ext = src.suffix.lower()
    fd, tp = tempfile.mkstemp(suffix=ext, dir=str(dst.parent))
    os.close(fd)
    tmp = Path(tp)
    try:
        if ext in (".jpg", ".jpeg"):
            tmp.write_bytes(strip_jpeg(src.read_bytes()))
        elif ext == ".png":
            tmp.write_bytes(strip_png(src.read_bytes()))
        elif ext in OOXML:
            if src.read_bytes()[:4] == b"PK\x03\x04":
                strip_docx(src, tmp)
            else:
                shutil.copy2(src, tmp)
        else:
            shutil.copy2(src, tmp)
        os.replace(tmp, dst)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise


def abrir(p):
    try:
        if os.name == "nt":
            os.startfile(p)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
    except Exception:
        pass


def registrar(base, accion, ruta, quitado, antes, despues, destino, estado):
    try:
        with open(base / "huella-registro.txt", "a", encoding="utf-8") as fh:
            fh.write(" | ".join([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), accion, ruta.name,
                quitado or "-", f"{antes}->{despues}" if despues is not None else str(antes),
                destino or "-", estado]) + "\n")
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# selección
# --------------------------------------------------------------------------- #
def parsear_seleccion(texto, total):
    texto = texto.strip().lower()
    if texto in ("t", "todo", "*"):
        return list(range(total))
    if texto in ("n", ""):
        return []
    sel = set()
    for tok in texto.replace(" ", ",").split(","):
        if not tok:
            continue
        if "-" in tok:
            a, b = tok.split("-", 1)
            if a.isdigit() and b.isdigit():
                for i in range(int(a), int(b) + 1):
                    if 1 <= i <= total:
                        sel.add(i - 1)
        elif tok.isdigit():
            i = int(tok)
            if 1 <= i <= total:
                sel.add(i - 1)
    return sorted(sel)


def preguntar(texto, validas):
    while True:
        try:
            r = input(col(texto, "t")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "q"
        if r in validas:
            return r
        print(col("  opción no válida", "medio"))


# --------------------------------------------------------------------------- #
# menú
# --------------------------------------------------------------------------- #
def carpetas_conocidas():
    casa = Path.home()
    cand = []
    for nombre, rutas in (("Fotos", ["Pictures", "Imágenes", "Imagenes"]),
                          ("Descargas", ["Downloads", "Descargas"]),
                          ("Escritorio", ["Desktop", "Escritorio"]),
                          ("Documentos", ["Documents", "Documentos"])):
        for r in rutas:
            p = casa / r
            if p.is_dir():
                cand.append((nombre, p))
                break
    return cand


def plataformas():
    limpia()
    print(col("\n  Qué borra cada sitio (hoy; cambian sin avisar)\n", "ok"))
    for quien, fotos, docs in (("Instagram, WhatsApp, X, LinkedIn", "borra el EXIF", "-"),
                               ("Wallapop, Vinted", "borra el EXIF", "borra el autor si convierte"),
                               ("Telegram", "borra en 'foto', CONSERVA en 'archivo'", "conserva"),
                               ("Correo, foros, Drive, Dropbox", "CONSERVA", "CONSERVA")):
        print(f"  · {quien}\n      fotos: {fotos} · documentos: {docs}")
    print(col("\n  Moraleja: no confíes en la app. Limpia el archivo antes.\n", "info"))


def menu_principal():
    while True:
        limpia()
        mostrar_banner()
        if SECO:
            print(col("  MODO SECO: no se escribe nada\n", "medio"))
        linea()
        carpetas = carpetas_conocidas()
        for i, (nombre, _p) in enumerate(carpetas, 1):
            print(f"   {i}) {nombre}")
        n = len(carpetas)
        print(f"   {n + 1}) Otra carpeta (arrástrala aquí)")
        print(f"   {n + 2}) Probar con archivos de ejemplo")
        print(f"   {n + 3}) Qué borra cada plataforma")
        print("   0) Salir")
        linea()
        r = preguntar("  Elige: ", [str(i) for i in range(0, n + 4)])
        if r in ("0", "q"):
            return None
        idx = int(r)
        if 1 <= idx <= n:
            return carpetas[idx - 1][1]
        if idx == n + 1:
            p = Path(input("  Arrastra la carpeta o archivo: ").strip().strip('"\' ')).expanduser()
            if p.exists():
                return p
            print(col("  no existe", "alto"))
            input("  Enter...")
        elif idx == n + 2:
            return crear_ejemplo()
        elif idx == n + 3:
            plataformas()
            input(col("\n  Enter...", "info"))


def crear_ejemplo():
    d = Path.cwd() / "ejemplo-huella"
    d.mkdir(exist_ok=True)
    (d / "cv.docx").write_bytes(_docx_bytes())
    (d / "foto.jpg").write_bytes(_jpeg_bytes())
    (d / "factura.pdf").write_bytes(_pdf_bytes())
    (d / "factura.pdf.exe").write_bytes(_pdf_bytes())
    (d / "foto-disfrazada.jpg").write_bytes(_pdf_bytes())
    (d / "presupuesto.pdf").write_bytes(_pdf_js_bytes())
    (d / "notas.png").write_bytes(_png_bytes())
    return d


def _docx_bytes():
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr("word/document.xml", '<w:document xmlns:w="x"><w:body><w:p>'
                   '<w:del w:id="1" w:author="Jefe"><w:r><w:delText>becario</w:delText></w:r></w:del>'
                   '<w:ins w:id="2" w:author="Ana"><w:r><w:t>responsable</w:t></w:r></w:ins></w:p></w:body></w:document>')
        z.writestr("docProps/core.xml", '<cp:coreProperties xmlns:cp="c" xmlns:dc="d">'
                   '<dc:creator>Ana Garcia</dc:creator><cp:lastModifiedBy>Ana Garcia</cp:lastModifiedBy></cp:coreProperties>')
        z.writestr("docProps/app.xml", '<Properties><Company>Consultora SL</Company></Properties>')
    return buf.getvalue()


def _jpeg_bytes():
    def entry(tag, typ, count, value):
        return struct.pack("<HHI", tag, typ, count) + value

    gps_off = 8 + 2 + 12 * 3 + 4
    gps = struct.pack("<H", 4)
    gps += entry(1, 2, 2, b"N\x00\x00\x00")
    gps += entry(2, 5, 3, struct.pack("<I", gps_off + 54))
    gps += entry(3, 2, 2, b"W\x00\x00\x00")
    gps += entry(4, 5, 3, struct.pack("<I", gps_off + 78))
    gps += struct.pack("<I", 0)
    gps += struct.pack("<II", 40, 1) + struct.pack("<II", 25, 1) + struct.pack("<II", 6000, 100)
    gps += struct.pack("<II", 3, 1) + struct.pack("<II", 42, 1) + struct.pack("<II", 1200, 100)
    ifd0 = struct.pack("<H", 3) + entry(0x010F, 2, 6, b"Apple\x00\x00\x00")
    ifd0 += entry(0x0110, 2, 10, b"iPhone 13\x00\x00")
    ifd0 += entry(0x8825, 4, 1, struct.pack("<I", gps_off)) + struct.pack("<I", 0)
    app1 = b"Exif\x00\x00" + b"II" + struct.pack("<HI", 42, 8) + ifd0 + gps
    return (b"\xff\xd8\xff\xe1" + struct.pack("!H", len(app1) + 2) + app1
            + b"\xff\xdb" + struct.pack("!H", 67) + b"\x00" + bytes(64)
            + b"\xff\xda" + struct.pack("!H", 8) + bytes(6) + bytes(20) + b"\xff\xd9")


def _pdf_bytes():
    return (b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n"
            b"4 0 obj<</Author(Ana Garcia)/Creator(Word)>>endobj\n"
            b"trailer<</Root 1 0 R/Info 4 0 R>>\n%%EOF\n")


def _pdf_js_bytes():
    return (b"%PDF-1.5\n1 0 obj<</Type/Catalog/OpenAction 5 0 R>>endobj\n"
            b"4 0 obj<</Author(Ana Garcia)/Creator(Word)>>endobj\n"
            b"5 0 obj<</S/JavaScript/JS(app.alert\\('hola'\\);)>>endobj\n"
            b"trailer<</Root 1 0 R/Info 4 0 R>>\n%%EOF\n")


def _png_bytes():
    def chunk(t, d):
        return struct.pack("!I", len(d)) + t + d + struct.pack("!I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack("!IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    txt = b"Software\x00Adobe Photoshop 24.0 (Windows)"
    return (PNG_FIRMA + chunk(b"IHDR", ihdr) + chunk(b"tEXt", txt)
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff")) + chunk(b"IEND", b""))


# --------------------------------------------------------------------------- #
# flujo
# --------------------------------------------------------------------------- #
def _es_relevante(p):
    suf = [s.lower() for s in p.suffixes]
    if not suf:
        return False
    if suf[-1] in EXTS:
        return True
    return len(suf) >= 2 and suf[-2] in EXTS


def recolectar(destino):
    if destino.is_file():
        return [destino] if _es_relevante(destino) else []
    return sorted(p for p in destino.rglob("*") if p.is_file() and _es_relevante(p))


def listar_y_elegir(resultados):
    orden = sorted(resultados, key=lambda r: (
        {"SOSPECHOSO": 0, "VIGILA": 1, "LIMPIO": 2}[veredicto(r)], -r["score"]))
    total = len(orden)
    pagina, por_pagina = 0, 30
    print(col(f"\n  {total} archivos encontrados", "info"))
    cuenta = {"SOSPECHOSO": 0, "VIGILA": 0, "LIMPIO": 0}
    for r in orden:
        cuenta[veredicto(r)] += 1
    if cuenta["SOSPECHOSO"]:
        print(col(f"  {cuenta['SOSPECHOSO']} sospechosos, {cuenta['VIGILA']} a vigilar, "
                  f"{cuenta['LIMPIO']} limpios\n", "raro"))
    else:
        print(col(f"  {cuenta['VIGILA']} a vigilar, {cuenta['LIMPIO']} limpios\n", "medio"))

    while True:
        trozo = orden[pagina * por_pagina:(pagina + 1) * por_pagina]
        for i, r in enumerate(trozo, pagina * por_pagina + 1):
            v = veredicto(r)
            k = {"SOSPECHOSO": "raro", "VIGILA": "medio", "LIMPIO": "bien"}[v]
            nq = len([x for x in r["plan"]["quita"] if not x["t"].startswith("nada")])
            marca = col(v[:10].ljust(11), k)
            print(f"  {i:>3}) {marca}{r['score']:>3}/100  {r['fichero'].name[:38]:<38} "
                  f"{col(str(nq) + ' a quitar', 'plan')}")
        fin = (pagina + 1) * por_pagina >= total
        if not fin:
            print(col(f"\n  Enter = siguientes 30 ({total - (pagina + 1) * por_pagina} más)", "info"))
        linea()
        print(col("  Escribe números (1,4,7-9) · t = todos · n = ninguno · q = salir", "info"))
        try:
            entrada = input(col("  Selección: ", "t")).strip()
        except (EOFError, KeyboardInterrupt):
            return []
        if entrada == "" and not fin:
            pagina += 1
            continue
        if entrada.lower() == "q":
            return []
        sel = parsear_seleccion(entrada, total)
        if sel:
            return [orden[i] for i in sel]
        print(col("  nada seleccionado", "medio"))


def mostrar(ruta, r, plan):
    v = veredicto(r)
    k = {"SOSPECHOSO": "raro", "VIGILA": "medio", "LIMPIO": "bien"}[v]
    print()
    print(f"  {col(ruta.name, 'ok')}   {col(v, k)}   {r['score']}/100")
    linea()

    for gravedad, etiqueta, color in (("raro", "RARO", "raro"),
                                      ("aviso", "aviso", "medio"),
                                      ("bien", "bien", "bien")):
        bloque = [x for x in r["rarezas"] if x["g"] == gravedad]
        if not bloque:
            continue
        if gravedad == "bien":
            print(col("  --- lo que está bien ---", "info"))
        for x in bloque:
            print(f"  {col('[' + etiqueta + ']', color)} {x['t']}")
            if x["p"]:
                print(col(f"         posible: {x['p']}", "pos"))

    if r["hallazgos"]:
        print(col("  --- metadatos ---", "info"))
        for h in sorted(r["hallazgos"], key=lambda x: SEV_O[x["severidad"]]):
            print(f"  {col('[' + h['severidad'].upper() + ']', h['severidad'])} {h['campo']}: {h['valor']}")
        if r["info"].get("lat"):
            la, lo = r["info"]["lat"], r["info"]["lon"]
            print(col(f"  -> https://www.openstreetmap.org/?mlat={la}&mlon={lo}#map=17/{la}/{lo}", "t"))

    linea()
    if plan["nada"] and plan["quita"] and plan["quita"][0]["t"].startswith("nada"):
        print(col("  --- limpieza ---", "info"))
        print(f"  {col('[nada]', 'info')} {plan['quita'][0]['t']}")
    else:
        total = sum(x["bytes"] for x in plan["quita"])
        print(col(f"  --- SE VA A QUITAR ({len(plan['quita'])} elemento(s), {total} bytes) ---", "quita"))
        for x in plan["quita"]:
            print(f"  {col('[quita]', 'quita')} {x['t']}")
        print(col("  --- se conserva ---", "info"))
        for x in plan["conserva"]:
            print(f"  {col('[queda]', 'bien')} {x}")
        previsto = max(0, ruta.stat().st_size - total)
        print(col(f"  --- resultado previsto: ~{previsto} bytes "
                  f"(el original tiene {ruta.stat().st_size}) ---", "plan"))
    linea()


def revisar(destino):
    base = destino if destino.is_dir() else destino.parent
    limpio_dir, respaldo_dir = base / "limpio", base / "originales"

    limpia()
    print(col("\n  Mirando...", "info"), end="", flush=True)
    ficheros = recolectar(destino)
    print(col(f" {len(ficheros)}\n", "info"))
    if not ficheros:
        print("  No hay fotos ni documentos ahí.")
        input(col("\n  Enter...", "info"))
        return

    resultados = [analyze_file(p) for p in ficheros]
    elegidos = listar_y_elegir(resultados)
    if not elegidos:
        return

    limpiar_resto = False
    hechos = saltados = fallos = quitados_tot = bytes_tot = 0
    registro = base / "huella-registro.txt"

    for r in elegidos:
        ruta = r["fichero"]
        plan = r["plan"]
        try:
            antes = ruta.stat().st_size
        except OSError:
            antes = 0

        limpia()
        mostrar(ruta, r, plan)

        if SECO:
            accion = "l"
        elif limpiar_resto:
            accion = "l"
            print(col("  (automático: limpiar el resto)", "info"))
        else:
            print(col("  [l] limpiar   [b] limpiar y sustituir   [v] abrir mapa   "
                      "[s] saltar   [t] limpiar el resto   [q] salir", "info"))
            accion = preguntar("  ¿Qué hago? ", ["l", "b", "v", "s", "t", "q"])

        if accion == "q":
            break
        if accion == "t":
            limpiar_resto, accion = True, "l"
        if accion == "v":
            if r["info"].get("lat"):
                abrir(f"https://www.openstreetmap.org/?mlat={r['info']['lat']}&mlon={r['info']['lon']}")
            accion = preguntar("  ¿Y ahora? [l] limpiar [b] sustituir [s] saltar [t] resto [q] salir ",
                               ["l", "b", "s", "t", "q"])
            if accion == "q":
                break
            if accion == "t":
                limpiar_resto, accion = True, "l"
        if accion == "s":
            saltados += 1
            registrar(base, "SALTADO", ruta, "", antes, None, None, "sin tocar")
            print(col("  saltado", "info"))
            input(col("  Enter...", "info"))
            continue

        if not SECO and not limpiar_resto and plan["quita"] and not plan["nada"]:
            if preguntar(f"  ¿Confirmar {len(plan['quita'])} elemento(s) y "
                         f"{sum(x['bytes'] for x in plan['quita'])} bytes? [s/n] ", ["s", "n"]) == "n":
                saltados += 1
                registrar(base, "CANCELADO", ruta, "", antes, None, None, "el usuario dijo no")
                continue

        tmp = None
        destino_real = None
        referencia = ruta
        comprobado = ruta
        try:
            if SECO:
                fd, tp = tempfile.mkstemp(suffix=ruta.suffix)
                os.close(fd)
                tmp = Path(tp)
                limpiar_a(ruta, tmp)
                comprobado = tmp
            elif accion == "b":
                respaldo_dir.mkdir(exist_ok=True)
                respaldo = respaldo_dir / ruta.name
                shutil.copy2(ruta, respaldo)
                referencia = respaldo
                limpiar_a(ruta, ruta)
                destino_real = ruta
                comprobado = ruta
            else:
                dst = limpio_dir / ruta.name
                n = 2
                while dst.exists():
                    dst = limpio_dir / f"{ruta.stem}-{n}{ruta.suffix}"
                    n += 1
                limpiar_a(ruta, dst)
                destino_real = dst
                comprobado = dst
        except Exception as exc:
            fallos += 1
            registrar(base, "ERROR", ruta, "", antes, None, None, str(exc)[:60])
            print(col(f"  error: {exc}", "alto"))
            if accion == "b" and (respaldo_dir / ruta.name).exists():
                shutil.copy2(respaldo_dir / ruta.name, ruta)
                print(col("  original restaurado desde originales/", "medio"))
            if tmp and tmp.exists():
                tmp.unlink()
            input(col("  Enter...", "info"))
            continue

        despues = comprobado.stat().st_size
        res = verificar(referencia, comprobado, ruta.suffix.lower())

        print()
        print(col("  --- INFORME ---", "ok"))
        for x in plan["quita"]:
            if not x["t"].startswith("nada"):
                print(f"  {col('[hecho]', 'ok')} quitado: {x['t']}")
        print(col(f"  [dato] {antes} -> {despues} bytes ({antes - despues:+d}, "
                  f"{100 * (antes - despues) / antes if antes else 0:.1f} %)", "info"))
        for x in res["bien"]:
            print(col(f"  [ok] {x}", "bien"))
        for x in res["problemas"]:
            print(col(f"  [fallo] {x}", "alto"))

        if res["ok"]:
            hechos += 1
            quitados_tot += len([x for x in plan["quita"] if not x["t"].startswith("nada")])
            bytes_tot += max(0, antes - despues)
            if destino_real:
                print(col(f"  guardado en {destino_real}", "ok"))
            registrar(base, "SECO" if SECO else ("SUSTITUIDO" if accion == "b" else "LIMPIADO"),
                      ruta, "; ".join(x["t"] for x in plan["quita"] if not x["t"].startswith("nada")),
                      antes, despues, str(destino_real) if destino_real else "(temporal)", "verificado")
        else:
            fallos += 1
            print(col("  el resultado no pasa la comprobación", "alto"))
            if accion == "b" and referencia.exists():
                shutil.copy2(referencia, ruta)
                print(col("  original restaurado desde originales/", "medio"))
            elif destino_real and destino_real.exists():
                destino_real.unlink()
                print(col("  copia descartada", "medio"))
            registrar(base, "FALLO-VERIFICACION", ruta,
                      "; ".join(res["problemas"]), antes, despues,
                      str(destino_real) if destino_real else "-", "restaurado")

        if SECO and tmp and tmp.exists():
            tmp.unlink()
        input(col("\n  Enter...", "info"))

    limpia()
    linea()
    print(f"\n  {len(elegidos)} elegidos · {hechos} limpiados · {saltados} saltados · {fallos} con fallo")
    if not SECO:
        print(f"  {quitados_tot} elementos eliminados · {bytes_tot} bytes liberados")
        print(col(f"  Registro: {registro}", "info"))
        if limpio_dir.is_dir():
            print(col(f"  Copias limpias en: {limpio_dir}", "ok"))
            print(col("  (los originales siguen intactos)", "info"))
            if preguntar("\n  ¿Abrir la carpeta? [s/n] ", ["s", "n"]) == "s":
                abrir(limpio_dir)
    print()
    input(col("  Enter para volver...", "info"))


def main():
    global SECO
    SECO = "--seco" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        p = Path(args[0]).expanduser()
        if p.exists():
            revisar(p)
        else:
            print(f"No existe: {p}")
        return
    while True:
        destino = menu_principal()
        if destino is None:
            print("\n  Hasta luego.\n")
            return
        revisar(destino)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Cancelado.\n")
        