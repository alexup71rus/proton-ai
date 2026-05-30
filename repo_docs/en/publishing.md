# Publishing Checklist

Use this checklist before pushing a public release.

## Repository

- Public name: `Proton AI`
- Repository slug: `proton-ai`
- Internal Python import name: `protonx`
- License: MIT

The internal package name can remain `protonx` until a Python distribution is introduced.

## Local State

Do not commit generated local state:

- `data/train/*`
- `data/weights/*`
- `data/tokenizers/*`
- `data/tools/*`
- `data/logs/*`
- `data/workspace/settings.json`

Commit only examples, `.gitkeep` files, docs, source code, and tests.

## Environment Names

Use public `PROTON_AI_*` variables in docs and deployment scripts. `PROTONX_*` remains a compatibility alias.

## Build

```bash
python -m pytest --import-mode=importlib service/tests web_backend/tests -q
(cd web_ui && npm run build)
git diff --check
```

## Runtime

Production packaging is not defined yet. For now, publish as a local-first developer project:

- run model service with `uvicorn main:app` from `service/`;
- run UI backend with `uvicorn web_backend.app:app`;
- build or serve the Vite web UI from `web_ui/`;
- mount or persist `data/` outside ephemeral containers if using containers later.
