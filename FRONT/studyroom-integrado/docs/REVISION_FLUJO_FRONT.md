# Revisión del flujo principal — 3 de noviembre de 2026

## Aclaración de alcance

La URL `http://127.0.0.1:8788/?prueba=youtube-auto` es el flujo existente de recomendaciones y reproducción YouTube. No requiere los archivos locales de la colección audios. El hallazgo de cero archivos registrados bloquea la reproducción local del panel `/`, no demuestra un fallo de la vista YouTube. La revisión siguiente corresponde al panel `/` y no debe interpretarse como una revisión funcional negativa del reproductor YouTube.

El recorrido implementado en youtube-auto es acceso → preferencias → autorización de conexión → recomendación de canciones → búsqueda por título/artista/duración → reproductor oficial → registro de reproducción → valoración explícita → siguiente canción o nueva lista.

### Verificación posterior en la URL real, con sesión iniciada por el usuario

- Se conservaron las preferencias originales: artista Emus DJ, género ambiental y tempo moderado; no se editaron ni se guardaron nuevas respuestas.
- Al solicitar recomendaciones se generó una lista de cinco y apareció «Géneros utilizados: ambient», confirmando la normalización del perfil anterior.
- El primer resultado fue Chufuku, del canal Emus DJ - Topic. El reproductor oficial avanzó a tres segundos y mostró «Reproduciendo desde YouTube».
- Las valoraciones se habilitaron después del inicio registrado. No se pulsó ninguna valoración.
- «Siguiente canción» cargó la segunda recomendación, Tumba la Casa Sola. La coincidencia guardada sigue siendo una versión titulada BASS BOOSTED de CT SOUND BASS: persiste el problema de verificación de versiones identificado en la auditoría musical.
- La segunda pista quedó esperando pulsar Reproducir. No se verificó continuación al final natural de una canción ni reproducción automática de la segunda.
- «Detener» retiró el reproductor y mostró «Reproducción detenida».

Esta comprobación sí generó una recomendación real y registró el inicio de reproducción. No se crearon sesiones VR ni se modificaron gustos. La evidencia `youtube-auto-reproduccion-real.png` corresponde a la reproducción real de Chufuku, no a una simulación.

## Alcance

Se abrió el frontend real en `http://127.0.0.1:8788/`: mostró acceso y enlaces a las dos pruebas YouTube. No se ingresaron credenciales reales ni se registraron usuarios. El recorrido posterior se probó en 8792 con cuenta, recomendaciones y servicios sintéticos. La consulta a MongoDB real fue de solo lectura: cero audios de canción y cero audios de tonos registrados. No se confirmó una conexión con Unreal real.

## Comprobaciones desde la interfaz

1. Acceso con cuenta sintética al panel principal.
2. Edición de géneros, guardado de ambiental como ambient y confirmación visible.
3. Preparación de sesión y recomendación sintética. Estado preparada; bloqueo de preferencias, iluminación y duración mientras permanece abierta.
4. Vinculación de la sesión sintética y aparición de Solicitar inicio en Unreal.
5. Solicitud de inicio: permanece preparada y muestra Pendiente de Unreal: activa. No se simula la confirmación del dispositivo.
6. Reproductor bloqueado antes del inicio confirmado. No se verificó reproducción real dentro de este recorrido.
7. Tonos y cuestionario aparecen deshabilitados por configuración provisional.
8. Antes de preparar la sesión, el enlace Música apunta a #musica pero el elemento todavía no existe. Se comprobó con el DOM; aparece después de obtener recomendaciones.

## Hallazgos

| Prioridad | Hallazgo | Efecto en el recorrido |
|---|---|---|
| Alta | El panel principal requiere archivos de audio autorizados y hay cero registrados | La ruta real de recomendación de sesión no puede devolver canciones reproducibles; genera conflicto por ausencia de archivos disponibles |
| Alta | YouTube automático está en una página de prueba separada | No suministra el audio de la sesión VR; su reproducción y feedback siguen siendo independientes |
| Alta | Los enlaces YouTube solo están en la pantalla de acceso, no en el panel autenticado | Tras entrar, el usuario no tiene una navegación visible hacia ese flujo |
| Media | Cambiar de ruta con enlaces normales recarga React; usuario y token solo viven en memoria | Entrar en la vista YouTube requiere identificarse de nuevo; no hay continuidad de acceso entre las vistas |
| Media | Preparar sesión no comprueba cambios sin guardar en Preferencias | Si se edita y no se pulsa Guardar, se usa el perfil persistido anterior. Hallazgo de código; en la prueba positiva sí se guardó antes |
| Media | La modalidad Preferencias + heurística es seleccionable pese al protocolo de tonos deshabilitado | El frontend ofrece una opción cuyo requisito actualmente no puede completarse; el backend exige una evaluación aprobada |
| Media | Artistas solo dispone de paginación, sin búsqueda | Localizar artistas en un catálogo grande exige recorrer páginas de 30 elementos |
| Baja | Enlace Música sin destino antes de recomendar | La navegación inicial no lleva al panel de música |
| Pendiente de investigación | Cuestionario deshabilitado | El recorrido no puede finalizar recogiendo una evaluación de atención percibida con la configuración actual |

## Corrección propuesta

Definir un recorrido visible desde el panel: acceso → preferencias guardadas → selección musical web → preparación/vinculación de sala → inicio confirmado → actividad → cierre → encuesta aprobada. La navegación debe conservar el contexto de acceso al pasar entre pantallas y advertir los requisitos no disponibles.

La incorporación de YouTube a una actividad de investigación necesita una decisión explícita de integración y registro; añadir un enlace al panel no convierte una lista web en una sesión VR. El reproductor oficial debe permanecer visible. La revisión no propone reproducción oculta dentro de Unreal ni extraer el audio de YouTube.

No se realizaron correcciones de producto en esta revisión. La evidencia visual `flujo-principal-revision.png` corresponde únicamente al entorno sintético. El servidor temporal se detuvo al terminar; el servidor real en 8788 se mantuvo en ejecución.
