# Prueba de reproducción de YouTube

Abrir **http://127.0.0.1:8788/?prueba=youtube** con el puente activo. También hay un enlace en la pantalla de acceso. No requiere una cuenta del estudio ni conexión a las APIs Python para cargar la pantalla.

1. Pegar el enlace HTTPS de un video (o su ID de 11 caracteres).
2. Permitir expresamente la conexión al reproductor de YouTube.
3. Pulsar **Cargar video** y después **Reproducir** en sus controles oficiales.
4. Mantener el reproductor a la vista. **Detener y retirar video** destruye el reproductor; retirar el permiso hace lo mismo.

No descarga, convierte, extrae audio, busca resultados ni necesita una clave de YouTube Data API. Usa la [IFrame Player API oficial](https://developers.google.com/youtube/iframe_api_reference) y un reproductor visible. No oculta controles, no elimina anuncios y no omite restricciones de inserción o autenticación.

La página comunica que utiliza servicios de YouTube y enlaza sus términos y la política de privacidad de Google. Solo solicita conectar con YouTube tras la acción explícita del usuario. No envía el perfil, tokens del sistema, respuestas de tonos o encuestas. El ID del video permanece en memoria de la pestaña, sin almacenamiento en MongoDB.

Los errores 100 (video no disponible), 101/150 (inserción no permitida), 153 (origen no verificable), problemas de red y carga no confirmada se muestran al usuario. Se conserva el referrer de origen con `strict-origin-when-cross-origin`. Un reproductor bloqueado no se sustituye por extracción de audio ni por un proxy de YouTube.

Se solicita pausa al ocultar la pestaña o cuando menos de la mitad del reproductor está en el área visible. Esto no detecta de forma universal el uso de otra aplicación nativa: pausar antes de entrar en Unreal. La prueba no está diseñada para reproducción de fondo durante VR, de acuerdo con las [políticas de YouTube](https://developers.google.com/youtube/terms/developer-policies).

## Alcance frente al catálogo

Esta primera prueba no modifica `songsV2`, no crea registros `audios`, no interviene en las recomendaciones y no guarda eventos de investigación. Un video pegado no se considera equivalente a una pista del catálogo automáticamente.

Para integrar después videos con recomendaciones será necesario verificar la correspondencia entre `track_id` y video/grabación, definir la fuente de reproducción en el backend y adaptar el registro de eventos. Esa asociación y la evaluación VR no quedan resueltas por mostrar un iframe.

## Verificación

Se añadieron pruebas de enlaces permitidos, rechazo de dominios ajenos, credenciales y entradas inválidas, y mensajes de errores. La suite completa contiene 10 pruebas aprobadas; la compilación de producción también pasó. La disponibilidad de un video y la reproducción efectiva dependen de YouTube, del navegador y de la red; una compilación correcta no prueba por sí sola que se pueda reproducir cualquier video.

Se comprobó además en el navegador local la carga del video técnico `M7lc1UVf-VE`, utilizado en la documentación oficial de la API: apareció el reproductor de YouTube y se observaron los estados de reproducción y pausa. No se utilizó una canción del catálogo para esta verificación ni se declaró correspondencia con un `track_id`. La captura `youtube-prueba.png` documenta la prueba web.
