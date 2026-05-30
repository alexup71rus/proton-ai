# Proton AI Project Concept

Proton AI is an AI constructor for specialized local automation models. The user defines the allowed tools, builds a dataset, trains a small router model, and keeps execution under explicit local control.

The closest product analogy is Shortcuts-style automation with a model in the selection step. Instead of asking the user to pick the exact action, Proton AI lets the user write a normal request and trains a small model to choose the matching tool and arguments.

Russian version: [PROJECT_CONCEPT.ru.md](PROJECT_CONCEPT.ru.md)

## Current Scope

Version 1 is not a chat assistant. The model must not produce free-form answers, invent tools, or execute code. It returns one strict JSON shape:

```json
{"tool_calls":[{"name":"tool_name","arguments":{}}]}
```

The output then goes through validation. Only validated output can reach the executor layer.

Product loop:

```text
define tools -> build dataset -> train tiny router -> test -> inspect logs -> improve dataset
```

## User Flow

1. Clone `proton-ai`.
2. Define tools with `name`, `tags`, argument schema, and executor path.
3. Generate a bootstrap dataset from the tools registry.
4. Add real examples when the bootstrap dataset misses user language.
5. Train a small router model.
6. Test requests in the web UI.
7. Use fallback/error logs to improve the dataset.

Result: a local model that chooses only from the user's allowed tools.

## Why Structured Arguments Matter

The simplest implementation would create a separate tool for each action variant:

```text
turn_light_on
turn_light_off
set_light_warm
set_light_cold
set_kitchen_light_warm
```

That reduces model difficulty, but it does not scale. The registry grows quickly, similar actions are duplicated, and new scenarios require more single-purpose tools.

The target contract is:

```text
tool name + structured arguments
```

Example:

```json
{"tool_calls":[{"name":"set_light","arguments":{"room":"kitchen","temperature":"warm"}}]}
```

This makes the routing task harder, but the tools registry stays closer to real APIs and scripts.

## Safety Boundary

Tools are explicit. They come from the user or a trusted authoring layer. The model sees routing metadata, but it does not see executor code and cannot create new executor paths.

The boundary is:

- model selects intent and arguments;
- validator checks contract, tool membership, required fields, and enum values;
- executor runs trusted local code;
- logs show where the model failed.

This boundary is the main reason Proton AI can be useful as an automation constructor without turning the runtime model into a general autonomous agent.

## Future Direction

The current architecture leaves room for stronger authoring support:

- a larger model can help write tools and executor scripts;
- a larger model can expand datasets with realistic phrasing;
- the small local model remains the runtime router;
- reusable tool packs can be shared;
- multi-step workflows can be added after single-step routing is reliable.

The core rule stays the same: the trained runtime model chooses from allowed tools and returns validated structured output.
