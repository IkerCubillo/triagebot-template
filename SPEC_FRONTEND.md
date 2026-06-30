# SPEC_FRONTEND.md — TriageBot Frontend mínimo con HTMX

> Documento de trabajo para usar en Cursor con Claude Code en modo **spec coding**.  
> Antes de implementar, usar `/plan` y revisar el plan. No empezar a modificar archivos sin un plan claro.

---

## 0. Contexto del proyecto

TriageBot es una aplicación interna para crear tickets, clasificarlos automáticamente con un LLM y gestionarlos desde un tablero web.

El backend ya expone una API de tickets y existen tests obligatorios. El frontend debe añadir una página HTML funcional sin romper la API ni los tests existentes.

El objetivo de este SPEC es construir un **frontend mínimo, usable y presentable**, usando:

- FastAPI
- Jinja2 templates
- HTMX
- Tailwind CSS por CDN
- Sin React
- Sin Vite
- Sin Webpack
- Sin build tools
- Sin HTML gigante como string dentro de `main.py`

---

## 1. Regla principal para Claude Code

Antes de tocar código, Claude Code debe hacer un plan.

### Prompt recomendado en Cursor

```text
Lee SPEC_FRONTEND.md y prepara un plan de implementación antes de escribir código.

Restricciones:
- No modifiques tests/test_acceptance.py.
- No rompas los endpoints JSON existentes.
- No cambies el stack.
- Usa Jinja2 templates.
- Usa HTMX + Tailwind por CDN.
- No metas HTML grande como strings en app/main.py.
- Mantén pytest y ruff verdes.

Primero dame el plan. No implementes todavía.
```

---

## 2. Objetivo del frontend

Crear una única página en `GET /` que permita:

1. Crear tickets desde un formulario.
2. Ver los tickets en un tablero visual.
3. Filtrar tickets por `category`, `priority` y `status`.
4. Actualizar la lista sin recargar toda la página.
5. Presentar una UI clara, intuitiva y visualmente accesible.

La página debe servir a una persona usuaria interna, llamada aquí “Marta”, que quiere revisar tickets rápidamente durante una demo o una jornada de trabajo.

Marta necesita entender de un vistazo:

- qué tickets son más urgentes;
- cuáles siguen abiertos;
- qué tipo de problema tiene cada ticket;
- qué tickets debe mirar primero.

---

## 3. Alcance funcional obligatorio

La página `GET /` debe contener tres bloques principales.

### 3.1 Formulario para crear tickets

Debe incluir:

- Campo `title` como input de texto.
- Campo `description` como textarea.
- Botón principal: `Crear ticket`.

Validaciones visuales recomendadas en HTML:

- `title` requerido.
- `title` máximo 200 caracteres.
- `description` requerida.
- `description` máximo 5000 caracteres.

El formulario debe enviar los datos mediante HTMX y refrescar el tablero sin recargar toda la página.

### 3.2 Tablero con lista de tickets

Debe mostrar los tickets en una tabla o tablero equivalente.

Campos obligatorios visibles:

- `id`
- `title`
- `category`
- `priority`
- `tags`
- `status`
- `created_at`

El tablero no puede ser una tabla sin formato. Debe tener una presentación visual mínima con Tailwind.

### 3.3 Filtros encima del tablero

Debe haber tres filtros:

- `category`
- `priority`
- `status`

Cada filtro debe ser un `<select>`.

Al cambiar un filtro, el tablero debe actualizarse mediante HTMX sin recargar toda la página.

Debe existir una opción para ver todos los valores, por ejemplo:

- `Todas las categorías`
- `Todas las prioridades`
- `Todos los estados`

Opcional pero recomendable:

- botón `Limpiar filtros`.

---

## 4. Importante: no romper la API JSON existente

Los tests obligatorios usan los endpoints API existentes, especialmente:

- `POST /tickets`
- `GET /tickets`
- `GET /tickets/{id}`
- `PATCH /tickets/{id}`

Por tanto:

> El frontend no debe romper las respuestas JSON que ya esperan los tests.

### Decisión recomendada

Mantener los endpoints JSON existentes y crear endpoints HTMX separados para devolver fragmentos HTML.

Endpoints recomendados para frontend:

| Endpoint | Uso | Respuesta |
|---|---|---|
| `GET /` | Página principal completa | HTML |
| `GET /tickets/board` | Fragmento del tablero filtrado | HTML parcial |
| `POST /tickets/form` | Crear ticket desde formulario HTMX | HTML parcial actualizado |

Los endpoints JSON existentes deben seguir funcionando como antes.

### Alternativa aceptable

También es aceptable que `POST /tickets` devuelva JSON para peticiones normales y HTML parcial solo cuando detecte una petición HTMX (`HX-Request: true`).

Pero para evitar romper tests, la opción más clara es usar endpoints HTMX separados.

---

## 5. Arquitectura de templates

Usar `Jinja2Templates`.

Estructura recomendada:

```text
templates/
  index.html
  partials/
    tickets_board.html
```

Opcional:

```text
templates/
  partials/
    ticket_row.html
    empty_state.html
```

### Regla

No escribir HTML grande como string dentro de `app/main.py`.

`main.py` debe encargarse de:

- recibir requests;
- consultar o crear tickets;
- pasar datos a templates;
- devolver `TemplateResponse` o `HTMLResponse`.

Los templates deben encargarse de renderizar la UI.

---

## 6. HTMX: comportamiento esperado

### 6.1 Crear ticket sin recargar la página

El formulario debe enviar los campos `title` y `description`.

Como HTMX envía formularios como `application/x-www-form-urlencoded` por defecto, el endpoint HTMX recomendado debe aceptar datos de formulario con `Form(...)`.

Ejemplo conceptual:

```html
<form
  hx-post="/tickets/form"
  hx-target="#tickets-board"
  hx-swap="innerHTML"
>
  <input name="title" />
  <textarea name="description"></textarea>
  <button type="submit">Crear ticket</button>
</form>

<div id="tickets-board">
  <!-- aquí se renderiza templates/partials/tickets_board.html -->
</div>
```

Después de crear el ticket:

- el ticket debe aparecer inmediatamente en el tablero;
- la página no debe recargarse entera;
- si es posible, el formulario debería limpiarse o mostrar feedback de éxito.

### 6.2 Filtrar al cambiar selects

Los selects deben actualizar el tablero.

Ejemplo conceptual:

```html
<form id="filters">
  <select
    name="category"
    hx-get="/tickets/board"
    hx-target="#tickets-board"
    hx-trigger="change"
    hx-include="#filters"
  >
    <option value="">Todas las categorías</option>
    <option value="bug">Error</option>
    <option value="feature_request">Nueva funcionalidad</option>
    <option value="question">Consulta</option>
    <option value="urgent">Urgente</option>
  </select>
</form>
```

El mismo patrón aplica para `priority` y `status`.

### 6.3 El backend devuelve HTML parcial para HTMX

Los endpoints HTMX deben devolver fragmentos HTML, no JSON.

Ejemplo:

```text
GET /tickets/board?category=bug&priority=P1&status=open
```

Debe devolver solo el HTML del tablero, no la página completa.

---

## 7. Diseño UI/UX

El frontend debe ser simple, claro y útil. No buscamos una interfaz espectacular, pero sí una interfaz que parezca producto y no una tabla sin formato.

### 7.1 Layout recomendado

```text
--------------------------------------------------
TriageBot
Crea, clasifica y gestiona tickets automáticamente
--------------------------------------------------

[ Card: Crear ticket ]
Título: [________________________]
Descripción:
[________________________________]
[________________________________]
                    [ Crear ticket ]

[ Filtros ]
[Categoría v] [Prioridad v] [Estado v] [Limpiar filtros]

[ Tablero de tickets ]
| ID | Título | Categoría | Prioridad | Tags | Estado | Fecha |
|----|--------|-----------|-----------|------|--------|-------|
```

### 7.2 Jerarquía visual

Orden recomendado en la página:

1. Cabecera clara.
2. Formulario de creación.
3. Filtros.
4. Tablero.

El usuario debe entender en menos de cinco segundos qué puede hacer.

### 7.3 Lenguaje de la interfaz

La interfaz debe estar en español porque la demo y el briefing están en español.

Labels recomendadas:

| Campo técnico | Label visible |
|---|---|
| `title` | `Título` |
| `description` | `Descripción` |
| `category` | `Categoría` |
| `priority` | `Prioridad` |
| `status` | `Estado` |
| `tags` | `Etiquetas` |
| `created_at` | `Creado` |

Botones:

- `Crear ticket`
- `Limpiar filtros`

Mensajes:

- `Todavía no hay tickets.`
- `Crea el primer ticket para empezar.`
- `Ticket creado correctamente.`
- `No se ha podido crear el ticket.`

### 7.4 Traducción visual de enums

Los valores internos del backend no deben cambiar, pero la UI puede mostrarlos de forma más humana.

#### Categorías

| Valor interno | Texto visible |
|---|---|
| `bug` | `Error` |
| `feature_request` | `Nueva funcionalidad` |
| `question` | `Consulta` |
| `urgent` | `Urgente` |

#### Prioridades

| Valor interno | Texto visible |
|---|---|
| `P1` | `P1 · Alta` |
| `P2` | `P2 · Media` |
| `P3` | `P3 · Normal` |

#### Estados

| Valor interno | Texto visible |
|---|---|
| `open` | `Abierto` |
| `in_progress` | `En progreso` |
| `closed` | `Cerrado` |

---

## 8. Colores y badges

Usar badges para que Marta identifique rápido qué importa más.

### 8.1 Prioridad

`P1` debe destacar más que el resto.

Sugerencia visual:

| Prioridad | Estilo sugerido |
|---|---|
| `P1` | badge rojo / destacado |
| `P2` | badge ámbar |
| `P3` | badge gris o verde suave |

### 8.2 Categoría

| Categoría | Estilo sugerido |
|---|---|
| `bug` | rojo suave |
| `feature_request` | azul |
| `question` | gris o morado suave |
| `urgent` | naranja o rojo intenso |

### 8.3 Status

| Status | Estilo sugerido |
|---|---|
| `open` | azul o gris |
| `in_progress` | amarillo / ámbar |
| `closed` | verde |

### 8.4 Tags

Los tags deben mostrarse como chips pequeños, no como una lista fea de Python.

Ejemplo visual:

```text
[login] [backend] [error_500]
```

---

## 9. Estados de UI

La interfaz debe contemplar estos estados.

### 9.1 Estado vacío

Cuando no hay tickets:

```text
Todavía no hay tickets.
Crea el primer ticket para empezar.
```

### 9.2 Estado cargando

HTMX puede mostrar un indicador simple.

Ejemplo:

```html
<div class="htmx-indicator">Actualizando tablero...</div>
```

### 9.3 Estado de error

Si la creación falla, mostrar un mensaje claro.

Ejemplo:

```text
No se ha podido crear el ticket. Revisa el título y la descripción.
```

No hace falta construir un sistema complejo de toasts. Un mensaje visible es suficiente.

---

## 10. Accesibilidad mínima

La UI debe cumplir mínimos básicos:

- Cada input debe tener `<label>`.
- El botón principal debe tener texto claro.
- No depender solo del color para entender prioridad o estado.
- Los badges deben tener texto visible.
- La tabla debe tener encabezados claros.
- Los campos deben tener `name` correctos para que HTMX envíe los datos.

---

## 11. Detalles backend para implementar el frontend

### 11.1 `GET /`

Debe devolver `templates/index.html`.

Debe cargar los tickets iniciales, probablemente sin filtros.

Debe incluir por CDN:

- HTMX
- Tailwind CSS

Ejemplo conceptual:

```html
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<script src="https://cdn.tailwindcss.com"></script>
```

### 11.2 `GET /tickets/board`

Debe aceptar query params opcionales:

- `category`
- `priority`
- `status`

Debe devolver `templates/partials/tickets_board.html`.

Debe reutilizar la misma lógica de filtrado que `GET /tickets` o una función común para evitar duplicación innecesaria.

### 11.3 `POST /tickets/form`

Debe aceptar datos de formulario:

- `title`
- `description`

Debe crear un ticket usando la misma lógica que el endpoint JSON.

Después debe devolver el tablero actualizado como HTML parcial.

Debe aplicar las mismas validaciones que el API:

- `title` no vacío tras trim;
- `title` máximo 200;
- `description` no vacía tras trim;
- `description` máximo 5000.

Si la validación falla, debe devolver un error visual o un fragmento con mensaje de error.

---

## 12. Reglas de implementación

### No hacer

- No usar React.
- No usar Vue.
- No usar frontend con build tools.
- No usar npm.
- No meter HTML grande como string dentro de `main.py`.
- No modificar `tests/test_acceptance.py`.
- No cambiar los nombres internos de enums.
- No romper los endpoints JSON existentes.
- No hardcodear respuestas falsas para que la demo parezca funcionar.
- No llamar al LLM desde el frontend.
- No commitear `.env`.

### Sí hacer

- Usar Jinja2 templates.
- Usar Tailwind por CDN.
- Usar HTMX para formulario y filtros.
- Usar badges visuales.
- Usar labels en español.
- Mantener los tests obligatorios verdes.
- Mantener CI verde.
- Mantener la lógica de tickets en backend.

---

## 13. Criterios de aceptación del frontend

El Lab 4 se considera cumplido cuando:

- [ ] `GET /` devuelve una página HTML completa.
- [ ] La página tiene formulario para crear tickets.
- [ ] El formulario tiene `title`, `description` y botón `Crear ticket`.
- [ ] Crear un ticket desde el formulario funciona.
- [ ] El ticket creado aparece inmediatamente en el tablero sin recargar toda la página.
- [ ] El tablero muestra `id`, `title`, `category`, `priority`, `tags`, `status`, `created_at`.
- [ ] Hay filtros para `category`, `priority` y `status`.
- [ ] Al cambiar un filtro, el tablero se actualiza sin recargar toda la página.
- [ ] La prioridad `P1` destaca visualmente.
- [ ] La UI está en español o, como mínimo, los labels visibles principales están en español.
- [ ] El tablero es visualmente accesible y no parece una tabla sin formato.
- [ ] Los tests obligatorios siguen verdes con `pytest`.
- [ ] `ruff` sigue verde.
- [ ] CI está verde en GitHub Actions.

---

## 14. Plan de implementación recomendado

Claude Code debe proponer un plan parecido a este antes de implementar.

### Paso 1 — Revisar estructura actual

- Leer `app/main.py`.
- Leer modelos y funciones existentes para tickets.
- Confirmar cómo se crean, listan y filtran tickets.
- Confirmar cómo se ejecutan los tests.

### Paso 2 — Añadir templates

Crear:

```text
templates/index.html
templates/partials/tickets_board.html
```

### Paso 3 — Configurar Jinja2 en FastAPI

Añadir `Jinja2Templates` en `app/main.py` o en el módulo adecuado.

### Paso 4 — Crear `GET /`

Renderizar la página completa.

### Paso 5 — Crear endpoint de tablero parcial

Crear:

```text
GET /tickets/board
```

Debe aplicar filtros y devolver solo el fragmento HTML del tablero.

### Paso 6 — Crear endpoint HTMX para formulario

Crear:

```text
POST /tickets/form
```

Debe aceptar `Form(...)`, crear ticket y devolver tablero actualizado.

### Paso 7 — Añadir HTMX al HTML

- `hx-post` en formulario.
- `hx-get` en filtros.
- `hx-target="#tickets-board"`.
- `hx-swap="innerHTML"`.

### Paso 8 — Mejorar UI visual

- Tailwind CDN.
- Cards.
- Tabla con cabecera clara.
- Badges.
- Empty state.

### Paso 9 — Ejecutar checks

Ejecutar:

```bash
pytest
ruff check .
```

Arreglar errores sin modificar los tests obligatorios.

---

## 15. Posibles errores típicos y cómo evitarlos

### Error 1: el POST funciona en curl pero no en el formulario

Causa probable:

- El endpoint espera JSON pero HTMX envía form data.

Solución recomendada:

- Usar endpoint HTMX separado con `Form(...)`.

### Error 2: después de crear un ticket no se actualiza la lista

Causa probable:

- `hx-target` apunta a un id que no existe.
- El endpoint devuelve JSON en lugar de HTML.
- `hx-swap` no está bien configurado.

Solución:

- Asegurar que existe `<div id="tickets-board">`.
- Asegurar que el endpoint devuelve HTML parcial.
- Usar `hx-swap="innerHTML"`.

### Error 3: los filtros funcionan pero al refrescar se pierden

No es grave para el MVP.

Opcionalmente se puede mantener el estado en query params, pero no es obligatorio si el tablero filtra correctamente al cambiar selects.

### Error 4: Tailwind no carga

Causa probable:

- Script CDN mal escrito.
- No hay conexión a internet.

Solución:

- Verificar el CDN.
- Mantener HTML usable aunque Tailwind no cargue.

### Error 5: la UI mezcla inglés y español

Solución:

- Mantener labels visibles en español.
- Usar traducción visual de enums en templates.
- No cambiar los valores internos del backend.

---

## 16. Definición final de “hecho”

El frontend está hecho cuando una persona puede abrir:

```text
http://localhost:8000/
```

y hacer esto sin usar Postman ni curl:

1. Crear un ticket.
2. Verlo aparecer en el tablero.
3. Identificar visualmente su categoría, prioridad y estado.
4. Filtrar por categoría, prioridad o estado.
5. Recargar la página y seguir viendo una interfaz clara.

Además:

```bash
pytest
ruff check .
```

deben pasar correctamente.

