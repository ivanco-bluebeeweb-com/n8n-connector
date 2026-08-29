# n8n Connector — UI component plan

Источники: `Docs/session-notes/UI_COMPONENT_VOCABULARY.md`, `UI_INTERFACE_STANDARD.md`,
`concepts/panels.md`. Основано на функционале `n8n-connector`.

## 1. Компоненты

| Экран | Примитивы | Почему именно эти |
|---|---|---|
| Sidebar (left) | `ui.Column`(align="start") + `ui.Text`(instance URL) + `ui.Divider` + navigation `ui.ListItem`(Workflows/Executions/Credentials) + `ui.Button`("App settings") | Без карточек по стандарту. |
| Workflow List (center, `center_overlay=True`) | `ui.Stats`(Active/Inactive/Failed executions today) + `ui.DataTable`(name, active Toggle-колонка через `editable=True, edit_type="toggle"`, tags, updated; sortable) | Активация/деактивация workflow прямо из таблицы — DataTable с editable toggle-колонкой закрывает этот сценарий без отдельной формы. |
| Workflow Detail | Back-button + `ui.KeyValue`(node count/trigger type/active) + `ui.Graph`(nodes=узлы workflow, edges=connections — реальная схема потока) + `ui.Row`(Button "Run Now", "Activate/Deactivate") | `Graph` (Cytoscape.js) — единственный примитив в SDK, подходящий для отображения графа узлов и связей workflow n8n. |
| Execution List | `ui.DataTable`(workflow, status Badge success/error/running, started_at, duration; sortable) | Табличная история запусков с быстрой фильтрацией по статусу. |
| Execution Detail | Back-button + `ui.KeyValue`(workflow/status/duration) + `ui.Code`(language="json", content=run data, readonly) + `ui.Button`("Retry") | `Code` с `language="json"` — подходящий примитив для просмотра сырых входных/выходных данных выполнения. |
| Credentials List | `ui.DataTable`(name, type; без значений — секреты никогда не показываются) + `ui.Button`("Добавить credential") | Список без утечки секретов — стандартная безопасность. |
| Variables Manager | `ui.DataTable`(key, value) + `ui.Dialog`(форма: `ui.Input`(key) + `ui.Input`(value)) | Простой список инстанс-переменных n8n (не секретных). |
| Security Audit Report | `ui.Alert`(variant="warn"/"error" по каждой найденной проблеме) + `ui.List`(рекомендации) | `Alert` — прямое попадание для отображения найденных рисков аудита. |
| App Settings | `ui.Accordion`([Connections+Disconnect, Base URL/API Key]) | Централизованные настройки по стандарту. |

## 2. User flow (валидно по panel lifecycle)

1. **SESSION INIT** → `__panel__n8n_sidebar` рендерит instance URL + разделы,
   `auto_action` открывает Workflow List.
2. Workflow List: DataTable с editable toggle "Active" → `on_cell_edit` вызывает
   `publish_n8n_workflow`/`unpublish_n8n_workflow` напрямую, без модалки (обратимое
   действие) → `refresh_panels=["n8n_center"]`.
3. Клик на строку (не на toggle) → `ui.Call(workflow_id=...)` → Workflow Detail
   на том же center handler — рендерит `Graph` из узлов/связей workflow.
4. "Run Now" — прямой `ui.Call`, без Dialog (запуск — не деструктивен).
5. Execution List: клик на строку → Execution Detail → `Code`(json) показывает
   сырые данные ранa; "Retry" — прямой Call.
6. Credentials List: только просмотр метаданных — форма создания открывает
   `Dialog` со схемой полей, специфичной для типа credential (динамическая форма
   на основе `get_n8n_credential_schema`).

## 3. Экраны (конкретно, по файлам `panels.py`)

1. `n8n_sidebar` (`slot="left"`) — навигация, App settings button.
2. `n8n_center` (`slot="center"`, `center_overlay=True`) — параметризован `view`
   (workflows/workflow_detail/executions/execution_detail/credentials/variables/audit).
3. `n8n_settings` (`slot="center"`, `panels_settings.py`) — Accordion с
   Connections/Base URL/API Key.
