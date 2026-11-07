# NeuroSound: backend del prototipo

Tres APIs Python/FastAPI, tres contenedores y un único MongoDB dockerizado, base `neurosound`. No incluye interfaz web ni sala virtual. Implementa los tres servicios definidos en los Markdown del proyecto; no utiliza la conexión MongoDB ni las credenciales del NeuroSound anterior.

## Iniciar en Windows

Requisitos: Docker Desktop con motor Linux y Python 3.12 o superior para generar secretos y ejecutar pruebas locales.

Desde esta carpeta:

```powershell
python scripts/setup_env.py
docker compose up -d --build --wait --wait-timeout 900
docker compose ps
```

El primer comando crea `.env` con claves aleatorias; si existe, no lo modifica. No compartir ni subir ese archivo a Git. Conservarlo: las contraseñas iniciales de MongoDB se guardan en el volumen, no se cambian regenerando `.env`.

| API | Documentación interactiva | Colecciones propias |
| --- | --- | --- |
| Usuarios y perfiles | http://localhost:8001/docs | `usuarios`, `perfiles`, `evaluaciones_tonos` |
| Catálogo y recomendación | http://localhost:8002/docs | `songsV2`, `artists`, `recomendaciones`, `feedback`, `youtube_vinculos` |
| Sesiones y reproducción | http://localhost:8003/docs | `audios`, `sesiones`, `encuestas` |

Los puertos se publican **solo en localhost**. MongoDB no publica un puerto en el equipo. Los servicios usan cuentas distintas sobre **la misma base**, con escritura únicamente sobre sus propias colecciones. Las consultas entre servicios son HTTP autenticado, no accesos a colecciones ajenas.

### Colecciones al iniciar y reiniciar

En **cada arranque de cada API** se ejecutan `create_collection` e índices. Si ya existen, se mantienen; no se vacían ni reemplazan. Además, Recomendación comprueba e importa incrementalmente los dos JSON del catálogo antes de declararse preparada. Un error de conexión, permisos o incompatibilidad de índices impide que la API se declare preparada.

El script inicial de MongoDB solo crea cuentas y permisos en un volumen nuevo. No sustituye la inicialización de las colecciones ni la carga del catálogo que realiza Recomendación en cada arranque. No se crean participantes ni archivos musicales de ejemplo.

```powershell
docker compose restart usuarios recomendacion sesiones
docker compose logs --tail 50 usuarios recomendacion sesiones
```

`/health/live` indica proceso activo; `/health/ready` indica inicialización terminada y conexión propia con MongoDB. No es una prueba de salud de todos los otros servicios: una dependencia caída produce un error explícito al usarla.

Para detener sin borrar datos: `docker compose stop`. También `docker compose down` conserva el volumen. **No utilizar `down -v` sobre datos del estudio:** elimina el volumen. Hacer copias de seguridad antes de cambios de esquema o despliegue.

## Cargar el catálogo existente, sin conexión remota

La carga automática está habilitada en `docker-compose.yml`, dentro del servicio `recomendacion`, con `CATALOGUE_AUTO_IMPORT: "true"`. Usa exclusivamente copias locales, montadas en modo lectura:

| Archivo requerido | Colección | Fuente recibida |
| --- | --- | --- |
| `imports/artists.json` | `artists` | `LecturaYescritura.artists.json` · 31.180 registros |
| `imports/songsV2.json` | `songsV2` | `LecturaYescritura.songsV2.json` · 402.301 registros |

Las copias ya están preparadas en este equipo; los archivos originales de Descargas no se modifican. `imports/` está ignorado por Git y excluido de las imágenes: al trasladar el proyecto, copiar también estos dos JSON. No incluir credenciales.

Al iniciar o reiniciar **el contenedor de recomendación**, primero se validan ambos archivos completos y después se importan por lotes de 1.000 documentos. Se conservan los ObjectId de Extended JSON, arrays, campos adicionales y valores originales. Los parámetros no numéricos no se convierten en mediciones inventadas: el motor omite los que no puede utilizar.

Los registros existentes no se actualizan ni borran. Se omiten los idénticos y se cuentan las diferencias como `conflictos_conservados` en los logs; en el arranque esos conflictos son advertencias y se mantiene el registro de MongoDB. Una colisión concurrente de `_id` tampoco sobrescribe el documento. Si falta un archivo, el JSON es inválido o falla MongoDB, la API no se declara lista. No reemplazar los archivos mientras se están cargando.

Cada arranque vuelve a comprobar las fuentes; no se confía en una marca de "ya importado" que pueda dejar documentos faltantes sin recuperar. Si Compose encuentra el contenedor **ya ejecutándose** y no lo reinicia, no hay nuevo arranque ni necesidad de recargar. Para forzar una comprobación:

```powershell
docker compose restart recomendacion
docker compose logs -f recomendacion
```

La primera carga puede tardar varios minutos. El healthcheck concede hasta 10 minutos iniciales; con `--wait` usar `--wait-timeout 900`. Los logs muestran progreso, cantidades, conflictos y SHA-256 de cada fuente. No usar `down -v`: la carga incremental no necesita borrar el volumen.

Se mantiene también el comando manual, ahora con el mismo lector incremental y carga por lotes:

```powershell
docker compose exec -T recomendacion python -m shared.manage importar /imports/artists.json --coleccion artists
docker compose exec -T recomendacion python -m shared.manage importar /imports/songsV2.json --coleccion songsV2
```

El importador valida todos los documentos antes de comenzar. Conserva sus campos, reconoce `id` o `idros`, y exige arrays reales para `artists`, `id_artists` y `genres`. Si ambos identificadores existen y difieren, rechaza el archivo por ambigüedad. No impone índices únicos al catálogo existente.

Una interrupción puede dejar una importación parcial; el siguiente arranque añade lo que falta sin repetir documentos. El comando **manual** devuelve código 2 si detecta conflictos o colisiones concurrentes, conservando los documentos anteriores. No hay transacción de todo el archivo ni se elimina información. La verificación Docker aislada desactiva expresamente la importación automática para no cargar el catálogo real en sus fixtures.

## Registrar los archivos de audio

### Alternativa web: búsqueda automática de YouTube

La vista `http://127.0.0.1:8788/?prueba=youtube-auto` recomienda por perfil y busca automáticamente videos, sin pedir enlaces. Requiere configurar `YOUTUBE_API_KEY` **solo en el backend**. Tiene una caché temporal separada y no modifica el catálogo ni reemplaza el protocolo VR. Consultar [activación y alcance](docs/YOUTUBE_AUTOMATICO.md).

`downloaded: true` no basta para reproducir. Copiar archivos que se tenga derecho a utilizar en `media/`; se montan en modo lectura. En esta versión se registra **WAV PCM mono o estéreo**, para comprobar duración sin otro servicio ni ffmpeg. No se descargan canciones de YouTube o Spotify. Convertir previamente los archivos legalmente disponibles si están en otro formato.

Crear una cuenta de investigador desde el contenedor; la contraseña se solicita sin mostrarla:

```powershell
docker compose exec usuarios python -m shared.manage crear-investigador investigador@ejemplo.edu
```

Después de iniciar sesión mediante `/auth/login`, usar su token en `POST http://localhost:8003/audios`:

```json
{
  "tipo": "cancion",
  "track_id": "ID_REAL_DEL_CATALOGO",
  "ubicacion": "canciones/archivo.wav",
  "correspondencia_verificada": true,
  "fuente_autorizada": true
}
```

Estas dos declaraciones son responsabilidad del investigador: la aplicación comprueba archivo, formato, duración, huella SHA-256 y existencia del identificador; no determina por sí misma derechos de autor ni reconoce acústicamente la canción. No acepta rutas fuera de `media/`. Si el archivo cambia, deja de entregarlo y de recomendarlo. Una grabación distinta debe registrarse como un audio nuevo, con otro archivo; no sustituir un archivo de una sesión anterior.

Para tonos usar `tipo: "tono"`, `tono_id` y no `track_id`. La correspondencia entre frecuencia del audio y protocolo debe comprobarse previamente; el backend no analiza espectros.

## Flujo de integración

Todas las rutas públicas de datos requieren `Authorization: Bearer TOKEN`, salvo registro, login y canje del código temporal. `/docs` muestra los modelos y sus restricciones.

1. **Usuarios, puerto 8001:** `POST /auth/registro`, confirmando mayoría de edad y consentimiento; luego `POST /auth/login`. El registro solo crea estudiantes, no permite elegir rol. El frontend debe mostrar previamente el texto aprobado del consentimiento versión `consentimiento-v1`; ese texto jurídico/investigativo aún debe definirse fuera del backend.
2. **Catálogo, puerto 8002:** consultar `/catalogo/artistas` y `/catalogo/canciones`, con paginación. En **Usuarios**, `PUT /perfiles/me` guarda preferencias con `version_esperada`, IDs de artistas, géneros y tempo (`lento`, `moderado`, `rapido` o `null`). La afinidad aprendida comienza vacía.
3. **Opcional y bloqueado por defecto:** consultar `/tonos/configuracion`; una vez aprobado el protocolo y registrados sus audios, `POST /evaluaciones-tonos` inicia una evaluación, y `PUT /evaluaciones-tonos/{id}` la completa o interrumpe. La frecuencia y el audio enviados deben corresponder al tono configurado. Las omisiones no se convierten en cero.
4. **Sesiones, puerto 8003:** `POST /sesiones`, con `solicitud_id`, `actividad` (al menos ID y versión) y `modalidad: "personalizada"`. Se fija la versión de perfil y consentimiento. `personalizada_heuristica` exige evaluación de tonos completada y aprobada.
5. **Recomendación, puerto 8002:** `POST /recomendaciones` con `solicitud_id` y `sesion_id`. Guarda perfil, reglas, atributos, puntuaciones y archivos seleccionados; después asocia la selección con la sesión. Si se interrumpe la asociación, reenviar **el mismo** identificador permite retomarla. No se cambia el ranking ya guardado.
6. **Sesiones:** la web pide `POST /sesiones/{id}/vinculacion` y entrega el código a la sala virtual por un canal seguro. La sala llama `POST /sesiones/{id}/canje` con ese código, sin las credenciales generales del usuario. Caduca en 5 minutos, admite 5 intentos y solo se canjea una vez. El token de sala dura 30 minutos, solo sirve para esa sesión y no permite leer perfiles, música ni encuestas. El piloto debe caber en ese plazo; la renovación de sesiones largas queda pendiente.
7. **Sala virtual:** `POST /sesiones/{id}/estado` cambia a `activa`, `pausada`, `activa` y `finalizada`, o `interrumpida`. La web solo puede interrumpir. Iniciar exige una recomendación asociada y consentimiento vigente. La actividad de aprendizaje pertenece a la sala, no a este backend.
8. **Web:** descarga `GET /audios/{audio_id}/contenido?sesion_id=...` con su token, admite `Range`; reproduce y envía `POST /sesiones/{id}/eventos`. Para tonos utiliza `?evaluacion_id=...`. Un elemento HTML `<audio src>` no agrega por sí solo el Bearer: usar `fetch` autenticado y Blob, o una integración equivalente que mantenga la autorización. No enviar tokens en la URL.
9. **Recomendación:** `POST /feedback` declara `preferencia` y/o `molestia`. Un `me_gusta` sin molestia acerca `energy` y `valence` hacia los atributos de la canción con tasa 0,1. La primera evidencia inicializa solo los atributos conocidos. Rechazo/neutral/molestia se conservan, pero no inventan una regla inversa. Saltar una canción solo es un evento, no un rechazo automático. Los ajustes afectan futuras sesiones.
10. **Sesiones:** después de finalizar o interrumpir una actividad iniciada, `POST /sesiones/{id}/encuesta`. El cuestionario está bloqueado hasta su aprobación. No se calculan puntuaciones compuestas no definidas. `GET /investigacion/exportacion` permite al investigador descargar JSON paginado con sesiones, recomendaciones, feedback y encuestas, sin correos, contraseñas ni códigos. Los IDs estables son seudónimos, **no anonimización irreversible**.

Ejemplo de registro:

```json
{
  "email": "estudiante@ejemplo.edu",
  "password": "UNA_CONTRASENA_LARGA",
  "mayor_edad_confirmado": true,
  "consentimiento_aceptado": true,
  "consentimiento_version": "consentimiento-v1"
}
```

Reenvíos: conservar `solicitud_id` por operación; no reutilizarlo para otros datos. Recomendaciones y feedback lo deduplican por usuario; eventos usan `evento_id` dentro de su sesión. Un envío simultáneo que choque con un índice devuelve 409: consultar o reenviar la misma solicitud. Si un ajuste quedó pendiente, reenviar el mismo feedback o llamar `/feedback/{id}/reintentar`; el perfil comprueba atómicamente el ID del feedback junto a su versión. No existe cola ni trabajador adicional.

Si se pierde la confirmación original de un ajuste ya aplicado, el reintento registra la versión de perfil **observada**, dejando `perfil_version_resultante` en `null`: no inventa cuál fue la versión histórica exacta si hubo otros cambios entre tanto.

El estado de una sesión no se reconstruye a partir de heartbeats. Se admiten hasta 500 eventos embebidos, reservando 20 para cambios de actividad. La web informa reproducción, no se prueba escucha efectiva mediante sensores. El volumen es digital 0–1, **no dB en el oído**.

## Reglas y límites de esta primera versión

- `config/reglas-v1.json`: pesos experimentales adaptados del motor anterior, puntuación base 100, preferencias por IDs y géneros del artista, distancias de atributos conocidos y tempo. No usa popularidad como objetivo, ni impone estados emocionales. La puntuación puede superar 100 o ser negativa: no es porcentaje ni escala clínica. Los géneros son del artista, no clasificación verificada de cada canción.
- Se consideran hasta 1.000 candidatos: primero artistas/géneros preferidos y después catálogo por `_id`. Se devuelven hasta 15 con audio válido. No es una búsqueda exhaustiva; un archivo fuera de esa ventana puede no aparecer. Desempates por `track_id`. Sin evidencia de afinidad se informa ese hecho. Los atributos ausentes quedan en `null`, no se sustituyen por supuestas mediciones.
- La heurística clasifica por `acousticness`, `energy`, `loudness`, `danceability` e `instrumentalness`, **no calcula frecuencia de la canción**. Mantiene separada su penalización. Las etiquetas heredadas Graves/Medios/Agudos no son límites acústicos ni criterios de seguridad. Su utilidad debe evaluarse, no asumirse.
- `tonos-v1.json` y `cuestionario-v1.json` tienen `aprobado: false`. La duración de tonos es `null`; los Hz, escalas y preguntas son borradores técnicos. No activarlos solo para quitar un error: definir protocolo, instrucciones, límites de exposición y equipo con la supervisión del estudio; registrar audios y conservar una versión identificable. La encuesta mide percepción, no atención objetiva. Las modalidades todavía no constituyen un diseño experimental aprobado ni una condición control definitiva.
- Las configuraciones utilizadas se copian dentro del registro. Al cambiar un protocolo o reglas, cambiar también su versión y conservar los archivos anteriores. No se fuerza la sustitución de datos de sesiones previas.
- El retiro bloquea operaciones posteriores incluso con un token emitido antes. No elimina automáticamente datos: definir retención, acceso, retiro y respaldo antes de incorporar participantes reales.
- Prototipo local, no despliegue público: antes de exponerlo se requieren HTTPS, límites de tasa externos para autenticación/canje, recuperación de contraseñas, rotación de secretos, copias de seguridad y revisión de privacidad. El límite HTTP de escritura es 64 KiB. La lista de feedback aplicados permanece embebida y es adecuada solo para el piloto.

## Pruebas

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas automatizadas usan una base simulada en memoria y audios sintéticos temporales, no el catálogo ni la base del estudio. Cubren arranque repetido, índices, consentimiento, permisos, perfil, flujo de sesión, reproducción parcial, eventos, feedback deduplicado y protocolos pendientes. Esta prueba no demuestra eficacia sobre atención ni reemplaza las pruebas con el cliente web y la sala reales.

Prueba adicional con MongoDB y HTTP reales:

```powershell
.\.venv\Scripts\python.exe scripts/verify_docker.py
```

Levanta temporalmente el proyecto **neurosound-verificacion**, con otros puertos (18001–18003), red y volumen propios. Usa solamente un usuario, catálogo y WAV sintéticos; comprueba flujo, permisos y reinicios. Al terminar elimina exclusivamente sus contenedores y su volumen temporal. No toca `neurosound_mongo_data`. Si ya existen recursos con el nombre de verificación, se detiene antes de modificarlos. Requiere Docker Compose compatible con `!override`.

Rutas de código: `usuarios/app.py`, `recomendacion/app.py` + `engine.py`, `sesiones/app.py`, infraestructura mínima `shared/`. No hay API gateway, broker, Redis, Kubernetes ni otra base.
