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

## 0.1 Estado actual de templates

La carpeta `templates/` **ya existe** y contiene estos archivos base:

```text
templates/
├── index.html
└── _tickets_table.html
```

Por tanto, **no hay que crear una arquitectura nueva de templates desde cero**. La tarea principal es completar los archivos existentes.

### `templates/index.html` existente

Este archivo ya contiene:

- estructura HTML base;
- idioma `lang="es"`;
- título `TriageBot`;
- Tailwind CSS cargado por CDN;
- HTMX cargado por CDN;
- cabecera inicial de la app;
- un TODO para añadir formulario, filtros y tabla HTMX.

Debe completarse aquí la página principal.

### `templates/_tickets_table.html` existente

Este archivo ya contiene una tabla base con columnas:

- `ID`
- `Título`
- `Categoría`
- `Prioridad`
- `Tags`
- `Estado`
- `Creado`

Y contiene un TODO dentro del `<tbody>` para renderizar tickets con Jinja2.

Debe completarse aquí el renderizado del tablero.

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
- Usa los templates existentes: templates/index.html y templates/_tickets_table.html.
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

Debe mostrar los tickets en una tabla visual.

Campos obligatorios visibles:

- `id`
- `title`
- `category`
- `priority`
- `deadline` — con badge "Vencido" en rojo si el ticket está vencido y no cerrado
- `tags`
- `status` — con sublínea "desde {fecha}" usando `status_since`
- `created_at`

El tablero no puede ser una tabla sin formato. Debe tener una presentación visual mínima con Tailwind.

### 3.3 Filtros encima del tablero

Debe haber cuatro filtros:

- `category`
- `priority`
- `status`
- `overdue` — select con opciones "Todos" / "Solo vencidos" (envía `overdue=true` a `GET /tickets/table`)

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
| `GET /tickets/table` | Fragmento de tabla filtrada | HTML parcial |
| `POST /tickets/form` | Crear ticket desde formulario HTMX | HTML parcial actualizado |

Los endpoints JSON existentes deben seguir funcionando como antes.

### Alternativa aceptable

También es aceptable que `POST /tickets` devuelva JSON para peticiones normales y HTML parcial solo cuando detecte una petición HTMX (`HX-Request: true`).

Pero para evitar romper tests, la opción más clara es usar endpoints HTMX separados.

---

## 5. Arquitectura de templates actualizada

Usar `Jinja2Templates`.

La estructura real del proyecto ya es:

```text
templates/
├── index.html
└── _tickets_table.html
```

No crear una carpeta `partials/` nueva salvo que haya una razón fuerte. Para este Lab, es suficiente completar los dos templates existentes.

### 5.1 `templates/index.html`

Responsabilidad: página completa servida por `GET /`.

Debe contener:

- cabecera de la app;
- formulario para crear tickets;
- filtros por `category`, `priority` y `status`;
- contenedor del tablero;
- inclusión/renderizado de `_tickets_table.html`.

Este archivo ya carga Tailwind CSS y HTMX por CDN. Mantener ese enfoque.

No añadir:

- React;
- Vite;
- Webpack;
- npm;
- build tools.

Ejemplo conceptual de contenedor:

```html
<div id="tickets-table">
  {% include "_tickets_table.html" %}
</div>
```

El formulario debe apuntar a ese contenedor:

```html
<form
  hx-post="/tickets/form"
  hx-target="#tickets-table"
  hx-swap="innerHTML"
>
  <!-- title + description + botón -->
</form>
```

Los filtros también deben actualizar ese mismo contenedor:

```html
<form id="ticket-filters">
  <select
    name="category"
    hx-get="/tickets/table"
    hx-target="#tickets-table"
    hx-trigger="change"
    hx-include="#ticket-filters"
    hx-swap="innerHTML"
  >
    <!-- opciones -->
  </select>
</form>
```

El mismo patrón aplica a `priority` y `status`.

### 5.2 `templates/_tickets_table.html`

Responsabilidad: partial reutilizable de la tabla.

No debe ser una página HTML completa. No debe tener `<html>`, `<head>` ni `<body>`.

Debe renderizar la tabla de tickets usando Jinja2.

Debe mostrar, como mínimo:

- `id`;
- `title`;
- `category`;
- `priority`;
- `tags`;
- `status`;
- `created_at`.

Debe incluir:

- badges visuales para `priority`;
- color o badge para `category`;
- badge para `status`;
- chips para `tags`;
- estado vacío si no hay tickets.

Ejemplo de estado vacío:

```text
Todavía no hay tickets. Crea el primero desde el formulario.
```

El archivo ya tiene un `<tbody id="tickets-table-body">`. Completar ese bloque con un loop Jinja2.

Ejemplo conceptual:

```html
<tbody id="tickets-table-body">
  {% if tickets %}
    {% for ticket in tickets %}
      <tr>
        <td>{{ ticket.id }}</td>
        <td>{{ ticket.title }}</td>
        <td>{{ ticket.category }}</td>
        <td>{{ ticket.priority }}</td>
        <td>
          {% for tag in ticket.tags %}
            <span>{{ tag }}</span>
          {% endfor %}
        </td>
        <td>{{ ticket.status }}</td>
        <td>{{ ticket.created_at }}</td>
      </tr>
    {% endfor %}
  {% else %}
    <tr>
      <td colspan="7">Todavía no hay tickets. Crea el primero desde el formulario.</td>
    </tr>
  {% endif %}
</tbody>
```

### 5.3 No meter HTML grande en `main.py`

`main.py` debe renderizar templates con Jinja2, no construir HTML como strings largos.

Correcto:

```python
return templates.TemplateResponse(
    "index.html",
    {"request": request, "tickets": tickets},
)
```

Correcto para el partial:

```python
return templates.TemplateResponse(
    "_tickets_table.html",
    {"request": request, "tickets": tickets},
)
```

Incorrecto:

```python
return HTMLResponse("<html>...</html>")
```

### 5.4 Separación clara entre API JSON y HTMX

Mantener los endpoints JSON existentes:

```text
GET /tickets
POST /tickets
GET /tickets/{id}
PATCH /tickets/{id}
```

Añadir endpoints HTML/HTMX:

```text
GET /
GET /tickets/table
POST /tickets/form
```

Así se separa claramente:

```text
API JSON:
GET /tickets
POST /tickets
GET /tickets/{id}
PATCH /tickets/{id}

HTMX / HTML:
GET /
GET /tickets/table
POST /tickets/form
```

Punto crítico:

> No cambiar `GET /tickets` para que devuelva HTML, porque actualmente debe devolver JSON para cumplir los tests obligatorios.

---

## 6. HTMX: comportamiento esperado

### 6.1 Crear ticket sin recargar la página

El formulario debe enviar los campos `title` y `description`.

Como HTMX envía formularios como `application/x-www-form-urlencoded` por defecto, el endpoint HTMX recomendado debe aceptar datos de formulario con `Form(...)`.

Ejemplo conceptual:

```html
<form
  hx-post="/tickets/form"
  hx-target="#tickets-table"
  hx-swap="innerHTML"
>
  <input name="title" />
  <textarea name="description"></textarea>
  <button type="submit">Crear ticket</button>
</form>

<div id="tickets-table">
  {% include "_tickets_table.html" %}
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
<form id="ticket-filters">
  <select
    name="category"
    hx-get="/tickets/table"
    hx-target="#tickets-table"
    hx-trigger="change"
    hx-include="#ticket-filters"
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
GET /tickets/table?category=bug&priority=P1&status=open
```

Debe devolver solo el HTML de `_tickets_table.html`, no la página completa.

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

### 7.3 Pensar como Marta

Antes de programar, priorizar estas preguntas:

- ¿Qué columna del tablero le importa más? Probablemente prioridad. `P1` debe destacar.
- ¿Qué filtra primero? Probablemente `status=open`, porque no quiere ver lo cerrado.
- ¿Qué le frustra? Clics innecesarios. Cada acción importante debe estar a un clic.

### 7.4 Lenguaje de la interfaz

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

### 7.5 Traducción visual de enums

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

#### Vencimiento (deadline)

Un ticket es **vencido** cuando `deadline < ahora` y `status != "closed"`. El tablero lo señala con fila en rojo suave y badge "Vencido". El filtro "Solo vencidos" muestra solo estos tickets.

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

El template `index.html` ya incluye por CDN:

- HTMX
- Tailwind CSS

No duplicar innecesariamente los scripts si ya están en el template.

### 11.2 `GET /tickets/table`

Debe aceptar query params opcionales:

- `category`
- `priority`
- `status`

Debe devolver `templates/_tickets_table.html`.

Debe reutilizar la misma lógica de filtrado que `GET /tickets` o una función común para evitar duplicación innecesaria.

### 11.3 `POST /tickets/form`

Debe aceptar datos de formulario:

- `title`
- `description`

Debe crear un ticket usando la misma lógica que el endpoint JSON.

Después debe devolver el tablero actualizado como HTML parcial usando `templates/_tickets_table.html`.

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
- No crear otra arquitectura de templates si no hace falta.

### Sí hacer

- Completar `templates/index.html`.
- Completar `templates/_tickets_table.html`.
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
- Leer `templates/index.html`.
- Leer `templates/_tickets_table.html`.
- Confirmar cómo se crean, listan y filtran tickets.
- Confirmar cómo se ejecutan los tests.

### Paso 2 — Configurar o confirmar Jinja2 en FastAPI

Confirmar que existe `Jinja2Templates(directory="templates")`.

Si no existe, añadirlo en `app/main.py` o en el módulo adecuado.

### Paso 3 — Crear o completar `GET /`

Renderizar `templates/index.html`.

Debe pasar a la plantilla:

- `request`;
- `tickets` iniciales sin filtros.

### Paso 4 — Completar `templates/index.html`

Añadir:

- card del formulario;
- filtros;
- contenedor `<div id="tickets-table">`;
- `{% include "_tickets_table.html" %}` dentro del contenedor.

### Paso 5 — Completar `templates/_tickets_table.html`

Añadir loop Jinja2 sobre `tickets`.

Renderizar:

- filas de tickets;
- badges;
- chips de tags;
- estado vacío.

### Paso 6 — Crear endpoint de tabla parcial

Crear:

```text
GET /tickets/table
```

Debe aplicar filtros y devolver solo `templates/_tickets_table.html`.

### Paso 7 — Crear endpoint HTMX para formulario

Crear:

```text
POST /tickets/form
```

Debe aceptar `Form(...)`, crear ticket y devolver `templates/_tickets_table.html` actualizado.

### Paso 8 — Añadir HTMX al HTML

- `hx-post="/tickets/form"` en formulario.
- `hx-get="/tickets/table"` en filtros.
- `hx-target="#tickets-table"`.
- `hx-swap="innerHTML"`.
- `hx-include="#ticket-filters"` en filtros.

### Paso 9 — Mejorar UI visual

- Tailwind CDN.
- Cards.
- Tabla con cabecera clara.
- Badges.
- Empty state.
- Labels en español.

### Paso 10 — Ejecutar checks

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

- Asegurar que existe `<div id="tickets-table">`.
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

### Error 6: se rompe `GET /tickets`

Causa probable:

- Se ha cambiado `GET /tickets` para devolver HTML en lugar de JSON.

Solución:

- Restaurar `GET /tickets` como JSON.
- Usar `GET /tickets/table` para HTML parcial.

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
