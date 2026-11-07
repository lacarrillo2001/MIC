# Descarga bajo demanda y reproducción web

Implementado el 3 de noviembre de 2026 dentro de los tres servicios existentes.

## Recorrido

En el panel principal `/`, la sección Música permite usar el perfil guardado para preparar una lista web. Al seleccionar una canción:

1. Sesiones comprueba que la lista pertenece al usuario y contiene el track_id solicitado.
2. Busca un audio con la misma firma de título, artistas, duración y track_id.
3. Si ya existe el archivo, lo reutiliza. Si falta, encola una descarga (una simultánea por proceso).
4. Busca hasta cinco resultados con yt-dlp y comprueba título, artista, duración y versiones. Se rechazan, entre otras, versiones BASS BOOSTED, remixes o covers no presentes en el nombre original.
5. Descarga el audio seleccionado y utiliza FFmpeg para convertirlo realmente a MP3. FFprobe comprueba codec y duración; se calcula SHA-256.
6. Guarda el archivo bajo `/media/descargas/<audio_id>/audio.mp3` y sus metadatos en la colección existente `audios`.
7. La interfaz consulta el estado y carga el archivo en un elemento audio nativo. Permite pausa, volumen, búsqueda temporal, siguiente canción y valoraciones explícitas.

### Cola de reproducción

El panel muestra todas las canciones recomendadas y permite seleccionarlas directamente. Los botones Canción anterior y Siguiente canción cambian la selección y solicitan continuar la reproducción. Al terminar un archivo, se pasa automáticamente al siguiente, conservando el volumen elegido. Si el navegador bloquea el inicio automático, se muestra «Pulsa Reproducir para continuar la lista».

Un fallo definitivo de preparación o de decodificación marca la canción como no disponible y avanza a la siguiente. Los errores de conexión o de autenticación no se convierten en rechazos musicales. Cuando el servidor tiene otra descarga en curso, se espera y se vuelve a consultar antes de agotar seis minutos. Al terminar la última pista se informa que finalizó la lista y permanecen disponibles la selección manual y la preparación de otra lista.

Verificación adicional de la cola: en el entorno aislado, una pista con fallo simulado se omitió y dos archivos WAV sintéticos de cuatro segundos se reprodujeron consecutivamente por su final natural. Se comprobaron selección directa, anterior, siguiente, detener y el estado final. No se modificaron historiales reales. Evidencia: `studyroom-integrado/docs/cola-reproduccion-prueba.png`.

No se acepta una URL arbitraria desde el navegador. No se importaron cookies, contraseñas o proxies del proyecto anterior. Un rechazo de acceso se registra como error; no se intenta eludirlo. La coincidencia por metadatos no acredita identidad acústica o autorización de reutilización. Se mantienen `fuente_autorizada=false` y `correspondencia_verificada=false` hasta una verificación específica; esos archivos no se incorporan automáticamente al protocolo VR de audios verificados.

## API

- POST `/descargas` con recomendacion_id y track_id: devuelve audio_id y estado.
- GET `/descargas/{audio_id}?recomendacion_id=...`: estado autenticado, con comprobación de pertenencia.
- GET `/descargas/{audio_id}/contenido?recomendacion_id=...`: archivo autenticado con soporte HTTP Range.
- GET `/youtube/recomendaciones/{id}/feedback?track_id=...`: respuesta vigente, sin consultar Google, para corregir valoraciones anteriores también desde el reproductor de audio.

El modo audio de la lista web no necesita YouTube Data API key. La URL `/?prueba=youtube-auto` conserva su reproductor oficial y su flujo anterior; mantiene el requisito de clave para las búsquedas oficiales.

## Persistencia y límites

`./media` se monta con escritura en el contenedor de sesiones; Compose y los reinicios conservan los archivos. MongoDB sigue en su mismo volumen. No se crean microservicios ni colecciones nuevas.

Se admiten pistas de 15 segundos a 20 minutos y archivos de hasta 80 MiB. La búsqueda y la descarga tienen tiempos máximos; no hay reintentos infinitos. El frontend deja de esperar después de seis minutos y ofrece reintentar. Una descarga en curso continúa en el servidor aunque se cambie de pista. Si hay otra descarga activa, se informa que debe esperarse; el usuario puede reintentar después.

La clave de caché incluye track_id y metadatos: no se deduplican grabaciones equivalentes que tengan identificadores diferentes. La caché no tiene una política automática de borrado ni cuota total de disco en esta primera versión; debe supervisarse el espacio local. La caché de archivos es distinta de los vínculos temporales de YouTube Data API.

`analisis_acustico=pendiente` reserva el estado para la fase posterior. Todavía no se calculan bandas, centroide, rolloff o RMS. El original recuperado se convierte a MP3; no se conserva además una copia sin conversión. Para análisis que requieran conservar el original habrá que añadir esa conservación antes de extraer los parámetros.

La música web se reproduce en el navegador y todavía no inicia ni finaliza automáticamente las sesiones de Unreal. Los controles VR y su cuestionario mantienen sus condiciones anteriores.

## Dependencias

El contenedor incluye FFmpeg/FFprobe, yt-dlp 2026.10.26 con sus dependencias default y Node 22 para el runtime JavaScript. Véase la [documentación oficial de dependencias de yt-dlp](https://github.com/yt-dlp/yt-dlp#dependencies). No se utiliza la técnica anterior de renombrar un contenedor desconocido como .mp3.

## Verificación real y automatizada

- 52 pruebas Python aprobadas; 11 del puente aprobadas; build Vite correcto.
- Pruebas de pertenencia, pista no incluida, caché, solicitudes Range, errores de preparación y rechazo de versiones alteradas.
- Descarga real de Chufuku: MP3 disponible, duración comprobada 194.496 ms, video 0-Qv9l42Zwg.
- En el panel principal autenticado, Tumba la Casa Sola no encontró/preparó un audio compatible y mostró error. Se pudo continuar a la siguiente canción.
- Blank Frank - 2004 Digital Remaster, de Brian Eno, se descargó y se reprodujo en el elemento audio del navegador. Se observó 0:19 / 3:37 y se pausó al terminar la prueba. No se enviaron valoraciones ni se modificaron preferencias.
- Al detener y volver a solicitar la misma canción, se recuperó el archivo disponible y el reproductor quedó listo de nuevo, sin repetir la preparación.
- Evidencia: `studyroom-integrado/docs/audio-descargado-reproduccion-real.png`.

Las descargas dependen de la disponibilidad y las restricciones de la fuente; estos éxitos no garantizan que todas las canciones del catálogo puedan descargarse.
