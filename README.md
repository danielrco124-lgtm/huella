# Huella

Herramienta local de auditoría, inspección y limpieza de metadatos y rastros ocultos en archivos (imágenes, documentos de Office y PDFs).

## Descripción

Huella es una utilidad desarrollada en Python orientada a la privacidad y la seguridad defensiva local. Permite analizar el contenido interno de diversos formatos de archivo para detectar metadatos sensibles (como coordenadas GPS, datos de autoría, histórico de ediciones y comentarios), así como posibles vectores de riesgo (como scripts ejecutables, dobles extensiones, caracteres de inversión de orden RTL o macros ocultas).

Todas las operaciones de análisis y limpieza se realizan de forma local, garantizando que los archivos no sean enviados a servidores externos.

## Características Principales

- **Inspección Profunda:** Verificación de cabeceras, firmas mágicas, integridad de bloques y detección de payloads o datos añadidos tras los marcadores de fin de archivo.
- **Análisis de Metadatos:** Identificación de metadatos sensibles en imágenes (EXIF, XMP, GPS), documentos de Office (autor, empresa, cambios no aceptados, comentarios) y archivos PDF (autor, creador, JavaScript incrustado).
- **Limpieza Segura:** Reescritura limpia del archivo conservando únicamente los flujos y estructuras legítimas necesarios para su correcto funcionamiento.
- **Doble Verificación y Rollback:** El archivo resultante se relee y verifica de forma automática tras el proceso de limpieza. Si la comprobación falla, el archivo original se restaura de manera automática.
- **Modo Seguro (--seco):** Permite ejecutar auditorías completas en modo de solo lectura, sin modificar ni escribir ningún archivo en disco.

## Requisitos del Sistema

- Python 3.x
- No requiere dependencias de terceros (utiliza exclusivamente la librería estándar de Python).

## Modo de Uso

Ejecutar la herramienta de forma interactiva seleccionando el origen mediante menús:

```bash
python huella.py
```

Ejecutar en modo de solo lectura (modo seco, sin realizar modificaciones):

```bash
python huella.py --seco
```

Indicar una ruta específica como argumento de entrada:

```bash
python huella.py /ruta/a/la/carpeta
```

## Estructura de Salida y Registros

- `limpio/`: Directorio donde se almacenan las copias de los archivos procesados y limpios.
- `originales/`: Directorio de respaldo que almacena copias de seguridad de los archivos originales antes de aplicar la sustitución.
- `huella-registro.txt`: Archivo de registro cronológico con el detalle de las operaciones, tamaños antes y después, y estado de la verificación.

## Autor

Daniel (danielrco124)

