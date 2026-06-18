# Analista de Catálogos

Sistema de análisis automatizado de catálogos técnicos industriales. Procesa PDFs de proveedores, extrae datos de tablas y curvas de desempeño, y los indexa para comparar componentes y evaluar sustituciones.

## Qué hace

- Detecta y clasifica páginas de catálogos (tablas, curvas, texto)
- Extrae datos con pdfplumber para tablas y Claude API para gráficos
- Indexa los resultados en una base vectorial (Qdrant)
- Permite buscar equipos por características en lenguaje natural
- Compara un componente pedido contra un sustituto propuesto y genera un reporte

## Requisitos

- Docker Desktop instalado y corriendo
- Una API key de Anthropic (se obtiene en https://console.anthropic.com/settings/keys)

No se requiere instalar Python ni ninguna otra dependencia manualmente.

## Instalación

Clonar el repositorio:

```
git clone https://github.com/gelv9/analista_catalogo.git
cd analista_catalogo
```

Crear el archivo de configuración a partir de la plantilla:

```
cp .env.example .env
```

Abrir el archivo `.env` con cualquier editor de texto y reemplazar el valor con tu API key:

```
ANTHROPIC_API_KEY=sk-ant-tu-key-aqui
```

## Uso

Levantar los servicios:

```
docker compose up
```

La primera vez tarda unos minutos porque Docker descarga las imágenes base. Las veces siguientes arranca en segundos.

Una vez que la terminal muestre que los servicios están listos, abrir en el navegador:

```
http://localhost:8501
```

Para detener:

```
docker compose down
```

## Estructura del proyecto

```
analista_catalogo/
  app.py                   punto de entrada de la interfaz
  core/                    modulos del pipeline
    pipeline.py            orquestador principal
    detector.py            clasificacion de paginas
    extractor_curvas.py    lectura de graficos via Claude API
    extractor_tablas.py    lectura de tablas via pdfplumber
    comparador.py          motor de comparacion de productos
    indexador.py           escritura en Qdrant
    qdrant_client.py       cliente de base vectorial
    reporte_pdf.py         generacion de reportes
  schemas/                 definicion de datos con Pydantic
  prompts/                 prompts separados por funcion
  static/                  fuentes del tema visual
  tests/                   tests de los modulos principales
  docker-compose.yml       definicion de servicios
  Dockerfile               imagen de la aplicacion
  requirements.txt         dependencias Python
```

## Notas

La base vectorial de Qdrant persiste en un volumen de Docker. Los datos indexados se conservan entre reinicios.

Los catálogos procesados no se incluyen en el repositorio. Cada usuario sube sus propios archivos desde la interfaz.

La API key nunca se comparte ni se sube al repositorio. Cada usuario usa la suya propia.
