# Marcello V1

Aplicación web para realizar encuestas de levantamiento de requisitos (15 preguntas fijas), guardar las respuestas en PostgreSQL y consultarlas/exportarlas desde un panel administrativo.

**Stack:** FastAPI (Python 3.12) · PostgreSQL 16 · SQLAlchemy · Alembic · Pydantic · OpenPyXL · Pandas · Uvicorn · Docker Compose · HTML/CSS/JS sin frameworks.

## Requisitos previos
- Linux con **Docker Engine** y el plugin **Docker Compose v2** (`docker compose version`).
- Git. (Para publicar: cuenta de GitHub.)

## Instalación y configuración
```bash
git clone URL_DEL_REPOSITORIO
cd marcello-v1
cp .env.example .env
```
Edite `.env` y complete **todos** los valores (la app no arranca con valores vacíos):
```bash
openssl rand -hex 24   # → POSTGRES_PASSWORD
openssl rand -hex 32   # → SECRET_KEY
# ADMIN_USER / ADMIN_PASSWORD (mínimo 10 caracteres) → acceso a /admin
```
Si publica detrás de HTTPS ponga `COOKIE_SECURE=true`.

## Inicio, detención y reinicio
```bash
docker compose up --build -d      # inicia (aplica migraciones y siembra el cuestionario automáticamente)
docker compose logs -f app        # ver registros
docker compose restart            # reinicia
docker compose stop               # detiene (conserva datos)
docker compose down               # elimina contenedores (conserva el volumen de datos)
docker compose down -v            # ¡BORRA también la base de datos!
```
Disponible en **http://localhost:8000** (encuesta pública) y **http://localhost:8000/admin** (panel).
Los datos viven en el volumen Docker `marcello_pgdata` y sobreviven a reinicios y recreaciones.

## Acceso administrativo
`/admin` pide el usuario y la contraseña de `ADMIN_USER` / `ADMIN_PASSWORD`. Tras 5 intentos fallidos desde una IP se bloquea 5 minutos. No hay enlace al panel desde la página pública.
Opcional: en lugar de `ADMIN_PASSWORD` puede usar `ADMIN_PASSWORD_HASH` (genérelo con `python -m app.security`; en `.env` póngalo entre comillas simples porque contiene `$`).

## Exportaciones (botones del panel)
| Botón | Contenido |
|---|---|
| Excel `.xlsx` | 4 hojas: Respuestas (1 fila por participante; múltiples en columnas 0/1), Diccionario de preguntas, Catálogo de opciones, Estadísticas |
| CSV `.csv` | 1 fila por participante, UTF-8 (con BOM para Excel; pandas/R/Power BI lo leen bien) |
| JSON `.json` | UUID, fecha UTC, ubicación, versión, preguntas y respuestas |
| PostgreSQL `.sql` / `.dump` | Respaldo completo con `pg_dump` (texto plano / formato custom) |

Excel, CSV y JSON **excluyen datos de prueba** salvo que active "Incluir datos de prueba". Los respaldos PostgreSQL son siempre de toda la base. Todas las rutas exigen sesión de administrador.

## Respaldo y restauración de PostgreSQL
Respaldo manual (además del botón del panel):
```bash
set -a; . ./.env; set +a
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner > respaldo.sql
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > respaldo.dump
```
Restauración (sobre una instancia levantada con `docker compose up -d`):
```bash
set -a; . ./.env; set +a
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < respaldo.sql
# o, para .dump:
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner < respaldo.dump
```
Guarde los respaldos fuera del repositorio (los `*.sql` y `*.dump` ya están en `.gitignore`).

## Pruebas automáticas
```bash
docker compose --profile test run --rm tests
```
Usa una base separada `marcello_test` (la suite se niega a correr contra una base cuyo nombre no termine en `_test`). Cubre: envío y validación de las 15 preguntas, almacenamiento en PostgreSQL, migración Alembic, protección del panel, consultas/filtros/paginación, estadísticas, exportaciones Excel/CSV/JSON y respaldos `pg_dump`, con **1.000 registros ficticios**.

### Datos de prueba
Todo dato ficticio se guarda con `is_test = true` y no aparece en el panel ni en las exportaciones salvo que se pida. Para cargar/borrar datos de demostración:
```bash
docker compose exec app python -m app.services.seed_test_data --n 1000
docker compose exec app python -m app.services.seed_test_data --purge   # borra solo is_test = true
```
**Antes de abrir la encuesta al público, ejecute `--purge`** si cargó datos de demostración.

## Privacidad y seguridad
- No se recopilan nombres, documentos, correos ni GPS; el backend rechaza cualquier campo no previsto. La encuesta ya no pregunta ubicación: país, departamento y ciudad se guardan como "No informado".
- Contraseña admin con bcrypt, sesión firmada (cookie `HttpOnly`, `SameSite=Strict`), rutas y exportaciones protegidas, consultas parametrizadas (SQLAlchemy), validación en frontend y backend, CSP estricta, límites de frecuencia por IP, neutralización de fórmulas (`=`, `+`, `-`, `@`) en CSV/Excel.
- Los límites por IP están en memoria y asumen 1 proceso; detrás de un proxy inverso verá la IP del proxy.
- No hay guardado parcial: el cuestionario se pierde si se recarga antes de enviar (no se usa localStorage).

## Cambiar el cuestionario
La versión `v1` vive en `app/survey_definition.py`. Una vez hay respuestas **no la edite**: cree una versión nueva (y una migración/semilla) para no alterar resultados históricos.

## Estructura
```
app/ (main, config, database, models, schemas, security, seed, routers/, services/, templates/)
static/ (css, js, assets)   migrations/ (Alembic)   tests/
Dockerfile · docker-compose.yml · requirements*.txt · .env.example
```

## Publicar en GitHub
```bash
git init -b main
git add .
git status          # verifique que .env NO aparece
git commit -m "Marcello V1: versión inicial"
# Cree un repositorio vacío en GitHub y luego:
git remote add origin git@github.com:USUARIO/marcello-v1.git
git push -u origin main
```
