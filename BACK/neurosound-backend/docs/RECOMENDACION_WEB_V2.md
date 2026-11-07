# Recomendación web: candidatos, diversidad y feedback

La mejora se aplica al modo YouTube web. Conserva los tres servicios y las colecciones existentes; no modifica canciones, artistas ni el protocolo de sesiones VR.

## Candidatos

Se combinan muestras aleatorias del catálogo: hasta 250 canciones de artistas preferidos, 250 de artistas asociados a géneros preferidos y 250 próximas a los atributos del perfil. Se completa hasta un máximo de 1.000 candidatas con una muestra general, eliminando identificadores duplicados y canciones rechazadas.

La proximidad usa tempo ±20 BPM y energía/valencia ±0,15, cuando existen esos objetivos. Son reglas técnicas experimentales, no umbrales de atención validados. La muestra de artistas por género se limita a 1.000 artistas. El ranking conserva los pesos de `reglas-v1.json`; no recorre ni puntúa todo el catálogo.

## Diversidad

Se mezclan candidatas dentro de bandas de hasta cinco puntos desde la mejor puntuación de cada grupo. La semilla es el identificador de solicitud y la lista final queda guardada: repetir la misma solicitud devuelve la misma lista.

Primero se evitan las canciones reproducidas en las dos listas web utilizadas más recientemente y se admiten como máximo dos canciones por artista (incluidos colaboradores). Si faltan alternativas, se permite reutilizar canciones recientes; finalmente se relaja el límite por artista. Los rechazos explícitos nunca se relajan. Una nueva solicitud puede repetir canciones si las alternativas son insuficientes.

## Reproducción y respuestas

`POST /youtube/recomendaciones/{id}/reproduccion` registra el primer evento PLAYING declarado por el cliente para una pista de esa lista. El registro es idempotente. No acredita escucha completa ni mide atención.

`POST /youtube/recomendaciones/{id}/feedback` admite `me_gusta`, `no_me_gusta`, `molestia` o `neutral`, junto con `track_id` y la revisión esperada. Exige propiedad de la lista y reproducción previamente registrada. Existe una respuesta web vigente por usuario y canción, guardada en `feedback` con una clave estable; una revisión evita sobrescribir cambios de otra pestaña.

- Me gusta: ajusta energía y valencia en la afinidad efectiva web con tasa 0,1. Sin afinidad previa se usa el valor de la primera canción valorada positivamente.
- No me gusta / molestia: excluyen la pista de próximas listas. La molestia no se atribuye a frecuencias ni se propaga al artista.
- Neutral: retira la influencia de esa respuesta.

La afinidad efectiva se reconstruye al preparar cada lista, partiendo de la afinidad del perfil y aplicando una sola vez las respuestas positivas vigentes, en orden de creación. Así, editar o retirar una respuesta no acumula ajustes históricos. Se guarda en `perfil_utilizado` de la nueva recomendación; no sobrescribe `perfiles.afinidad_aprendida` ni cambia una sesión VR fijada. Las valoraciones web tampoco se procesan mediante el endpoint de ajustes VR.

`GET /youtube/feedback?pagina=1` permite revisar y corregir valoraciones anteriores, incluso de canciones excluidas. Devuelve 20 por página. Las listas existentes permanecen intactas al cambiar una respuesta; el efecto comienza en la siguiente lista.

La API no interpreta una omisión, una búsqueda fallida ni una pausa como rechazo musical. El cliente deshabilita las valoraciones hasta confirmar el registro de reproducción.

## Verificación

Las pruebas cubren selección fuera del inicio del catálogo, deduplicación, diversidad y su relajación, historial reciente, propiedad de listas, reproducción idempotente, revisión de respuestas, retirada de afinidad, exclusiones, aislamiento entre usuarios y conservación del perfil VR.

Verificación local del 2 de noviembre de 2026: 34 pruebas Python y 11 del puente aprobadas; build Vite correcto. En una cuenta sintética se verificaron el bloqueo antes de reproducir, las cuatro respuestas, la corrección desde el historial y la sincronización de sus controles con los del reproductor. Esa prueba no creó cuentas ni valoraciones en MongoDB real y utilizó un resultado de búsqueda simulado con un video técnico público. Evidencia: `studyroom-integrado/docs/frontend-feedback-v2.png`.

Una consulta de solo lectura al catálogo real obtuvo 1.000 candidatas en 0,908 segundos con género ambient, tempo moderado y afinidades de ejemplo. Es una observación local, no un benchmark general. El servicio Docker y el puente en 8788 se actualizaron; su endpoint de salud devolvió 200 y el historial sin autenticación devolvió 401.
