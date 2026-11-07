# Coincidencias de géneros en español y etiquetas del catálogo

Corrección aplicada el 3 de noviembre de 2026. Se verificaron las 3.841 etiquetas distintas de `artists.genres` y 39 equivalencias explícitas: todos sus destinos existen en el catálogo de este entorno.

| Entrada admitida | Etiqueta conservada |
|---|---|
| ambiental / música ambiental | ambient |
| clásica / música clásica | classical |
| electrónica / música electrónica | electronica |
| pop latino | latin pop |
| pop en español | spanish pop |
| meditación | meditation |
| ruido blanco | white noise |
| bandas sonoras | soundtrack |
| música de fondo | background music |
| música para dormir | sleep |
| reguetón | reggaeton |
| hip-hop / hiphop | hip hop |
| lofi | lo-fi |
| jazz latino | latin jazz |
| piano clásico | classical piano |
| piano de fondo | background piano |

Las etiquetas exactas existentes tienen prioridad. Para el resto se normalizan mayúsculas, tildes, espacios repetidos y variantes con guion. Si la normalización tiene más de un destino, no se elige uno automáticamente. La configuración completa está en `config/generos-v1.json`; no se traducen indiscriminadamente las miles de etiquetas.

`instrumental`, `piano` y `ruido rosa` no existen como etiquetas exactas en este catálogo. No se convierten automáticamente en ambient, classical u otro género. La búsqueda de piano muestra alternativas reales como background piano y classical piano. Instrumentalidad es además un atributo del audio, distinto del género; esta corrección no añade un filtro instrumental al ranking.

## Flujo

- `GET /catalogo/generos?q=...`: sugerencias autenticadas, tomadas de MongoDB y presentadas con traducción cuando está definida. Máximo 30 resultados; la interfaz muestra los primeros ocho.
- El servicio de usuarios valida los géneros al guardar mediante `POST /internal/generos/resolver` del servicio de recomendación. La ruta interna admite solamente a usuarios como servicio llamante; no se publica en el puente.
- Un género desconocido devuelve 422 y evita guardar parcialmente las preferencias o aumentar la versión del perfil.
- Los perfiles anteriores, incluido un valor guardado como ambiental, se interpretan al generar una recomendación nueva, tanto web como VR. No requieren migración masiva ni modificación de las canciones/artistas originales. Las listas ya guardadas conservan su contenido.
- La recomendación guarda `normalizacion_generos`: etiquetas reconocidas, entradas no reconocidas y equivalencias aplicadas. En la vista YouTube se muestran los géneros utilizados y cualquier entrada anterior que no pudo reconocerse.
- Al guardar preferencias nuevas se conservan las etiquetas reales del catálogo, sin duplicados. La interfaz confirma cuáles quedaron guardadas y permite seleccionar sugerencias para el último término de una lista separada por comas.

No se modificaron los pesos del ranking ni los objetivos de tempo de esta corrección. Los nombres de artistas y títulos no se traducen.

## Verificación

48 pruebas Python y 11 del puente aprobadas, build Vite correcto. Las pruebas cubren traducciones, tildes, mayúsculas, etiquetas exactas, desconocidas, deduplicación, permisos internos, guardado atómico y normalización de perfiles anteriores sin cambiar su versión.

Contra MongoDB real se verificaron las 39 equivalencias y ocho conversiones de ejemplo; el resultado quedó en `outputs/validacion_generos_2026_11_03.json`. En el navegador aislado se comprobaron conversión al guardar, rechazo de una entrada inventada y selección de Clásica conservando Ambiental. Esas interacciones utilizaron una cuenta sintética y no modificaron el perfil real.
