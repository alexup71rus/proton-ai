# Концепция Proton AI

Proton AI - AI constructor для специализированных локальных automation models. Пользователь задает разрешенные tools, собирает dataset, обучает маленькую router model и оставляет execution под явным локальным контролем.

Ближайшая продуктовая аналогия - Shortcuts-style automation, где модель отвечает за выбор действия. Пользователь пишет обычный запрос, а обученная маленькая модель выбирает подходящий tool и arguments.

English version: [PROJECT_CONCEPT.md](PROJECT_CONCEPT.md)

## Текущие границы

Версия 1 не является chat assistant. Модель не должна писать свободные ответы, придумывать tools или исполнять код. Она возвращает один строгий JSON shape:

```json
{"tool_calls":[{"name":"tool_name","arguments":{}}]}
```

Дальше output проходит validation. Только validated output может попасть в executor layer.

Product loop:

```text
define tools -> build dataset -> train tiny router -> test -> inspect logs -> improve dataset
```

## Пользовательский flow

1. Клонировать `proton-ai`.
2. Описать tools: `name`, `tags`, argument schema и executor path.
3. Сгенерировать bootstrap dataset из tools registry.
4. Добавить реальные examples, если bootstrap dataset плохо покрывает пользовательский язык.
5. Обучить маленькую router model.
6. Проверить запросы в web UI.
7. Использовать fallback/error logs для улучшения dataset.

Результат: локальная модель, которая выбирает только из разрешенных tools пользователя.

## Зачем нужны structured arguments

Самый простой вариант - создать отдельный tool под каждую комбинацию действия:

```text
turn_light_on
turn_light_off
set_light_warm
set_light_cold
set_kitchen_light_warm
```

Так модели проще, но registry быстро разрастается. Похожие действия дублируются, а новые сценарии требуют все больше одноцелевых tools.

Целевой контракт:

```text
tool name + structured arguments
```

Пример:

```json
{"tool_calls":[{"name":"set_light","arguments":{"room":"kitchen","temperature":"warm"}}]}
```

Routing task становится сложнее, но tools registry остается ближе к реальным API и scripts.

## Safety boundary

Tools описываются явно. Они приходят от пользователя или trusted authoring layer. Модель видит routing metadata, но не видит executor code и не может создавать новые executor paths.

Граница ответственности:

- model выбирает intent и arguments;
- validator проверяет contract, tool membership, required fields и enum values;
- executor запускает trusted local code;
- logs показывают, где модель ошиблась.

Эта граница позволяет использовать Proton AI как automation constructor, не превращая runtime model в общего autonomous agent.

## Дальнейшее направление

Текущая архитектура оставляет место для более сильного authoring layer:

- большая модель помогает писать tools и executor scripts;
- большая модель расширяет datasets реалистичными формулировками;
- маленькая локальная модель остается runtime router;
- reusable tool packs можно распространять отдельно;
- multi-step workflows можно добавлять после надежного single-step routing.

Главное правило остается прежним: trained runtime model выбирает из разрешенных tools и возвращает validated structured output.
