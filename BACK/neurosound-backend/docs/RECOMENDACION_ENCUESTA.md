# Recomendación a partir de la encuesta

La lista web principal y `?prueba=youtube-auto` utilizan `encuesta-web-v4`.
Las actividades se ejecutan en la aplicación de sala virtual; aquí solo se registra su tipo.
Esta actualización no cambia el protocolo ni el algoritmo legado de las sesiones VR.

## Datos y API

`PUT /perfiles/me`: versión esperada, hasta tres IDs de artistas, hasta tres géneros,
`preferencia_voz` (`instrumental`, `con_voz` o null), `tempo_preferido`
(`lento`, `moderado`, `rapido` o null). Null/lista vacía significa sin preferencia.
Los perfiles anteriores se leen sin migrarlos; para guardar más de tres selecciones
antiguas deben reducirse mediante los botones Quitar del formulario.

`POST /youtube/recomendaciones`: conserva solicitud_id, limite y modo; añade
`actividad` (`lectura_comprensiva`, `atencion_flechas` o null para clientes anteriores),
`energia_sesion` (`suave`, `energica`, `mantener`). El frontend siempre envía actividad.
Cambiar estos datos requiere una nueva solicitud_id. La actividad no cambia por sí sola
el tempo ni crea una prescripción musical.

## Puntaje de 0 a 100

Configuración: `config/recomendacion-web-v3.json`. Pesos iniciales: gustos 40 %, voz
25 %, tempo 20 %, energía 15 %. Solo se activan componentes con preferencias conocidas;
sus pesos se normalizan para sumar uno. Sin componentes activos el puntaje es cero y
se ofrece una selección diversa de respaldo, sin afirmar personalización.

- Gustos: uno si coincide un artista O un género asociado a sus artistas, cero si no.
  No se suman dos bonificaciones por ambas coincidencias.
- Voz: instrumentalness para instrumental; 1 - instrumentalness para con voz.
  Es un indicador probabilístico del catálogo, no una certificación de presencia de voz.
- Tempo: coincidencia uno dentro de 40–90, 90–120 o 120–220 BPM, según preferencia.
  Fuera del rango decrece linealmente hasta cero a 60 BPM de distancia. Los límites
  compartidos son intencionales: 90 y 120 pueden encajar en ambos rangos adyacentes.
- Energía: 1 - distancia absoluta a .25 (suave) o .75 (enérgica). Mantener utiliza
  energía aprendida de feedback explícito si existe; si no, omite este componente.
  Energy no representa volumen, activación medida ni frecuencia acústica.

Un atributo ausente o inválido aporta cero dentro de su componente activo: no se
redistribuye su peso por canción, evitando premiar datos incompletos. Se guarda
`desglose_puntaje`, atributos, perfil, contexto y copia de reglas en cada lista.
Los pesos y rangos son decisiones experimentales configurables, no resultados validados
de artículos. El puntaje mide compatibilidad con respuestas, no concentración.

## Selección e historial

Se conservan muestras acotadas por artistas/géneros, atributos y catálogo general.
La muestra por atributos incorpora instrumentalidad. Se excluyen rechazos/molestias
vigentes y duraciones desconocidas o fuera de 15 segundos–20 minutos, coherente con
el reproductor de descarga. No se garantiza encontrar el óptimo entre todo el catálogo.
Se conserva diversidad por bandas de cinco puntos, máximo inicial de dos canciones
por artista y evitación de canciones reproducidas en las dos últimas listas; estos
límites se relajan si faltan opciones. La lista puede no quedar estrictamente ordenada.

Los likes actuales siguen aportando energía a la afinidad web reconstruida; una elección
explícita de energía de sesión prevalece temporalmente. No se cambia el perfil persistente
ni se incorporan resultados de tareas o encuestas como ajustes automáticos. Todavía no hay
aprendizaje específico por actividad. Se conserva valence en el historial, pero esta versión
del puntaje no la utiliza porque no hay una pregunta sobre valencia.

La encuesta posterior y el intercambio de resultados con Unreal no se implementan en esta
entrega: esta entrega conecta las respuestas iniciales y de sesión con la recomendación.

## Preselección y corrección personal de voz (v4)

Todas las muestras de candidatos aplican el filtro antes de puntuar. Para instrumental
se exige instrumentalness >= .8 y <= 1; para con voz, entre 0 y .2. Los límites se
configuran en voice_prefilter del JSON de reglas. Un reporte personal vigente de voz
excluye el track de listas instrumentales y puede incluirlo como candidato con voz.
Sin preferencia de voz no se filtra por este atributo. No se relaja el filtro si faltan
candidatas: se devuelve una lista menor con aviso o 409 si ninguna es elegible.

Los límites son heurísticos, no una detección del audio ni una garantía de letra. La
interfaz distingue probablemente instrumental, baja instrumentalidad y voz reportada
por el estudiante. No se realizan descargas masivas ni se instala un modelo de voz.
La descarga existente sigue siendo bajo demanda al seleccionar una canción.

GET/POST `/youtube/recomendaciones/{id}/voz` permiten consultar y corregir el reporte.
POST recibe track_id, tiene_voz y revision. Se exige propiedad de la lista y reproducción
registrada de la canción; admite reenvío idempotente y rechaza versiones desactualizadas.
`tiene_voz: false` retira el reporte: no certifica ausencia de voz.

Los reportes usan la colección feedback existente, tipo voz_web y una clave única por
usuario/track. Son independientes de me_gusta/no_me_gusta/molestia, no ajustan afinidades
y no son una clasificación global del catálogo. No generan nuevas colecciones.
No se propagan automáticamente a IDs alternativos de la misma grabación ni verifican
la correspondencia acústica del audio descargado. La lista original se conserva intacta;
la corrección influye en listas futuras. El botón permite retirar la corrección al
volver a seleccionar una canción escuchada. La nueva sección aparece tanto en el panel
como en la prueba directa de YouTube. GET `/youtube/voz?pagina=1` alimenta el historial
personal de correcciones; permite retirar un reporte aunque la canción ya no aparezca
en las nuevas listas instrumentales.
