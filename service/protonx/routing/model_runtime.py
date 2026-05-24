import json
import hashlib
from pathlib import Path

import sentencepiece as spm
import torch
import torch.nn.functional as F

from protonx.contracts import build_fallback_payload
from protonx.model_contract import PROMPT_FORMAT_VERSION
from protonx.training.format import decode_generated_continuation
from protonx.training.format import OUTPUT_FORMAT_CALL
from protonx.training.format import OUTPUT_FORMAT_JSON
from protonx.training.format import render_model_output
from protonx.training.format import serialize_call_payload
from protonx.training.format import serialize_inference_prompt
from protonx.training.model import TinyRouterConfig, TinyRouterModel


class ModelRuntime:
    def __init__(self, weights_path: Path, tokenizer_path: Path):
        self.weights_path = weights_path
        self.tokenizer_path = tokenizer_path
        self._artifact_signature: tuple[int, int, int, int] | None = None
        self._config: TinyRouterConfig | None = None
        self._model: TinyRouterModel | None = None
        self._tokenizer: spm.SentencePieceProcessor | None = None
        self._output_format: str = OUTPUT_FORMAT_JSON

    def _fallback(self) -> str:
        return json.dumps(build_fallback_payload())

    def _clear_cached_runtime(self) -> None:
        self._artifact_signature = None
        self._config = None
        self._model = None
        self._tokenizer = None
        self._output_format = OUTPUT_FORMAT_JSON

    def _artifacts_signature(self) -> tuple[int, int, int, int] | None:
        if not self.weights_path.exists() or not self.tokenizer_path.exists():
            return None
        weights_stat = self.weights_path.stat()
        tokenizer_stat = self.tokenizer_path.stat()
        return (
            weights_stat.st_mtime_ns,
            weights_stat.st_size,
            tokenizer_stat.st_mtime_ns,
            tokenizer_stat.st_size,
        )

    def _tokenizer_sha1(self) -> str:
        return hashlib.sha1(self.tokenizer_path.read_bytes()).hexdigest()

    def _load_runtime_artifacts(
        self,
    ) -> tuple[TinyRouterConfig, TinyRouterModel, spm.SentencePieceProcessor] | None:
        checkpoint = torch.load(self.weights_path, map_location="cpu")
        if checkpoint.get("prompt_format") != PROMPT_FORMAT_VERSION:
            return None

        expected_tokenizer_sha1 = checkpoint.get("tokenizer_sha1")
        if expected_tokenizer_sha1 and expected_tokenizer_sha1 != self._tokenizer_sha1():
            return None

        config = TinyRouterConfig(**checkpoint["config"])
        model = TinyRouterModel(config)
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        self._output_format = str(checkpoint.get("output_format") or OUTPUT_FORMAT_JSON)

        tokenizer = spm.SentencePieceProcessor(model_file=str(self.tokenizer_path))
        return config, model, tokenizer

    def _get_runtime(
        self,
    ) -> tuple[TinyRouterConfig, TinyRouterModel, spm.SentencePieceProcessor] | None:
        signature = self._artifacts_signature()
        if signature is None:
            self._clear_cached_runtime()
            return None

        if (
            self._artifact_signature == signature
            and self._config is not None
            and self._model is not None
            and self._tokenizer is not None
        ):
            return self._config, self._model, self._tokenizer

        artifacts = self._load_runtime_artifacts()
        if artifacts is None:
            self._clear_cached_runtime()
            return None

        self._config, self._model, self._tokenizer = artifacts
        self._artifact_signature = signature
        return artifacts

    def _default_call_arguments(self, tool: dict) -> dict[str, str]:
        raw_args = tool.get("args")
        if not isinstance(raw_args, dict):
            return {}

        arguments: dict[str, str] = {}
        for field_name, spec in raw_args.items():
            if isinstance(spec, list) and spec:
                arguments[str(field_name)] = str(spec[0])
                continue
            arguments[str(field_name)] = str(field_name).replace("_", " ")
        return arguments

    def _score_call_candidate(
        self,
        *,
        config: TinyRouterConfig,
        model: TinyRouterModel,
        tokenizer: spm.SentencePieceProcessor,
        prompt_ids: list[int],
        candidate_text: str,
    ) -> float:
        candidate_ids = tokenizer.encode(candidate_text, out_type=int)
        full_ids = [*prompt_ids, *candidate_ids]
        eos_id = tokenizer.eos_id()
        if eos_id >= 0:
            full_ids.append(eos_id)

        if len(full_ids) > config.max_seq_len:
            available_prompt_len = config.max_seq_len - len(candidate_ids) - (1 if eos_id >= 0 else 0)
            if available_prompt_len <= 1:
                return float("inf")
            full_ids = [*prompt_ids[:available_prompt_len], *candidate_ids]
            if eos_id >= 0:
                full_ids.append(eos_id)

        input_ids = torch.tensor([full_ids[:-1]], dtype=torch.long)
        labels = torch.tensor(full_ids[1:], dtype=torch.long)
        candidate_start = max(len(full_ids) - len(candidate_ids) - (1 if eos_id >= 0 else 0) - 1, 0)
        with torch.no_grad():
            logits = model(input_ids)[0]
        candidate_logits = logits[candidate_start:]
        candidate_labels = labels[candidate_start:]
        losses = F.cross_entropy(
            candidate_logits,
            candidate_labels,
            reduction="none",
        )
        return float(losses.mean().item())

    def _generate_scored_call(
        self,
        *,
        config: TinyRouterConfig,
        model: TinyRouterModel,
        tokenizer: spm.SentencePieceProcessor,
        prompt: dict,
        prompt_text: str,
    ) -> str:
        prompt_ids = tokenizer.encode(prompt_text, out_type=int)
        best_score = float("inf")
        best_payload: dict | None = None

        for tool in prompt.get("tools", []):
            tool_name = str(tool.get("name") or "")
            if not tool_name:
                continue
            payload = {
                "tool_calls": [
                    {
                        "name": tool_name,
                        "arguments": self._default_call_arguments(tool),
                    }
                ]
            }
            candidate_text = serialize_call_payload(payload)
            score = self._score_call_candidate(
                config=config,
                model=model,
                tokenizer=tokenizer,
                prompt_ids=prompt_ids,
                candidate_text=candidate_text,
            )
            if score < best_score:
                best_score = score
                best_payload = payload

        if best_payload is None:
            return self._fallback()
        return json.dumps(best_payload, ensure_ascii=False, separators=(",", ":"))

    def generate(self, prompt: dict) -> str:
        runtime = self._get_runtime()
        if runtime is None:
            return self._fallback()

        config, model, tokenizer = runtime
        prompt_text = serialize_inference_prompt(prompt)
        if self._output_format == OUTPUT_FORMAT_CALL:
            return self._generate_scored_call(
                config=config,
                model=model,
                tokenizer=tokenizer,
                prompt=prompt,
                prompt_text=prompt_text,
            )

        token_ids = tokenizer.encode(prompt_text, out_type=int)[: config.max_seq_len]
        generated = list(token_ids)

        for _ in range(64):
            input_ids = torch.tensor(
                [generated[-config.max_seq_len :]],
                dtype=torch.long,
            )
            with torch.no_grad():
                logits = model(input_ids)
            next_token = int(torch.argmax(logits[0, -1]).item())
            generated.append(next_token)
            if next_token == tokenizer.eos_id():
                break

        raw_candidate = decode_generated_continuation(
            tokenizer,
            generated,
            len(token_ids),
            tokenizer.eos_id(),
        )
        candidate = render_model_output(raw_candidate, self._output_format)
        return candidate or self._fallback()
