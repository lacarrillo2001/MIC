# Recomendaciones con búsqueda automática en YouTube

## Activación

La integración está implementada, pero necesita una clave propia de **YouTube Data API v3**. No se incluye una clave de demostración ni se reutilizan credenciales del proyecto anterior.

1. En Google Cloud, habilitar YouTube Data API v3 y crear una API key. Restringirla a esa API y aplicar las restricciones de servidor adecuadas; no usar una clave de frontend restringida por referrer para estas solicitudes de backend.
2. Añadirla únicamente al `.env` del backend:

```dotenv
YOUTUBE_API_KEY=TU_CLAVE_PRIVADA
YOUTUBE_REGION=EC
YOUTUBE_MAX_SEARCHES_PER_DAY=50
```

No pegar la clave en el chat, React, enlaces o archivos versionados. `.env` está ignorado por Git. Se envía a Google en el header `X-Goog-Api-Key`, no dentro de las URL ni las respuestas públicas.

3. Para una base ya inicializada, ejecutar una vez la migración **aditiva** de permisos (ya aplicada en este equipo):

```powershell
Get-Content -Raw mongo/upgrade_youtube.js | docker compose exec -T mongo mongosh --quiet
```

En volúmenes nuevos, `mongo/init.js` incluye esos permisos desde el inicio. No borrar el volumen para aplicar este cambio.

4. Recrear solo el servicio de recomendación para cargar la variable:

```powershell
docker compose up -d --force-recreate recomendacion
```

El arranque vuelve a comprobar el catálogo sin duplicarlo. Si se usa `--wait`, añadir `--wait-timeout 900`.

5. Con el puente Node actualizado en ejecución, abrir **http://127.0.0.1:8788/?prueba=youtube-auto** e iniciar sesión. Autorizar la conexión a YouTube y pulsar **Recomendar y buscar automáticamente**. No es necesario pegar enlaces de canciones.

## Qué hace

Actualización del modo web: selección de candidatos sin depender del inicio del catálogo, diversidad y valoraciones corregibles. Véase [Recomendación web v2](RECOMENDACION_WEB_V2.md) para las reglas, el historial y la afinidad efectiva utilizada en próximas listas.

Recomienda hasta cinco canciones usando el perfil actual y las reglas musicales existentes. No exige archivos WAV porque esta lista es **solo web**, independiente de las sesiones de investigación VR. Guarda el perfil utilizado en `recomendaciones` con `tipo: youtube_web`, `sesion_id: null` y `estado_vinculacion: solo_web`; no permite aplicarles feedback de las sesiones VR.

Al resolver cada canción, el backend envía a Google solamente título y artista principal del catálogo. No envía el perfil, correo, respuestas auditivas, ID del participante ni tokens del sistema. Usa `search.list` y `videos.list` oficiales: comprueba título, artista, duración, inserción habilitada, estado público, restricciones de región y versiones. Rechaza covers, remixes o versiones en vivo no indicadas en la pista de origen. No se elige un video al azar si no hay coincidencia.

La coincidencia sigue siendo **probable por metadatos**, no verificación acústica. La tolerancia de duración es el máximo entre ocho segundos y 5 % de la duración del catálogo; es una regla técnica conservadora, no una validación científica. Un resultado insertable puede después dejar de estarlo o depender de la cuenta, región o navegador.

La web carga el reproductor oficial visible. El primer inicio puede requerir un clic. Al finalizar intenta buscar/cargar la siguiente canción; si el navegador bloquea el inicio automático lo indica. Videos retirados o con inserción denegada se omiten. Errores de clave, red o cuota no se convierten en coincidencias inventadas ni disparan reintentos infinitos.

## Caché y cuota

Se añadió **una colección** `youtube_vinculos`, propiedad del servicio de recomendación. No se añaden microservicios ni bases y no se modifica `songsV2` ni `artists`.

- Asociación por `track_id` y firma de los metadatos utilizados.
- Resultado disponible conservado hasta siete días; sin coincidencia, hasta seis horas.
- Índice TTL **solo en la caché**, nunca en canciones ni artistas. Mongo elimina físicamente las entradas vencidas de manera asíncrona; el resolver no utiliza una entrada caducada aunque todavía exista.
- Contador diario UTC y límite local configurable, aplicado atómicamente en MongoDB. El valor 50 es un límite interno conservador, no una promesa de cuota disponible de Google.
- Las búsquedas se hacen bajo demanda, no para las 402.301 canciones al importar o iniciar Compose. El perfil influye en el ranking musical, no en parámetros privados enviados a Google.

La política de retención de esta caché se mantiene por debajo del plazo máximo de actualización/borrado de metadatos de API. No se guardan estadísticas de popularidad ni se derivan métricas públicas de YouTube.

## Rutas protegidas

| Ruta de Catálogo | Función |
| --- | --- |
| `GET /youtube/configuracion` | Informa si hay clave, sin devolverla |
| `POST /youtube/recomendaciones` | Lista web personalizada e idempotente por solicitud |
| `POST /youtube/recomendaciones/{id}/resolver` | Resuelve únicamente una pista de la lista del propietario |

React las utiliza mediante `/backend/catalogo/...` del puente. No se expone un proxy genérico de Google ni un buscador arbitrario.

## Límites y verificación

Este modo no reproduce audio oculto ni de fondo durante Unreal. No crea una sesión VR, no registra medidas de atención y no convierte una omisión en rechazo del usuario. Las políticas, privacidad y anuncios del reproductor siguen aplicándose.

Las pruebas automatizadas usan respuestas simuladas de Google, con clave ficticia: verifican coincidencias, rechazos, caché, cuota, propiedad de listas, idempotencia y ausencia de exposición de la clave. La reproducción manual del reproductor oficial se comprobó previamente. **La búsqueda real no queda validada hasta configurar una clave propia** y probar títulos del catálogo con su cuota y restricciones reales.

Fuentes oficiales: [search.list](https://developers.google.com/youtube/v3/docs/search/list), [videos.list](https://developers.google.com/youtube/v3/docs/videos/list), [IFrame Player API](https://developers.google.com/youtube/iframe_api_reference), [políticas de YouTube](https://developers.google.com/youtube/terms/developer-policies), [manejo seguro de API keys](https://docs.cloud.google.com/docs/authentication/api-keys-best-practices).
