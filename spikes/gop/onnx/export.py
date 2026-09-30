"""Export facebook/wav2vec2-lv-60-espeak-cv-ft to ONNX with a dynamic time axis.

    uv run --directory spikes/gop python onnx/export.py

Input  `input_values` float32 [batch, samples], already normalised (audio_prep.normalise).
Output `logits`       float32 [batch, frames, vocab]; log-softmax is done in numpy.
Writes DATA_DIR/onnx/wav2vec2_fp32.onnx.
"""

import os
import time
from pathlib import Path

import torch
from transformers import Wav2Vec2ForCTC

MODEL = "facebook/wav2vec2-lv-60-espeak-cv-ft"


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "~/sonari-data")).expanduser()


class Logits(torch.nn.Module):
    """The CTC model without the output dataclass, so the graph has one output."""

    def __init__(self, model: Wav2Vec2ForCTC) -> None:
        super().__init__()
        self.model = model

    def forward(self, input_values: torch.Tensor) -> torch.Tensor:
        return self.model(input_values).logits


def main() -> None:
    out = data_dir() / "onnx"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "wav2vec2_fp32.onnx"
    model = Wav2Vec2ForCTC.from_pretrained(MODEL, attn_implementation="eager").eval()
    example = torch.randn(1, 16000 * 3)
    start = time.perf_counter()
    torch.onnx.export(
        Logits(model),
        (example,),
        str(path),
        input_names=["input_values"],
        output_names=["logits"],
        dynamic_axes={
            "input_values": {0: "batch", 1: "samples"},
            "logits": {0: "batch", 1: "frames"},
        },
        dynamo=False,
        external_data=False,
    )
    size = path.stat().st_size / 1e6
    print(
        f"exported {path} ({size:.0f} MB) in {time.perf_counter() - start:.0f} s, "
        f"torch {torch.__version__}"
    )


if __name__ == "__main__":
    main()
