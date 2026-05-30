# Гайды Proton AI

Эти документы описывают локальный workflow Proton AI: model service, UI backend, web UI, tools registry, datasets, training, testing и logs.

- [Быстрый старт](getting-started.md)
- [Workflow](workflow.md)
- [Tools registry](tools-registry.md)
- [Training и testing](training-and-testing.md)
- [Publishing checklist](publishing.md)

Карта компонентов:

```text
service/      FastAPI model service
web_backend/  FastAPI UI backend
web_ui/       React/Vite web UI
data/         local tools, datasets, weights, tokenizers, logs
```

Retired `web/` Streamlit UI оставлен для совместимости. Для новой работы используется `web_ui`.
