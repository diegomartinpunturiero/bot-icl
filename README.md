# Bot ICL — prototipo de consultas de cursos

Primer prototipo funcional sobre el repositorio original (que solo contenía `bot`, un archivo de un byte). Python 3.10 o superior, biblioteca estándar, sin claves ni servicios pagos.

## Ejecutar

Desde la carpeta del repositorio:

```bash
python3 app.py
```

Abrir http://127.0.0.1:8000. En Windows puede usarse `python` en lugar de `python3`.

También hay un chat de terminal:

```bash
python3 app.py chat
```

Escribir `/salir` para terminar. `Ctrl+C` detiene el servidor.

## Flujo disponible

- Menú inicial con seis áreas de cursos; selección por número o palabras clave sin distinguir acentos o mayúsculas.
- Detección de interés en texto libre. Si se mencionan varias áreas, pide elegir una.
- Consultas de precio y modalidad con memoria del curso seleccionado.
- `asesor`, `persona`, `humano`, `inscribirme` o `anotarme`: crea una solicitud de atención humana con código y curso de interés.
- Tras la derivación, pausa el flujo automático de esa sesión. `menú` vuelve al inicio. No duplica solicitudes al repetir `asesor` en la misma sesión pausada.

Ejemplo: `hola` → `me interesa inverter` → `cuánto cuesta` → `modalidad` → `asesor`.

## Cargar información real de ICL

Editar `config/courses.json`. El catálogo inicial es una propuesta de áreas, **no confirma oferta, cupos, fechas ni precios vigentes**. `price` y `modality` están en `null`: el bot indica que falta confirmar y ofrece un asesor, sin inventar información.

Cada curso contiene `id` único, `name`, `keywords`, `price` y `modality`. Estos dos últimos campos aceptan texto o `null`. Ejemplo ilustrativo, no dato comercial real:

```json
{"id":"aire","name":"Instalación y reparación de aire acondicionado","keywords":["split","aire acondicionado"],"price":"ARS [importe vigente]; [forma de pago]","modality":"[presencial/virtual], [sede], [duración], [horarios]"}
```

Reiniciar la aplicación después de editar. No cambiar IDs de cursos con conversaciones activas.

Para habilitar un botón de contacto, completar `advisor_whatsapp` con el número internacional real, solo dígitos, sin `+`, espacios ni guiones. Dejar vacío hasta confirmar el número. El enlace abre WhatsApp con un mensaje preparado: el usuario decide enviarlo.

## Atención humana

```bash
python3 app.py handoffs
```

Muestra la bandeja local de solicitudes pendientes con código, sesión, curso y fecha UTC. SQLite conserva la información al reiniciar. Este prototipo **no envía avisos, no asigna operadores y no promete respuesta automática**. El equipo debe revisar la bandeja; con el teléfono configurado, el interesado también puede iniciar contacto directo por WhatsApp. No hay consola de respuesta humana ni resolución de tickets todavía.

## Configuración mínima

Valores por defecto: puerto `8000`, catálogo `config/courses.json`, base `data/bot.sqlite3` (las rutas predeterminadas son relativas a la ubicación de `app.py`). Variables opcionales: `PORT`, `BOT_CATALOG`, `BOT_DATABASE`. Las rutas configuradas por entorno son relativas al directorio desde el cual se ejecuta el comando. `.env.example` es referencia: no se carga automáticamente.

Ejemplo Bash:

```bash
PORT=8080 BOT_DATABASE=data/demo.sqlite3 python3 app.py
```

## API para futuros canales

`GET /health`: estado. `POST /api/chat`: JSON con `message` y `session_id` opcional (UUID). La primera respuesta devuelve un UUID; conservarlo y enviarlo para mantener el contexto. La respuesta contiene `reply`, `session_id`, `handoff` y, al derivar, `ticket_id` y `contact_url` si se configuró un teléfono.

```bash
curl http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"me interesa lavarropas"}'
```

El navegador conserva la sesión solo en memoria: recargar inicia otra conversación. El servidor conserva las sesiones en SQLite. Se validan mensajes de 1–2000 caracteres y cuerpos HTTP de hasta 16 KiB. El catálogo se renderiza como texto, no HTML.

## Pruebas

```bash
python3 -m unittest discover -s tests -v
```

Incluyen menú, interés ambiguo, acentos, precio/modalidad configurados, memoria tras reinicio, sesiones independientes, derivación persistente sin duplicados y contrato HTTP.

## Estructura

`bot.py`: motor y persistencia; `app.py`: servidor y consola; `static/index.html`: chat demo; `config/courses.json`: datos editables; `tests/`: pruebas. `bot` conserva el archivo original sin utilizarlo. `data/` y secretos están excluidos de Git.

## Alcance y próximo paso

La demo escucha únicamente en `127.0.0.1`. No está desplegada ni conectada a WhatsApp Business, Instagram o un CRM. La detección usa reglas, no un modelo de IA, y no cubre todas las expresiones posibles.

Para conectar WhatsApp hace falta un adaptador oficial que valide webhooks, identifique cada conversación, envíe respuestas y gestione reintentos e idempotencia de mensajes. Antes de exponer el servicio públicamente, incorporar HTTPS, autenticación, límites de tráfico, retención/eliminación de datos, monitoreo y un servidor de producción. El UUID de sesión no sustituye autenticación. La bandeja solo se consulta por terminal, sin endpoint público. No se guardan mensajes completos ni se solicitan datos personales; proteger la base local y definir su retención con ICL.
