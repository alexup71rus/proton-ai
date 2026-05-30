# Proton AI Guides

These guides cover the local Proton AI workflow: model service, UI backend, web UI, tools registry, datasets, training, testing, and logs.

- [Getting started](getting-started.md)
- [Workflow](workflow.md)
- [Tools registry](tools-registry.md)
- [Training and testing](training-and-testing.md)
- [Publishing checklist](publishing.md)

Component map:

```text
service/      FastAPI model service
web_backend/  FastAPI UI backend
web_ui/       React/Vite web UI
data/         local tools, datasets, weights, tokenizers, logs
```

The retired `web/` Streamlit UI is kept for compatibility. New work should use `web_ui`.
