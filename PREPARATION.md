# n8n Connector — Preparation

**Статус:** Фаза 1 завершена — все открытые вопросы закрыты Владом
2026-08-18. Готово к Фазе 2 (дизайн панелей).
**Владелец продукта:** vlad@bluebeeweb.com
**Дата подготовки:** 2026-08-18, v0.2 (открытые вопросы закрыты)
**Почему сейчас:** в портфеле Imperal уже есть коннектор к Make.com (см.
`Apps/Make.com Connector`), построенный на паттерне BYOK + REST API моста
между Imperal и внешней no-code automation платформой. n8n — вторая по
популярности (и самая популярная self-hosted/open-source) automation
платформа в том же классе: пользователи Imperal, которые вместо Make
используют n8n (свой сервер или n8n Cloud), сейчас не имеют такого же
моста. Это естественное расширение той же категории интеграций, тем же
проверенным паттерном — не гипотеза с нуля.

---

## 1. Паспорт приложения

**Название в Marketplace (display_name): «n8n»** — по аналогии с решением
для Make.com (там тоже решили короче, без слова Connector, см. запись в
Make.com PREPARATION.md раздел 1). Внутренний app_id/папка:
`n8n-connector`. Проверено: `search_marketplace` по «n8n» и по общим
терминам workflow/automation не нашёл ни одного существующего или
похожего приложения — дублей нет (см. Журнал проверок, раздел 6).

**n8n Connector** — коннектор к n8n Public REST API (`/api/v1/...`). Даёт
Webbee возможность от имени пользователя читать и управлять его
workflow'ами n8n (list/get/create/update/delete, publish/unpublish,
запустить вручную там, где инстанс это поддерживает), видеть их
executions (list/get/retry/stop/delete), и работать с тегами. Как и
Make.com Connector, это BYOK — пользователь подключает СВОЙ n8n instance
(self-hosted сервер или свой n8n Cloud аккаунт) своим собственным API
ключом; Imperal ничего не хостит и не проксирует помимо самого запроса.

---

## 2. Ключевые факты об n8n Public API (проверено по официальной
документации docs.n8n.io, не по догадке)

### 2.1 Аутентификация — ОДИН заголовок, НЕ Bearer/Basic

Источник: `docs.n8n.io/connect/n8n-api/authentication` (прочитано
дословно 2026-08-18).

- Заголовок: **`X-N8N-API-KEY: <your-api-key>`** — ровно так, без
  Bearer/Token префикса. Отличается и от Make.com (`Authorization: Token
  <token>`), и от DataForSEO (Basic auth) — значит строится свой, а не
  копируется чужой.
- Ключ создаётся пользователем в самом n8n: `Log in → Settings → n8n API
  → Create an API key` — задаётся Label и Expiration; на Enterprise-плане
  дополнительно можно выставить конкретные **Scopes** (community
  packages, credentials, data tables + columns + rows, executions,
  execution tags, folders, insights, projects, security audit, source
  control, tags, users, variables, workflows, workflow tags). На
  Community/self-hosted free плане скоупинга может не быть — ключ даёт
  доступ ко всему, на что способна сама Public API.

### 2.2 Base URL — НЕТ фиксированных «зон», в отличие от Make.com

Это ключевое архитектурное отличие от Make.com Connector, и здесь нельзя
скопировать паттерн zone-discovery один в один.

- **Self-hosted**: `<N8N_HOST>:<N8N_PORT>/<N8N_PATH>/api/v<version>/...`
  — произвольный хост, порт и путь, целиком определяется тем, как
  пользователь у себя развернул n8n (Docker/Railway/VPS/итд). Нет
  никакого публичного списка возможных хостов, которые можно перебрать.
- **n8n Cloud**: `<your-cloud-instance>/api/v<version>/...` — тоже
  персональный поддомен конкретного пользователя (`xxx.app.n8n.cloud`
  и т.п.), не общий фиксированный хост.
- **Вывод:** у n8n в принципе нет аналога `discover_zone` из Make.com —
  URL инстанса физически невозможно угадать перебором, его обязан ввести
  сам пользователь. Модель подключения здесь ближе к **WordPress
  Hub/DataForSEO** (пользователь явно вводит URL + ключ), чем к Make.com
  (авто-подбор зоны по токену). Это решённый факт, не открытый вопрос —
  но UX последствия из него закреплены как решение в разделе 3 (п.2
  таблицы решений).

### 2.3 Workflows API — набор эндпоинтов (per docs.n8n.io/connect/n8n-api)

- `GET /workflows` — список (с пагинацией через cursor, фильтры вроде
  `active`).
- `GET /workflows/{id}` — одна workflow.
- `POST /workflows` — создать.
- `PUT /workflows/{id}` — обновить (полная замена, не PATCH).
- `DELETE /workflows/{id}` — удалить.
- `GET/PUT /workflows/{id}/tags` — теги workflow.

### 2.4 Активация/публикация — ВАЖНО: старый endpoint deprecated

Источник: GitHub issues n8n-io/n8n **#34771** и **#34745** (оба
официальные, от команды n8n).

- Старые `POST /workflows/{id}/activate` и `POST
  /workflows/{id}/deactivate` **объявлены deprecated**.
- Новый стандарт: **`POST /workflows/{id}/publish`** и **`POST
  /workflows/{id}/unpublish`**.
- **Решение:** строим `set_workflow_active`-эквивалент сразу на
  publish/unpublish, а не на устаревающем activate/deactivate — иначе
  ловим технический долг с первого дня, ровно то, чего осознанно
  избегали при выборе `write_mode="both"` и прочих паттернов в
  Make.com Connector.

### 2.5 «Запустить workflow по ID» — НЕ гарантированная возможность на
всех инстансах, критичный нюанс

Источник: GitHub PR n8n-io/n8n **#23435** и **#20234** (добавление
эндпоинта), плюс форумный тред n8n Community **«Executing a workflow via
API call (without webhook or CLI command)»** (2025-10-28, до появления
этого PR).

- Новый эндпоинт: **`POST /workflows/{id}/execute`** — программный запуск
  workflow без webhook, возвращает `executionId` асинхронно. Требует
  scope `workflow:execute`.
- **Это относительно новая возможность** (PR датированы концом 2025) —
  до неё официальный ответ команды n8n на «как запустить workflow через
  API» был **«никак, только через Webhook node URL»**. Значит на СТАРЫХ
  версиях self-hosted n8n (а self-hosted — это ключевой сценарий
  использования n8n вообще, в отличие от Make.com, который весь в
  облаке) этого эндпоинта физически может не быть.
- **Решение:** `run_workflow`-инструмент обязан явно обрабатывать 404 на
  этом эндпоинте как «твоя версия n8n не поддерживает прямой запуск —
  добавь Webhook-триггер в workflow и вызови его URL напрямую», а НЕ как
  общую ошибку подключения. Это прямая параллель тому, как Make.com
  Connector в `make_client.py` различает «зона не узнала токен» (401,
  пробуем дальше) от «зона узнала, но не хватает scope» (403,
  останавливаемся с точным сообщением) — тот же принцип: разные коды
  ошибок значат разное, нельзя схлопывать их в одно сообщение.

### 2.6 Executions API

- `GET /executions` — список, фильтры по `status`/`workflowId`,
  пагинация через cursor.
- `GET /executions/{id}` — одно исполнение (с опцией `includeData`,
  `unmaskData` — то самое поле `execution:reveal` scope для нередактированных
  данных).
- `DELETE /executions/{id}` — удалить.
- `POST /executions/{id}/retry` — повторить (опция `loadWorkflow` —
  подхватить текущую версию workflow вместо версии на момент исполнения).
- `POST /executions/{id}/stop` — остановить одно.
- `POST /executions/stop` — остановить **массово**, по фильтру
  (`status`, `workflowId`, `startedAfter`/`startedBefore`) — уже
  встроенная bulk-операция на стороне самого n8n, не нужно эмулировать
  её собственным циклом по одному.
- `GET/PUT /executions/{id}/tags` — теги исполнения.

---

## 3. Решённые архитектурные вопросы (по аналогии с Make.com Connector,
где применимо; иначе — обоснованное новое решение)

| # | Вопрос | Решение | Обоснование |
|---|---|---|---|
| 1 | BYOK или центральный брокер? | **BYOK**, как Make.com/DataForSEO/Magnific | n8n — платформа, где у пользователя своя инсталляция и свои данные; Imperal не может и не должно быть посредником для чужих workflow. |
| 2 | Сколько секретов? | **Три**: `n8n_base_url`, `n8n_api_key`, опционально `n8n_api_version` (дефолт `v1`) | Base URL нельзя угадать (см. 2.2) — в отличие от Make.com, где зона автоопределяется, здесь URL — обязательный явный ввод пользователя. |
| 3 | `write_mode`? | **`"both"`**, как у Make.com/DataForSEO | Та же причина: platform Secrets screen сам по себе не объяснит новому пользователю, что такое n8n API key и как его создать; `connect_n8n` валидирует явно (см. п.6) перед записью. |
| 4 | Активация/деактивация — на чём строить? | **`publish`/`unpublish`**, не `activate`/`deactivate` | `activate`/`deactivate` официально deprecated (issue #34771) — строить на устаревающем API значило бы закладывать долг с первого дня. |
| 5 | «Запустить workflow по ID» — обязательная фича первого среза? | **Да, но с graceful fallback-сообщением на 404** | Эндпоинт новый и не гарантирован на всех self-hosted версиях (см. 2.5) — инструмент должен явно объяснить это пользователю, а не выдать невнятную ошибку. |
| 6 | Bulk-операции по executions? | **Используем встроенный `POST /executions/stop`** (bulk по фильтру), не пишем свой цикл | n8n уже даёт это на своей стороне — переизобретать нет смысла и это надёжнее (транзакционность на стороне n8n). |
| 7 | Формат тела запроса для update workflow? | **`PUT` — полная замена**, не `PATCH` | В отличие от многих REST API, у n8n `PUT /workflows/{id}` заменяет всю сущность целиком — значит `update_workflow`-инструмент обязан сначала прочитать текущую workflow и замёржить изменения на своей стороне, иначе снесёт остальные поля. Прямая параллель тому, как `apply_bulk_*` инструменты WordPress Hub всегда перечитывают текущее состояние перед записью. |

---

## 4. Вопросы Владу — ОТВЕТЫ ПОЛУЧЕНЫ 2026-08-18 (закрыто)

1. **Название в Marketplace** → **«n8n»**, без слова Connector.
   Display_name = `n8n`, папка/app_id остаются `n8n-connector`.
2. **Приоритет self-hosted vs n8n Cloud в UX** → **Да, подтверждено**.
   Форма подключения (`connect_n8n` panel) сразу и явно спрашивает URL
   инстанса первым полем — никакой попытки авто-определения/зоны, как
   зафиксировано в п.2 таблицы решений раздела 3.
3. **Credentials API** → **«Дать полный доступ»**. Решение Влада:
   coннектор ПОЛУЧАЕТ доступ к credentials API n8n (не исключаем эту
   область). Это меняет п.3 раздела 3 (BYOK) — реализация обязана явно
   предупреждать в UI (settings-панели и/или в описании инструмента),
   что credentials — чувствительные данные нод, и что вызывающий несёт
   ответственность за то, кому/зачем даёт агенту это право. Не тихая
   фича — предупреждение обязательно на этапе дизайна панелей (Фаза 2).
4. **Scopes/403 предупреждение** → **«окей», подтверждено**.
   `n8n_client.py` обязан различать 401 (ключ в принципе не подошёл к
   этому base_url) от 403 (ключ подошёл, но не хватает scope) — прямая
   параллель фиксу, сделанному в `make_client.py`. При 403 сообщение
   должно явно называть недостающий scope, а не быть общей ошибкой.

---

## 5. Фаза 2 — Функциональный план (инструменты + данные)

Инструменты сгруппированы по тому же принципу, что и в Make.com Connector
(read-инструменты с `data_model=sdl.EntityList[...]`, write-инструменты с
явным подтверждением на рискованных шагах). Помечено **[confirmed]**, если
эндпоинт проверен по официальной докс/GitHub — включая два пункта, ранее
помеченных [TO VERIFY], закрытые 2026-08-18 перед началом Фазы 4:

- **Retry/stop execution** — ПОДТВЕРЖДЕНО. Официальное оглавление
  `docs.n8n.io/connect/n8n-api/execution` перечисляет ровно: Retrieve all
  executions, Retrieve an execution, Delete an execution, **Retry an
  execution**, **Stop an execution**, **Stop multiple executions**, Get
  execution tags, Update tags of an execution. Все идут в план ниже.
- **Credentials API** — ПОДТВЕРЖДЕНО, но с важным ограничением: n8n
  Public API поддерживает только **get credential schema, create,
  delete** — **НЕТ update/PATCH эндпоинта** для credentials (подтверждено
  community-постом n8n, 2024-12-30: «There is no modify/update endpoint»,
  и совпадает с OpenAPI-спекой `n8n-docs/api/v1/openapi.yml`). Значит в
  план НЕ включаю `update_n8n_credential` — только list/get-schema/create/
  delete. Чтобы «изменить» credential, пользователю нужно удалить и
  создать заново — это ограничение самого n8n, не моего дизайна, и должно
  быть явно объяснено в описании инструмента, а не молчаливым пробелом.

### 5.1 Подключение (BYOK)

- `connect_n8n(base_url, api_key)` [confirmed] — сохраняет URL + ключ,
  проверяет вызовом `GET /workflows?limit=1` перед записью. Различает
  401 (ключ не подошёл к этому base_url) от 403 (ключ подошёл, не хватает
  scope) — по решению п.4 раздела 4.
- `disconnect_n8n()` [confirmed] — удаляет секреты.

### 5.2 Workflows

- `list_workflows(active=None, tags=None, limit=50, cursor=None)` [confirmed]
  — `GET /workflows`, курсорная пагинация (`nextCursor`).
- `get_workflow(workflow_id)` [confirmed] — `GET /workflows/{id}`.
- `create_workflow(name, nodes, connections, ...)` [confirmed] — `POST /workflows`.
- `update_workflow(workflow_id, ...)` [confirmed] — `PUT /workflows/{id}`,
  **read-merge-write** обязателен (см. п.7 таблицы решений раздела 3 —
  `PUT` заменяет всю сущность).
- `delete_workflow(workflow_id)` [confirmed] — `DELETE /workflows/{id}`,
  требует явного подтверждения (`confirm=True` в UI-действии).
- `publish_workflow(workflow_id)` / `unpublish_workflow(workflow_id)`
  [confirmed] — **новый** API, НЕ `activate`/`deactivate` (тот deprecated,
  см. issue #34771 в разделе 2). Прямая замена `set_scenario_active` из
  Make.com Connector, но другим именем и другой семантикой на стороне n8n.
- `run_workflow(workflow_id)` [confirmed, но version-dependent] — `POST
  /workflows/{id}/execute`. Эндпоинт очень свежий (PR конца 2025) — на
  старых self-hosted инстансах может не существовать. Обработчик обязан
  ловить 404/501 на этом конкретном вызове и явно объяснять пользователю
  «этот n8n instance не поддерживает запуск по API — используй Webhook
  node в самом workflow», а не глотать как общую ошибку.

### 5.3 Executions

- `list_executions(workflow_id=None, status=None, limit=50, cursor=None)`
  [confirmed] — `GET /executions`, поддерживает redaction-флаги.
- `get_execution(execution_id, include_data=False)` [confirmed] —
  `GET /executions/{id}`.
- `delete_execution(execution_id)` [confirmed] — `DELETE /executions/{id}`.
- ~~`retry_execution`~~ / ~~`stop_execution`~~ [TO VERIFY] — я видела только
  поля `retryOf`/`retrySuccessId` в ответе `GET /executions`, НЕ нашла
  задокументированный `POST .../retry` или `.../stop` в Public API (в
  отличие от Make, где `retry_incomplete_execution` подтверждён явно).
  **Не включаю в Фазу 4**, пока не прочитаю `execution.md`/openapi.yml
  целиком и не найду точный путь — иначе рискую написать инструмент,
  который бьётся о несуществующий эндпоинт.

### 5.4 Tags

- `list_tags()`, `create_tag(name)`, `delete_tag(tag_id)` [confirmed] —
  `GET/POST/DELETE /tags`, аналог меток на workflow.

### 5.5 Credentials — полный доступ (решение п.3 раздела 4)

- `list_credentials()`, `get_credential(credential_id)`,
  `delete_credential(credential_id)` [TO VERIFY перед Фазой 4 — нужно
  прочитать `docs.n8n.io/connect/n8n-api` раздел credentials целиком,
  т.к. Public API исторически ограничивал credentials сильнее workflows
  (нет `GET` списка в некоторых версиях — нужно подтвердить, не
  предполагать]. Независимо от точного набора действий: каждый такой
  инструмент обязан в своём `description=` явно предупреждать, что
  credentials — это чувствительные данные авторизации нод к третьим
  сервисам, по решению из раздела 4 п.3.

### 5.6 Данные (sdl.Entity)

```python
class N8nWorkflow(sdl.Entity):      # id/title/status via base Entity
    active: bool = False
    tags: list[str] = []
    updated_at: str | None = None

class N8nExecution(sdl.Entity):
    workflow_id: str = ""
    status: str = ""               # success/error/running/waiting/canceled
    started_at: str | None = None
    stopped_at: str | None = None
```

---

## 6. Фаза 3 — Дизайн панелей (component sketch, PRE-PANEL CHECKLIST пройден)

Тот же паттерн слотов, что в Make.com Connector: один левый sidebar-панель
+ один center_overlay dialog для инструкции. Credentials — отдельная
секция с явным предупреждением (решение п.3 раздела 4), не подмешана в
общий список без разметки.

```python
# SKETCH — n8n_connect (slot="left")
# ui.Stack (v, gap=4)
#   ui.Header(text="n8n", level=2, subtitle=...)
#   [not connected]
#     ui.Card(title="Connect n8n", content=ui.Stack(v, gap=3, children=[
#       ui.Text("Self-hosted or n8n Cloud — paste your instance URL first."),
#       ui.Form(action="connect_n8n", children=[
#         ui.Input(param_name="base_url", placeholder="https://your-n8n-host or https://x.app.n8n.cloud"),
#         ui.Password(param_name="api_key", placeholder="n8n API key"),
#       ], submit_label="Verify and connect"),
#       ui.Button("How do I get an API key?", variant="ghost", size="sm",
#                 on_click=ui.Call("__panel__n8n_connect_help")),
#     ]))
#   [connected]
#     ui.Card(title="n8n", subtitle="Connected", content=ui.Stack(v, gap=2, children=[
#       ui.Text(base_url, variant="caption"),
#       ui.Button("Disconnect", variant="danger", size="sm", on_click=ui.Call("disconnect_n8n")),
#     ]))
#     ui.Divider()                                    ← НЕ Card, плоская секция (правило 4.1)
#     ui.Text("Your workflows", variant="heading")
#     ui.List(items=[ui.ListItem(...) for each workflow])   ← List уже разделяет строки, без своего Card
#     ui.Divider()
#     ui.Text("Recent executions", variant="heading")
#     ui.List(items=[ui.ListItem(...) for each execution])
#     ui.Divider()
#     ui.Alert(type="warning", title="Credentials access",
#              message="This connector can read/delete n8n credentials — "
#                      "the login data your workflows use for other services. "
#                      "Treat this like any other admin-level access.")
#     ui.Text("Credentials", variant="heading")
#     ui.List(items=[ui.ListItem(...) for each credential])

# SKETCH — n8n_connect_help (slot="center", center_overlay=True)
# ui.Dialog(title="How to get an n8n API key", content=ui.Stack(v, gap=3, children=[
#   ui.Text("1. Open Settings → n8n API in your instance."),
#   ui.Text("2. Click Create an API key (optionally set an expiry)."),
#   ui.Text("3. Copy it now -- n8n shows it once."),
#   ui.Divider(),
#   ui.Link(label="Open n8n's official documentation",
#           href="https://docs.n8n.io/connect/n8n-api/authentication"),
# ]), confirm_label="", cancel_label="Close")
```

**PRE-PANEL CHECKLIST пройден для обеих панелей:**
- `ui.Input`/`ui.Password` — без `label=`, без `type=` ✅
- `ui.Card` — везде `content=`, не `children=` ✅
- `ui.Form` — оба поля (`base_url`, `api_key`) пользователь вводит сам,
  ничего не пред-заполнено `value=` — не нужен store-обход ✅
- Списки workflows/executions/credentials — плоские `ui.List`/`ui.Divider`,
  НЕ обёрнуты в `ui.Card` целиком (правило раздела 4.1) ✅
- `n8n_connect_help` — `slot="center"` с `center_overlay=True` (иначе
  панель никогда не подтягивается — см. PRE-PANEL CHECKLIST) ✅
- `ui.Dialog` открыт тем же проверенным паттерном, что
  `make_connect_help`/`yt_connect_dialog`/`wp_ssh_dialog` ✅

**Статус Фазы 3:** sketch готов, но это ещё псевдокод в комментариях —
реальный `panels.py` не написан. Переход в Фазу 4 (код) требует твоего
явного согласия именно на этот шаг, по правилу перехода между фазами.

---

## 7. Правило дизайна сайдбара, зафиксированное Владом заодно с ответами
(обязательно для Фазы 3 — панели n8n Connector, применено с первого
черновика в разделе 6 выше)

**Карточки в левом (или соответствующем) сайдбаре рисуются СТЕКОМ с
разделителем между ними, БЕЗ оформления контейнера (без padding/фона/
рамки на каждом повторяющемся элементе).** Это не новая идея — это
повторение правила, которое уже приходилось чинить как баг в Make.com
Connector (см. запись в журнале UI_INTERFACE_STANDARD.md 2026-08-18):
повторяющиеся секции списка (team picker, список сценариев/workflow,
статус вебхука) — это плоский `Stack` + `Divider()` между элементами;
настоящая `Card` с оформлением используется ТОЛЬКО там, где виджет один
и не повторяется (например, единый блок подключения/статуса), а не как
обёртка каждого элемента списка. При проектировании панелей n8n
(список workflows, список executions, список tags) в Фазе 2 это
применяется с первого черновика — не постфактум-фикс, как это было с
Make.com.

---

## 8. Что переиспользуется из Make.com Connector один в один

- Общая структура файлов: `app.py` (secrets/lifecycle), `<name>_client.py`
  (HTTP-клиент), `schemas.py`, `handlers.py`, `panels.py`.
- Паттерн подтверждения перед потенциально разрушительными действиями
  (delete workflow/execution, stop-массово) — confirmation gate, как у
  `run_scenario`/`bulk_delete_connections` в Make.com Connector.
- Обязательный проход по `CLAUDE.md` 4-фазному процессу и
  `UI_INTERFACE_STANDARD.md` (единая кнопка "App settings" в сайдбаре,
  единый settings-центр) — это применяется к КАЖДОМУ приложению с UI,
  без исключений, независимо от того, что это второе приложение того же
  класса.

---

## 9. Журнал проверок дублей

| Дата | Запрос в `search_marketplace` | Результат |
|---|---|---|
| 2026-08-18 | «n8n» | 0 совпадений |
| 2026-08-18 | «workflow automation» | Совпадений по n8n/автоматизации workflow нет (найдены Notes/Tasks/Mail — не пересекаются по домену) |

**Вывод:** дублей нет, путь свободен для Фазы 2 (дизайн) после ответа
Влада на открытые вопросы раздела 4.

---

## 10. Источники (для последующей сверки при кодировании, не полагаться
на память)

- `docs.n8n.io/connect/n8n-api/authentication` — auth, создание ключа.
- `docs.n8n.io/connect/n8n-api/execution` — полный список executions
  эндпоинтов и их тел запроса/ответа.
- `docs.n8n.io/connect/n8n-api` — общий обзор Public API.
- GitHub `n8n-io/n8n` issue **#34771** — deprecation activate/deactivate.
- GitHub `n8n-io/n8n` issue **#34745** — добавление publish/unpublish.
- GitHub `n8n-io/n8n` PR **#23435**, **#20234** — добавление
  `POST /workflows/{id}/execute`.
- n8n Community forum, **«Executing a workflow via API call (without
  webhook or CLI command)»** (2025-10-28) — подтверждение отсутствия
  такого эндпоинта ДО появления PR выше.
