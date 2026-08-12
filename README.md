# Gasti

Bot de Telegram para gestion de gastos e ingresos personales. El usuario envia texto, fotos, PDFs o notas de voz y la IA extrae monto / descripcion / categoria, pidiendo confirmacion antes de guardar en PostgreSQL.

## Funcionalidades

- Recepcion multi-formato: texto, imagen, PDF, audio (transcripcion) y nota de voz
- Extraccion con IA (Gemini) con respuesta JSON estructurada y personalidad propia ("Gasti")
- Confirmacion del usuario antes de persistir (botones inline)
- Guardrails: la IA marca si el contenido es o no un registro valido y las validaciones deterministas lo refuerzan (estado `RECHAZADO`)
- Estados de extraccion: `PENDIENTE` / `COMPLETADO` / `FALLIDO` / `CANCELADO` / `RECHAZADO`
- Comando `/pendientes` para recuperar registros sin confirmar (post-reinicio)
- Limite mensual de gasto opcional por usuario (`/limite`), con warning antes de guardar y alerta al superarlo
- 12 categorias: Comida, Transporte, Servicios, Salidas y Ocio, Salud, Pagos y Suscripciones, Educacion, Ropa y Accesorios, Hogar y Mantenimiento, Viajes y Vacaciones, Pago de deudas, Otros

## Arquitectura

El proyecto usa una arquitectura de 3 capas:

```
receivers --> core <--> ia
```

- `receivers/` — centraliza los canales de informacion (solo Telegram por ahora).
- `core/Processer.py` — define el tipo de mensaje recibido (texto, audio, imagen o doc), llama a los metodos base de extraccion segun tipo, informa al usuario los datos extraidos y espera confirmacion, e inserta el registro confirmado en la BD. Encapsula `BaseAIExtractor` y `DAO`.
- `ia/` — interfaz abstracta (`base.py`) con implementaciones concretas (solo `GeminiExtractor` por ahora).
- `core/DAO.py` — capa de acceso a datos; delega todo a stored procedures y funciones de PostgreSQL (`core/SPs.sql`).

## Stack

- Python 3.12, async con `asyncio.to_thread()` para llamadas bloqueantes a DB
- PostgreSQL via `psycopg2-binary` (container Docker `gasti_db`, puerto 5433)
- Google Gemini API (modelo `gemini-3.1-flash-lite`)

## Comandos del bot

- `/start`, `/help`
- `/pendientes` — lista y confirma registros pendientes
- `/limite` — configura el limite mensual de gasto (conversacional; sin monto lo limpia)

## IA y extraccion

La extraccion devuelve un `ExtractedData` con `concepto`, `monto`, `tipo` (GASTO/INGRESO), `categoria`, `respuesta` (mensaje conversacional de Gasti al usuario) y flags de guardrail (`es_registro_valido`, `razon_rechazo`). Las instrucciones del sistema (anti prompt-injection, reglas de cordura y personalidad) van por `system_instruction`, separadas del input del usuario.

## Estado

- Funciona: flujo completo de texto y foto verificado; persistencia y confirmacion ok.
- Pendiente: insertar las 6 categorias nuevas en la DB, seed en `core/SPs.sql` y probar end-to-end las nuevas respuestas de la IA (personalidad). Ver `CONTEXT.md` para el detalle.
