# Verificación del frontend — 2 de noviembre de 2026

Prueba aislada en el puerto 8792, con cuenta y respuestas de backend sintéticas. No se modificó MongoDB ni el servidor de producción del puerto 8788.

## Resultados observados en la interfaz

- Acceso con la cuenta de prueba y guardado de preferencias musicales.
- Con configuración ausente, se muestra el aviso de falta de `YOUTUBE_API_KEY`; no se simula una búsqueda exitosa.
- Con el resolver simulado habilitado, la primera pista sin coincidencia se omite y se carga la segunda, identificada expresamente como video técnico de prueba.
- El reproductor oficial de YouTube cargó el video público `M7lc1UVf-VE`, reprodujo contenido y mostró el estado «Reproduciendo desde YouTube».
- «Siguiente canción» consultó la tercera pista, sin coincidencia, y mostró que no quedaban canciones disponibles.
- Secuencia registrada por el fixture: `fixture-no-match`, `fixture-video`, `fixture-final`.
- «Preparar una nueva lista» retiró el resultado y volvió a habilitar la preparación de recomendaciones.
- `npm test`: 10 pruebas aprobadas. La ejecución inicial dentro del sandbox no pudo conectar a puertos locales (EACCES); al ejecutar con permiso de red local todas pasaron.

## Alcance pendiente

La selección del video fue una respuesta sintética; no demuestra una búsqueda real en YouTube Data API ni correspondencia con una canción de songsV2. Para validar el recorrido completo faltan configurar la clave del backend e iniciar sesión en la aplicación real. Tampoco se esperó el final natural del video: el avance se verificó con «Siguiente canción».

Evidencia visual: `frontend-youtube-automatico-prueba.png` (reproducción real, selección simulada) y `frontend-youtube-sin-clave.png` (aviso de configuración ausente).

El servidor temporal de prueba se detuvo al terminar.
