# Catálogo local y carga automática

## Fuentes conservadas

| Colección | Archivo original | Copia para Compose | Registros |
| --- | --- | --- | ---: |
| `artists` | `LecturaYescritura.artists.json` | `imports/artists.json` | 31.180 |
| `songsV2` | `LecturaYescritura.songsV2.json` | `imports/songsV2.json` | 402.301 |

Los archivos originales de Descargas no se modificaron. Las copias coinciden byte a byte según SHA-256:

- Artistas: `06d5cecefa9483482a4df62ef8d8b9c42bbb6e186ee7115c5e3e720e82808828`.
- Canciones: `2776311bea2b4879e8213b9d95d69f847cc18aa65612873d9d77c906a5cb3a9a`.

En la primera importación MongoDB tenía cero artistas y cero canciones. Se insertaron ambos archivos completos, sin conflictos ni colisiones. Se conservaron los ObjectId, los arrays y los atributos originales; no se limpiaron ni reemplazaron valores musicales desconocidos.

## Ejecución

El servicio de recomendación ejecuta `shared/catalogue.py` durante su inicialización, después de crear sus colecciones e índices y antes de declararse preparado. Se validan ambos archivos completos y se insertan solo registros faltantes, por lotes de 1.000, leyendo incrementalmente JSON array/JSON Lines y Extended JSON.

En cada arranque vuelve a comprobar las fuentes y el contenido existente. No borra, no vacía colecciones y no cambia registros diferentes: los conserva y los cuenta para revisión. Si Compose deja un contenedor ya iniciado sin reiniciarlo, no se vuelve a ejecutar su inicialización. `docker compose restart recomendacion` fuerza la comprobación.

Las fechas Extended JSON sin zona explícita y las fechas UTC devueltas por PyMongo se comparan por el mismo instante UTC. La normalización es solo para comparar: no reescribe fechas. Se incorporó una prueba de regresión para evitar avisos falsos debidos únicamente a la representación de zona horaria.

No se añadieron contenedores, bases ni colecciones auxiliares. Las fuentes están montadas en modo lectura e ignoradas por Git. Al trasladar el proyecto deben trasladarse también ambos archivos. Los datos de MongoDB permanecen en su volumen persistente.

## Cobertura de artistas en las fuentes

| Comprobación sobre los JSON originales | Cantidad |
| --- | ---: |
| Canciones con al menos un artista presente en `artists` | 372.914 |
| Canciones con todos sus artistas presentes | 333.214 |
| Canciones sin ningún artista presente | 29.387 |
| IDs distintos de artistas referenciados pero ausentes | 42.832 |

Estas ausencias ya existen en las fuentes, no son registros perdidos por la importación. Se mantienen todas las canciones. No se inventan artistas o géneros para completarlas; las canciones sin coincidencia no aportan evidencia de afinidad basada en los géneros de sus artistas.

`downloaded: true` no acredita disponibilidad del audio. La importación carga metadatos, no descarga ni registra archivos musicales. La reproducción todavía requiere archivos autorizados y verificados en `audios`.

## Verificación

Se ejecutaron 26 pruebas automatizadas aprobadas, incluidas lectura incremental, Extended JSON, archivos inválidos, validación antes de escribir, reenvío sin duplicación, conservación de conflictos y fechas UTC. Se verificó además el catálogo real en MongoDB y la ausencia de IDs de canción duplicados.

Los resúmenes de cada arranque aparecen en `docker compose logs recomendacion`, con conteos, conflictos y SHA-256. El healthcheck de recomendación concede tiempo para la carga inicial; utilizar `--wait-timeout 900` al esperar Compose.

Resultado del arranque repetido con el comparador UTC corregido:

| Colección | Insertados nuevamente | Reconocidos idénticos | Conflictos | Total en MongoDB |
| --- | ---: | ---: | ---: | ---: |
| `artists` | 0 | 31.180 | 0 | 31.180 |
| `songsV2` | 0 | 402.301 | 0 | 402.301 |

Se comprobaron además cero IDs duplicados en ambas colecciones y cero canciones sin `id`. El servicio volvió a responder `/health/ready` con HTTP 200 después de la comprobación.
