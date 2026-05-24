import pytest

from protonx.training.trainer import IGNORE_INDEX, _batch_records


def test_batch_records_masks_prompt_targets_and_pad_positions():
    batch_tensors = _batch_records(
        tokenized_records=[([10, 11, 12], [13, 14]), ([20, 21], [22])],
        max_seq_len=8,
        pad_id=0,
        eos_id=2,
    )

    assert batch_tensors is not None
    input_ids, labels = batch_tensors

    assert input_ids.tolist() == [
        [10, 11, 12, 13, 14],
        [20, 21, 22, 0, 0],
    ]
    assert labels.tolist() == [
        [IGNORE_INDEX, IGNORE_INDEX, 13, 14, 2],
        [IGNORE_INDEX, 22, 2, IGNORE_INDEX, IGNORE_INDEX],
    ]


def test_batch_records_rejects_silent_truncation():
    with pytest.raises(ValueError, match="exceeds max_seq_len"):
        _batch_records(
            tokenized_records=[([10, 11, 12], [13, 14])],
            max_seq_len=5,
            pad_id=0,
            eos_id=2,
        )