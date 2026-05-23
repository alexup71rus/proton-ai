# Proton-X

Платформа для одновременного обучения и тестирования языковых моделей.

## Архитектура

Два независимых сервиса:

- **`service/`** — LLM-сервис (FastAPI). Инференс, управление моделями, обучение.
- **`web/`** — Веб-интерфейс (Streamlit). Чат, управление датасетами, графики обучения.

## Режимы

| Режим | Описание |
|-------|----------|
| **Обучение** | Загрузка датасетов, запуск обучения, прогресс с графиками |
| **Чат** | Общение с моделью, история, настройки (temperature, top_k) |

## Структура проекта

```
proton-x/
├── service/          # LLM-сервис (FastAPI)
│   ├── main.py
│   └── requirements.txt
├── web/              # Веб-интерфейс (Streamlit)
│   ├── app.py
│   └── requirements.txt
├── data/             # Данные (не в git)
│   ├── train/        # Датасеты для обучения
│   ├── weights/      # Веса моделей
│   └── models/       # Готовые модели
├── docs/             # Документация и планы
└── README.md
```

## Быстрый старт

### 1. Установка зависимостей

```bash
# LLM-сервис
cd service && pip install -r requirements.txt

# Веб-интерфейс
cd web && pip install -r requirements.txt
```

### 2. Запуск

```bash
# Терминал 1 — LLM-сервис
cd service && uvicorn main:app --reload --port 8000

# Терминал 2 — Веб-интерфейс
cd web && streamlit run app.py --server.port 8501
```

### 3. Проверка

- LLM-сервис: http://localhost:8000/health
- Веб-интерфейс: http://localhost:8501

## Стек

- Python 3.11+
- FastAPI + Uvicorn
- Streamlit
- PyTorch
- SentencePiece (токенизатор, BPE/unigram, совместимость с Gemma)
- Transformers, Datasets, Accelerate, TRL
- Safetensors, Einops

## Архитектура модели

Gemma-стиль, ~30-80M параметров:

```
Embedding → RoPE → 8 Transformer Blocks → RMSNorm → Linear
```

Параметры: `layers=8, hidden=512, heads=8, context=512, vocab=32000`
