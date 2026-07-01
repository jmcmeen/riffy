"""Shared helpers for the riffy example scripts.

Files whose name starts with ``_`` are treated as support modules, not runnable
examples, so ``run_all.py`` skips them.
"""

import struct
from pathlib import Path


def make_pcm_wav(
    path: str | Path,
    *,
    sample_rate: int = 44100,
    channels: int = 1,
    bits_per_sample: int = 16,
    seconds: float = 0.05,
) -> Path:
    """Write a minimal valid PCM WAV file and return its path.

    The examples use this to produce a base file, then embed metadata into it
    with riffy's metadata classes.
    """
    block_align = channels * bits_per_sample // 8
    byte_rate = sample_rate * block_align
    num_frames = int(sample_rate * seconds)
    audio = bytes(i % 256 for i in range(num_frames * block_align))

    fmt = struct.pack("<HHIIHH", 1, channels, sample_rate, byte_rate, block_align, bits_per_sample)
    body = (
        b"fmt "
        + struct.pack("<I", len(fmt))
        + fmt
        + b"data"
        + struct.pack("<I", len(audio))
        + audio
    )
    path = Path(path)
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body) + 4) + b"WAVE" + body)
    return path


def banner(title: str) -> None:
    """Print a section header for readable example output."""
    print(f"\n=== {title} ===")
