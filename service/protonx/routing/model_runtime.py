import json
from pathlib import Path

import sentencepiece as spm
import torch

from protonx.contracts import build_fallback_payload
from protonx.training.format import serialize_inference_prompt
from protonx.training.model import TinyRouterConfig, TinyRouterModel


class ModelRuntime:
    def __init__(self, weights_path: Path, tokenizer_path: Path):
        self.weights_path = weights_path
        self.tokenizer_path = tokenizer_path

    def _fallback(self, answer_allowed: bool) -> str:
        return json.dumps(build_fallback_payload(answer_allowed))

    def generate(self, prompt: dict) -> str:
        answer_allowed = prompt["system"].get("answer_allowed", True)
        if not self.weights_path.exists() or not self.tokenizer_path.exists():
            return self._fallback(answer_allowed)

        checkpoint = torch.load(self.weights_path, map_location="cpu")
        config = TinyRouterConfig(**checkpoint["config"])
        model = TinyRouterModel(config)
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()

        tokenizer = spm.SentencePieceProcessor(model_file=str(self.tokenizer_path))
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

        decoded = tokenizer.decode(generated)
        assistant_prefix = "<assistant>\n"
        if assistant_prefix not in decoded:
            return self._fallback(answer_allowed)
        candidate = decoded.split(assistant_prefix, 1)[1].strip()
        return candidate or self._fallback(answer_allowed)
