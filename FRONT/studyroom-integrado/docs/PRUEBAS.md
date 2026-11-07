# Verificación de la entrega

## Comprobaciones automatizadas

- Compilación React/Vite mediante `npm run build`.
- Pruebas Node mediante `npm test`: modo local, autenticación web y sala, orígenes permitidos, comando sin cambio prematuro de estado, confirmación deduplicada, aislamiento por ID de sesión, bloqueo de comandos concurrentes, rechazo de rutas internas y fallo de Python sin retorno automático a local.
- Las fixtures usan memoria y archivos temporales propios, no MongoDB. Los tonos y la encuesta de prueba mantienen su aprobación en `false`.

Resultado ejecutado: **7 pruebas Node aprobadas y compilación de producción correcta**.

También se ejecutó `scripts/verify-python.mjs` contra las fuentes reales de las tres APIs Python, levantadas en puertos temporales con una base simulada en memoria. Se verificaron registro y mayoría de edad, perfil, sesión, recomendación idempotente, canje privado, inicio pendiente hasta confirmación, audio HTTP Range (206), eventos, feedback sin doble ajuste, pausa/reanudación/finalización y bloqueos de tonos y encuesta. No se abrió ni modificó MongoDB del estudio y no se editó el backend.

Para repetir, proporcionar las rutas al Python que tiene instaladas las dependencias de prueba del backend y a su carpeta de fuentes:

```powershell
node scripts/verify-python.mjs RUTA_PYTHON_DEL_BACKEND RUTA_FUENTES_BACKEND
```

Se revisó la interfaz en navegador con la fixture aislada: acceso, preferencias, preparación, vinculación, estado pendiente y confirmado, carga y reproducción de WAV sintético, omisión, feedback, pausa, reanudación y finalización. Esta prueba no usa cuentas reales. La captura `verificacion-interfaz.png` documenta el entorno sintético, no un visor conectado.

## No confundir con validación del sistema completo

El simulador HTTP de Unreal únicamente verifica el contrato de mensajes. No demuestra compilación C++, ejecución del nivel ni compatibilidad con un visor. Tampoco verifica eficacia de recomendaciones, atención objetiva ni seguridad acústica.

Antes de evaluar con estudiantes deben completarse:

1. Compilar la copia de Unreal 5.7 y ejecutar el nivel preparado, con materiales y OpenXR configurados.
2. Probar inicio, pausa, reanudación, cierre e interrupción con la sala real y revisar los eventos guardados.
3. Importar catálogo y registrar audios con permisos, correspondencia e integridad verificados, si aún faltan.
4. Aprobar consentimiento, protocolo de tonos y cuestionario antes de habilitarlos para participantes.
5. Probar salida de audio del navegador durante PC VR, comodidad, volumen y pérdida de conexión.
6. Comprobar vencimiento de tokens, recarga del navegador y recuperación tras reiniciar el puente.
