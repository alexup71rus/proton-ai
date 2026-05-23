from pathlib import Path

import sentencepiece as spm


def train_sentencepiece(
    input_path: Path, model_prefix: Path, vocab_size: int = 2048
) -> Path:
    spm.SentencePieceTrainer.train(
        input=str(input_path),
        model_prefix=str(model_prefix),
        vocab_size=vocab_size,
        model_type="bpe",
        hard_vocab_limit=False,
        bos_id=1,
        eos_id=2,
        pad_id=0,
        unk_id=3,
    )
    return model_prefix.with_suffix(".model")
