# StudyRoom integrado

Copia independiente del panel React y del proyecto Unreal. El original `StudyRoom_VR_Pro` no se modifica. La base y los tres servicios Python existentes tampoco se duplican ni se renombran.

## Estructura

```text
studyroom-integrado/
  web/                       React: modo local y modo integrado
    src/api/                 Cliente HTTP de usuarios, catálogo, sesiones y puente
    src/components/          Acceso, preferencias, tonos, vinculación, audio y encuesta
  bridge/                    Node: ajustes de sala y vinculación privada con Python
  unreal/                    Copia de la sala; adaptaciones en StudyRoomBuilder.h/.cpp
  scripts/                   Preparación de claves y vista aislada de prueba
  tests/                     Pruebas HTTP con backend sintético en memoria
  docs/                      Contrato de conexión y resultados de pruebas
```

## Iniciar

Requiere Node.js 22 o posterior y el backend Python levantado con su Docker Compose. No detener ni cambiar la base para ejecutar este proyecto.

Desde esta carpeta:

```powershell
npm install
npm run setup
npm run build
npm run bridge
```

Abrir **http://127.0.0.1:8788**. El puente sirve también el frontend compilado. Si `setup` informa que ya existe configuración, conservarla: no es un fallo de la aplicación ni se debe regenerar sin sincronizar Unreal.

Para desarrollar React, mantener el puente activo y, en otra terminal:

```powershell
npm run dev
```

La web de desarrollo estará en **http://127.0.0.1:5174**. Estos puertos son distintos de los del proyecto original. Vite exige el puerto indicado; no salta a otro silenciosamente.

`npm run setup` crea `.env` en la raíz y `unreal/room-key.local.txt`, ambos ignorados por Git. La clave de sala no se muestra ni se entrega a React. No compartir esos archivos ni publicar la clave. No hay contraseñas de MongoDB en este proyecto.

La configuración generada apunta a los servicios existentes: usuarios 8001, catálogo 8002 y sesiones 8003. Las llamadas del navegador pasan por rutas `/backend/...` del puente; no dependen de ampliar CORS en Python. El proxy solo permite rutas públicas explícitas, no `/internal`, destinos arbitrarios ni canjear tokens de sala desde React.

## Modos

### Prueba independiente de YouTube

**Búsqueda automática:** `http://127.0.0.1:8788/?prueba=youtube-auto`. Tras iniciar sesión, recomienda desde el perfil y busca videos por título/artista/duración sin pegar enlaces. Requiere `YOUTUBE_API_KEY` configurada únicamente en el backend y reiniciar el puente actualizado. Las coincidencias se consideran probables, no verificaciones acústicas; es un modo solo web, separado de las sesiones VR.

Abrir **http://127.0.0.1:8788/?prueba=youtube** para pegar un enlace y probar el reproductor oficial visible, sin descargar audio ni iniciar sesión. El puente debe estar activo. Esta prueba no modifica el catálogo, no genera recomendaciones ni registra una sesión de investigación. Consultar [alcance, privacidad y restricciones](docs/YOUTUBE_PRUEBA.md).

- `MODE=local`: conserva las rutas `/api/state` y `/api/vr/state`, los controles y el WAV demostrativo del panel original. No registra actividad en Python ni genera recomendaciones reales. Se indica visiblemente que es una demostración.
- `MODE=integrado`: login y perfil en Python; sesiones individuales, recomendaciones y archivos autorizados; vinculación con Unreal. No vuelve al modo local si falla una dependencia.

Cambiar el modo en `.env` y reiniciar el puente. No cambiar de modo en medio de un estudio. Sin `.env` se inicia explícitamente como local; con `.env` integrado y clave inválida, el proceso se detiene.

## Abrir Unreal

Abrir **la copia** `unreal/StudyRoomUE5.uproject` con Unreal 5.7 y regenerar/compilar sus fuentes. Se conservan las mallas procedurales, luces, materiales y scripts originales. Todavía se requiere preparar el nivel y los materiales desde el editor según el proyecto original; no se incluyen mapas `.umap` inventados.

El actor `StudyRoomBuilder` usa por defecto `http://127.0.0.1:8788`. Si un nivel ya guardado conserva la URL antigua en sus propiedades, cambiarla manualmente a ese valor. Al ejecutar Play carga `room-key.local.txt` desde el directorio del proyecto. No necesita el token general del estudiante ni credenciales de MongoDB.

El actor sondea cada 2 segundos, conserva las funciones de iluminación y envía confirmaciones HTTP de los comandos de actividad. `bAutoConfirmCommandsWhilePlaying=true` confirma mientras el actor está en Play: confirma ejecución de la sala, no desempeño del estudiante ni conexión del visor. Para una tarea de aprendizaje específica, desactivarlo y llamar **ConfirmActivityState** desde los eventos reales del Blueprint/UMG de la tarea:

- `activa`: inicio o reanudación del comando recibido.
- `pausada`: pausa del comando recibido.
- `finalizada`: cierre del comando recibido.
- `interrumpida`: también admite una interrupción espontánea desde la sala activa.

No se añadió locomoción, interacción con mandos ni interfaz 3D. No se ha compilado o ejecutado esta copia en un visor en esta entrega. El visor continúa dependiendo del runtime OpenXR/PC VR y de la configuración del equipo.

## Flujo integrado

1. Acceder con una cuenta existente o registrarse. El registro exige mayoría de edad y declaración de haber recibido y aceptado el consentimiento aprobado `consentimiento-v1`. El texto aprobado debe proporcionarlo el investigador; el aviso técnico del panel no lo sustituye.
2. Guardar artistas del catálogo, géneros y tempo. Si el catálogo no está importado, aparecerá vacío; este proyecto no lo descarga ni lo modifica.
3. Los tonos solo pueden iniciarse si el protocolo está aprobado y sus archivos están registrados. El panel muestra el estado pendiente del backend sin forzarlo.
4. Elegir duración prevista (15 o 25 minutos), iluminación y modalidad. Preparar la sesión y generar su recomendación. Se conservan los IDs de solicitud para reintentos.
5. Vincular la sesión al puente. El código temporal se canjea en Node; solo el token limitado a esa sesión queda en memoria del puente.
6. Solicitar inicio. Unreal recibe el comando y confirma; solo entonces Python cambia el estado. Pausa, reanudación y cierre usan el mismo circuito. La web puede interrumpir como salida de seguridad.
7. Cargar y reproducir la canción autorizada en el navegador. El audio no se reproduce en Unreal. Los eventos enviados distinguen inicio, pausa, fin, omisión y volumen digital. Una omisión no es automáticamente rechazo.
8. Guardar preferencia y molestia por canción. Los ajustes del perfil corresponden a futuras sesiones, no cambian la selección ya guardada.
9. Tras cerrar una actividad iniciada, responder la encuesta solo cuando esté aprobada. Se recoge percepción, no una medida objetiva de atención. Liberar la sala antes de preparar otra sesión.

## Límites importantes

- Un puente admite **una sala y una sesión vinculada a la vez**. No es un servidor multiusuario de salas ni una nueva base de datos.
- Python es la autoridad del estado. Node solo conserva ajustes visuales, el vínculo y los comandos pendientes.
- La duración de actividad es una previsión, no un cierre automático. El token de sala dura 30 minutos; las pausas cuentan dentro de ese plazo. Al vencer, interrumpir desde la web y crear una nueva sesión. No se modifica el backend para ampliar permisos.
- Al preparar la sesión se guardan multiplicador de brillo y preset como configuración de la actividad. Tras vincularlos quedan fijados para mantener correspondencia con el registro. El control de volumen del reproductor sigue disponible y es digital 0–1, no dB en el oído.
- El token del estudiante queda solo en memoria del navegador; recargar exige iniciar sesión de nuevo. `sessionStorage` conserva únicamente IDs de solicitudes, ID de sesión y configuración para recuperar/reintentar la operación, no contraseñas ni tokens. En equipo compartido cerrar la sesión y la pestaña.
- El token de sala no se persiste. Si Node se reinicia tras canjear el código, puede perderse el vínculo y Python no permite reutilizar ese código. Recuperar la sesión desde la web, interrumpirla y crear otra. No se finge recuperación del token perdido.
- Los eventos de audio se reintentan con el mismo ID en una cola acotada en memoria. No es modo offline: cerrar/recargar la pestaña puede perder eventos aún no enviados y se avisa al abandonar desde los controles de la aplicación. Una desconexión pausa la reproducción al detectarse; no se interpreta como fin confirmado del estudio.
- `EndPlay` intenta notificar una interrupción; un cierre abrupto o fallo de red puede impedir entregarla. El investigador debe verificar y cerrar sesiones pendientes desde la web.
- El indicador de Unreal acredita consultas con clave de sala, **no detección del visor ni atención del estudiante**.
- La ilustración de habitación sigue siendo CSS, no vídeo en vivo. Los valores de iluminación no son lux medidos. Las fuentes tipográficas externas pueden no cargar sin Internet; hay fuentes locales de respaldo.
- El puente limita acceso a loopback, orígenes explícitos y cuerpos de 64 KiB. No exponerlo a Internet o LAN sin TLS, autenticación operativa de sala y revisión de seguridad. La clave compartida del prototipo no sustituye un sistema de identidad de dispositivos.

## Pruebas

```powershell
npm test
npm run build
```

Para una vista de prueba aislada, sin Python ni MongoDB:

```powershell
node scripts/preview-test.mjs
```

Abrir `http://127.0.0.1:8790`, con cuenta **sintética** `demo@example.test` y contraseña `demo-password-123`. Este script simula el intercambio HTTP de Unreal, no ejecuta el motor ni un visor. Es exclusivamente una fixture, no un modo del sistema de investigación. Detenerlo con Ctrl+C al terminar.

Consultar [contrato de conexión](docs/CONEXION.md) y [verificación y pendientes](docs/PRUEBAS.md).
