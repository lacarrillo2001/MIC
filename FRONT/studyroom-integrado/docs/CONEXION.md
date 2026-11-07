# Contrato de conexión

```text
React ── /backend/usuarios ──→ API Python de usuarios
      ── /backend/catalogo ──→ API Python de recomendaciones
      ── /backend/sesiones ──→ API Python de sesiones y audio
      ── /api/state, /api/session/* ──→ Puente Node
                                          ↕ clave privada de sala
                                     Unreal en Play
```

Las rutas `/backend` son un proxy local con lista permitida, no otro backend de negocio. Mantienen el Bearer del estudiante y la validación de Python. No hay acceso directo a MongoDB desde Node, React o Unreal.

## Rutas del puente

| Ruta | Emisor | Función |
| --- | --- | --- |
| `GET /api/config` | React | Modo explícito y restricción de una sala |
| `GET /api/health` | Operador | Salud del proceso, no de todas las dependencias |
| `GET /api/state` | React | Ajustes y estado confirmado; requiere Bearer en modo integrado |
| `PATCH /api/state` | React | Ajustes locales; en integrado no acepta `sessionActive` ni preferencias musicales |
| `POST /api/session/link` | React | `{sesion_id,codigo}`, verifica propietario y canjea código en Python |
| `POST /api/session/command` | React | `{id,estado}`, guarda intención pendiente; no inicia la sesión |
| `GET /api/vr/state` | Unreal | Ajustes, ID de sesión y comando pendiente; exige `X-Room-Key` en integrado |
| `POST /api/vr/events` | Unreal | `{id,estado,sesion_id}`, confirma actividad y transmite transición a Python |
| `POST /api/session/release` | React | Libera el vínculo solo después del cierre oficial |

El token de sala no se devuelve en ninguna de estas respuestas. La clave de sala tampoco. Los logs no imprimen claves, códigos, contraseñas ni tokens.

## Coherencia y errores

Un comando tiene ID estable. Mientras esté pendiente no se acepta otro distinto. La confirmación debe coincidir en ID, sesión y estado; se guarda una ventana de confirmaciones recientes para no repetir la operación. Python también valida transiciones e idempotencia del estado. El historial de Node es acotado y se pierde al reiniciar: no constituye una auditoría persistente ni una garantía de entrega exactamente una vez.

Una interrupción espontánea de Unreal se admite para la sesión activa o pausada. El alumno puede interrumpir directamente desde React mediante el endpoint público autorizado de Python. Las consultas del visor no se guardan como eventos de reproducción ni actividad de aprendizaje.

Si Python rechaza una transición o no responde, no se declara confirmada ni se cambia al modo local. El próximo sondeo muestra el error. La iluminación se aplica al estado confirmado; no se afirma que sea una intervención eficaz sobre atención.

## Compatibilidad

Modo local conserva el contrato original. En modo integrado el cliente Unreal debe ser la copia adaptada: un Unreal antiguo que no envíe `X-Room-Key` recibirá 403, sin debilitar la autenticación. El modo no se cambia durante una sesión.

Se usan HTTP y puertos de loopback; la sala es PC VR en el mismo equipo. No se implementó transporte LAN, WebXR ni aplicación Quest independiente.
