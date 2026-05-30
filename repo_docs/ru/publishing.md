# Publishing Checklist

Используй этот checklist перед public release.

## Repository

- Public name: `Proton AI`
- Repository slug: `proton-ai`
- Internal Python import name: `protonx`
- License: MIT

Internal package name можно оставить `protonx`, пока нет отдельной Python distribution.

## Local state

Не коммить generated local state:

- `data/train/*`
- `data/weights/*`
- `data/tokenizers/*`
- `data/tools/*`
- `data/logs/*`
- `data/workspace/settings.json`

В git должны попадать source code, tests, docs, examples и `.gitkeep`.

## Environment names

В docs и deploy scripts используй публичные `PROTON_AI_*` variables. `PROTONX_*` остается compatibility alias.

## Build

```bash
python -m pytest --import-mode=importlib service/tests web_backend/tests -q
(cd web_ui && npm run build)
git diff --check
```

## Runtime

Production packaging пока не описан. Сейчас проект публикуется как local-first developer project:

- model service запускается через `uvicorn main:app` из `service/`;
- UI backend запускается через `uvicorn web_backend.app:app`;
- Vite web UI собирается или запускается из `web_ui/`;
- `data/` нужно сохранять вне ephemeral containers, если позже появится container deployment.
