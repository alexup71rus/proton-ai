from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = DATA_DIR / "logs"
TRAIN_DIR = DATA_DIR / "train" / "routing"
TOKENIZER_DIR = DATA_DIR / "tokenizers"
WEIGHTS_DIR = DATA_DIR / "weights"
