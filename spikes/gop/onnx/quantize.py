"""Dynamic int8 quantisation of the exported model.

    uv run --directory spikes/gop python onnx/quantize.py [--ops MatMul Conv ...]

Weights become int8; activations are quantised on the fly at run time (no calibration
data). Writes DATA_DIR/onnx/wav2vec2_int8.onnx. By default every quantisable op type is
included; --ops restricts it, which is the usual fix if the conv feature encoder hurts.

Memory: the fp32 file is 1.26 GB and the tool holds several copies of it (peak 4.0 GB).
Run it under a memory cap (see BENCH.md); two uncapped runs on the 8 GB dev machine
coincided with the WSL VM restarting. The optional `quant_pre_process` step is skipped:
its symbolic shape inference fails on this graph.
"""

import argparse
import os
import sys
import time
from pathlib import Path

from onnxruntime.quantization import QuantType, quantize_dynamic

sys.path.append(str(Path(__file__).resolve().parents[1]))
from clips import data_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ops", nargs="*", default=None, help="op types to quantise")
    parser.add_argument("--name", default="int8", help="output suffix: wav2vec2_<name>.onnx")
    args = parser.parse_args()
    root = data_dir() / "onnx"
    src, dst = root / "wav2vec2_fp32.onnx", root / f"wav2vec2_{args.name}.onnx"
    os.chdir(root)  # onnxruntime tools may write temporary files to the working directory
    start = time.perf_counter()
    quantize_dynamic(
        str(src),
        str(dst),
        weight_type=QuantType.QInt8,
        op_types_to_quantize=args.ops,
    )
    print(
        f"wrote {dst} ({dst.stat().st_size / 1e6:.0f} MB, "
        f"fp32 was {src.stat().st_size / 1e6:.0f} MB) "
        f"in {time.perf_counter() - start:.0f} s; ops={args.ops or 'all'}"
    )


if __name__ == "__main__":
    main()
