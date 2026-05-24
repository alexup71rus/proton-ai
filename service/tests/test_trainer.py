import pytest
import torch

from protonx.training.model import TinyRouterConfig, TinyRouterModel
from protonx.training.trainer import _assert_finite_model_parameters
from protonx.training.trainer import IGNORE_INDEX, _batch_records, _cpu_state_dict
from protonx.training.trainer import _finite_loss_value
from protonx.training.trainer import _select_training_device
from protonx.training.trainer import _tool_name_symbols
from protonx.training.format import serialize_assistant_payload


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


def test_serialize_assistant_payload_keeps_only_tool_calls_and_name_first():
    serialized = serialize_assistant_payload(
        {
            "tool_calls": [
                {
                    "name": "list_downloads",
                    "arguments": {},
                    "answer": False,
                }
            ],
            "answer": False,
            "fallback": False,
            "response": "ignored",
        }
    )

    assert serialized == '{"tool_calls":[{"name":"list_downloads","arguments":{}}]}'


def test_select_training_device_defaults_to_cpu(monkeypatch):
    monkeypatch.delenv("PROTONX_TRAIN_DEVICE", raising=False)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)

    assert _select_training_device().type == "cpu"


def test_select_training_device_can_force_mps_when_available(monkeypatch):
    monkeypatch.setenv("PROTONX_TRAIN_DEVICE", "mps")
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)

    assert _select_training_device().type == "mps"


def test_select_training_device_can_force_cpu(monkeypatch):
    monkeypatch.setenv("PROTONX_TRAIN_DEVICE", "cpu")
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)

    assert _select_training_device().type == "cpu"


def test_cpu_state_dict_detaches_checkpoint_tensors_to_cpu():
    model = TinyRouterModel(
        TinyRouterConfig(
            vocab_size=8,
            hidden_dim=8,
            num_layers=1,
            num_heads=2,
            max_seq_len=8,
        )
    )

    state_dict = _cpu_state_dict(model)

    assert state_dict
    assert all(tensor.device.type == "cpu" for tensor in state_dict.values())


def test_finite_loss_value_rejects_nan():
    with pytest.raises(ValueError, match="non-finite"):
        _finite_loss_value(torch.tensor(float("nan")))


def test_assert_finite_model_parameters_rejects_nan_weight():
    model = TinyRouterModel(
        TinyRouterConfig(
            vocab_size=8,
            hidden_dim=8,
            num_layers=1,
            num_heads=2,
            max_seq_len=8,
        )
    )
    with torch.no_grad():
        model.head.weight[0, 0] = float("nan")

    with pytest.raises(ValueError, match="checkpoint was not saved"):
        _assert_finite_model_parameters(model)


def test_tool_name_symbols_include_available_and_target_tools():
    symbols = _tool_name_symbols(
        [
            {
                "tools": [{"name": "get_current_time"}],
                "assistant": {"tool_calls": [{"name": "custom_runtime_tool"}]},
            }
        ]
    )

    assert symbols == ["custom_runtime_tool", "get_current_time"]
