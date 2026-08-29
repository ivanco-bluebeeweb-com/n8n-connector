# n8n Connector — идеальный первый запуск

Источник: `ONBOARDING_FIRST_LAUNCH_STANDARD.md`. Целевой пользователь: automation/ops-
инженер на self-hosted или n8n Cloud инстансе.

## 1. Credential type
Self-hosted-capable: base_url (SSRF-защищённый, поддерживает и self-hosted, и n8n Cloud
поддомены) + собственный API key.

## 2. Идеальный флоу
1. **Первое открытие** — `Empty` с выбором self-hosted/Cloud ДО формы (влияет на
   placeholder base_url — n8n Cloud формат `*.app.n8n.cloud` явно отличается от
   произвольного self-hosted URL) + ссылка на генерацию API key в самом n8n
   (Settings > API).
2. **Форма** — base_url (с адаптивным placeholder) + api_key (password-type).
3. **После успеха** — список workflows со статусом активности сразу — actionable.
4. **Multi-project (Enterprise)** — если инстанс поддерживает Enterprise projects —
   идеально: селектор проекта, если он есть, аналогично Workato.
5. **Ошибка "SSL certificate verify failed" (self-hosted)** — аналогично Ansible/GitLab
   self-hosted паттерну — конкретное объяснение отдельно от обычного network error.

## 3. Разница с реализацией сейчас
См. `UI_COMPONENT_PLAN.md` §0.
