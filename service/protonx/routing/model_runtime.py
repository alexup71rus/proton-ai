import json
import hashlib
from pathlib import Path

import sentencepiece as spm
import torch

from protonx.contracts import build_fallback_payload
from protonx.model_contract import PROMPT_FORMAT_VERSION
from protonx.training.format import decode_generated_continuation
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

    def _fallback(self) -> str:
        return json.dumps(build_fallback_payload())

    def _clear_cached_runtime(self) -> None:
        self._artifact_signature = None
        self._config = None
        self._model = None
        self._tokenizer = None

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

    def generate(self, prompt: dict) -> str:
        runtime = self._get_runtime()
        if runtime is None:
            return self._fallback()

        config, model, tokenizer = runtime
        prompt_text = serialize_inference_prompt(prompt)
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

        candidate = decode_generated_continuation(
            tokenizer,
            generated,
            len(token_ids),
            tokenizer.eos_id(),
        )
        return candidate or self._fallback()
