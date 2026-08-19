# Post-Audit Log — n8n Connector

Формат и правила ведения: см. `/Users/vladivanco/Documents/Imperal OS/POST_AUDIT_LOG_STANDARD.md`.
Новые записи добавляются СВЕРХУ.

---

## 2026-08-19 — Plausible Scenario Testing (PST), первый прогон — 2 реальных бага найдены, не пойманы статическим пост-аудитом ниже

**Что проверялось:** реальное поведение кода через `imperal_sdk.testing.MockContext`
+ `MockHTTP` — не статическая структура файлов, а фактическое исполнение
`handlers.py`/`n8n_client.py` по 27 сценариям вдоль 5 обязательных веток
(happy/error/blocked/recovery/adversarial), см. полный журнал и метод в
`SCENARIO_TESTS.md` этого приложения.

**Почему через MockContext, а не живой n8n:** пользователь не подключил
собственный n8n-инстанс (`get_n8n_connection` → `connected: false`);
Docker недоступен в среде выполнения; `npx n8n` не устанавливается за
разумное время. MockContext + MockHTTP — следующий по строгости честный
вариант: реальный код продукта, тестовый сетевой двойник вместо чужого
живого сервера.

### Находки (обе исправлены)

1. **`update_n8n_variable`** — `handlers.py` вызывал `nc.update_variable`
   с 5 позиционными аргументами на сигнатуру, требующую 6 обязательных
   (`ctx, base_url, api_key, variable_id, key, value, project_id=""`);
   `params.value` подставлялся на место `key`, а обязательный `value`
   не передавался вовсе — гарантированный `TypeError` при первом реальном
   вызове. Подтверждено дополнительной AST-сверкой всех вызовов `nc.*`
   против сигнатур клиента — единственное совпадение такого рода.
2. **`run_n8n_workflow` и `get_n8n_execution`** — оба вызывали
   `ActionResult.success(..., data_extra={...})`; реальный SDK
   (`imperal_sdk.types.action_result.ActionResult.success`) такого
   параметра не имеет — гарантированный `TypeError` при каждом реальном
   вызове, включая самую частую операцию "запустить workflow".

**Значение находки:** оба бага были в коде, который уже прошёл предыдущий
статический пост-аудит (запись ниже) и уже был передеплоен с
выставленными ценами (`PRICING_HISTORY.md`) — статический аудит по
конструкции сверяет структуру (manifest↔schemas↔handler↔client), а не
фактическое число аргументов при вызове или существование kwargs в
установленной версии SDK. Это ровно тот класс дефектов, ради которого
введён обязательный PST-этап (см. `Docs/session-notes/
SCENARIO_TESTING_STANDARD.md`) — прямое, живое подтверждение того, что
пост-аудит один недостаточен и нужен ещё этот шаг перед публикацией/
после каждого значимого изменения кода.

**Действие:** оба бага исправлены в `handlers.py`/`schemas.py`; приложение
передеплоено. Полный список из 27 сценариев, метод и обоснование — в
`SCENARIO_TESTS.md`.

---

## 2026-08-19 — Сквозной пост-аудит + исправление системного double-prompt бага (7 функций)

**Что проверялось:** py_compile всех 7 модулей; количество `@chat.function`
(48, совпадает с манифестом); классификация `action_type` каждой функции;
double-prompt антипаттерн (ручное поле `confirm: bool` в Params-классе +
ручной гейт `if not params.confirm: return error(...)` рядом с
`action_type` слабее `destructive`) — по всем 6 `delete_n8n_*` функциям И
по `run_n8n_workflow`; отсутствие тестовой директории у этого приложения
(подтверждено — тестов для n8n Connector нет вообще, ни в `tests/`, ни
где-либо ещё в дереве).

**Метод:** распечатала полный список `name -> action_type`; grep по всем
`*.py` на `confirm` нашёл совпадения в 6 файлах; прочитала КАЖДЫЙ из 6
`delete_n8n_*` обработчиков и их Params-классы целиком — все шесть
оказались идентичным паттерном: `action_type="write"` + ручное поле
`confirm: bool = Field(False, ...)` + ручная проверка
`if not params.confirm: return ActionResult.error(..., code="N8N_CONFIRM_REQUIRED")`.
Также нашла тот же паттерн у `run_n8n_workflow` — не `delete_*` по имени,
но с тем же ручным confirm-гейтом. Сравнила с уже установленным в этой
серии аудитов эталоном (`delete_message` в Slack Connector,
`run_scenario` в Make.com Connector), чтобы решить правильную
классификацию каждой.

### Находки

**Системный баг — 6 из 6 функций `delete_n8n_*` неправильно
классифицированы, плюс `run_n8n_workflow`.** Это НЕ единичная ошибка, а
паттерн, повторённый разработчиком приложения ровно 7 раз подряд:
`action_type="write"` + собственноручно написанный `confirm`-гейт вместо
использования платформенного `action_type="destructive"`.

1. `delete_n8n_workflow` — "Cannot be undone." — should be destructive.
2. `delete_n8n_execution` — "Permanently delete... " (execution history) — destructive.
3. `delete_n8n_credential` — "Permanently delete... also the only way to
   'change' one" — destructive.
4. `delete_n8n_tag` — "Permanently delete..." — destructive.
5. `delete_n8n_variable` — "Permanently delete..." — destructive.
6. `delete_n8n_user` — "Permanently delete..." — destructive.
7. `run_n8n_workflow` — "there is no dry-run or undo" — тот же профиль
   риска, что у `run_scenario` в Make.com Connector (уже правильно
   `destructive` там) — приведено в соответствие с этим эталоном.

Все семь описаний в манифесте буквально констатируют невозвратность
("Permanently", "Cannot be undone", "no dry-run or undo") — что само по
себе однозначный сигнал для `destructive`, а не `write`.

### Что сделано

1. `schemas.py`: удалено поле `confirm: bool` из всех 7 Params-классов
   (`DeleteWorkflowParams`, `DeleteExecutionParams`,
   `DeleteCredentialParams`, `DeleteTagParams`, `DeleteVariableParams`,
   `DeleteUserParams`, `RunWorkflowParams`).
2. `handlers.py`: во всех 7 функциях `action_type` изменён `write` →
   `destructive`; убран ручной `if not params.confirm: ...` гейт; docstring
   каждой функции дополнен объяснением, почему `destructive`, а не
   `write` (по образцу `run_scenario` из Make.com Connector).
3. `imperal.json`: синхронизирован программно — `action_type` всех 7
   функций → `destructive`, поле `confirm` удалено из `properties` и
   `required` каждой схемы. Валидность JSON и py_compile подтверждены.
4. Итоговая раскладка `action_type` после исправления:
   `{write: 23, read: 18, destructive: 7}` (было `{write: 30, read: 18,
   destructive: 0}` — то есть до этого аудита в приложении не было ВООБЩЕ
   ни одной `destructive`-функции, при шести операциях безвозвратного
   удаления и одном безвозвратном запуске).
5. **Тестовый прогон не проводился — у приложения нет тестовой
   директории вообще** (ни `tests/`, ни файлов `test_*.py` где-либо в
   дереве). Это отдельный пробел, зафиксированный здесь как факт, а не
   как "не сработавший тест": в этом приложении просто нет
   автоматизированных тестов для проверки регрессии на дату аудита.

### Итог

Проверка кода — 7/7 найденных проблем исправлено (0 → 7 `destructive`
операций правильно классифицированы, double-prompt убран). Проверка
регрессии тестами — невозможна: тестов нет. Рекомендация на будущее:
добавить `tests/` с покрытием хотя бы для всех `destructive`-функций,
аналогично остальным приложениям в портфеле.

**Статус: FIXED (7 bugs), NO TEST COVERAGE TO VERIFY AGAINST.**
