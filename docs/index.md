# riffy

Riffy is a pure Python library for parsing and managing RIFF format files, with
initial support for WAV audio files. It has **zero external dependencies** and
ships full type hints (PEP 561).

## Install

```bash
pip install riffy
```

## Highlights

- Parse WAV files and extract format metadata (sample rate, channels, bit depth, duration)
- Inspect, add, replace, copy, and remove RIFF chunks
- Decode recorder metadata: GUANO, RIFF INFO, Broadcast Wave `bext`, AudioMoth, iXML
- RF64 / BW64 large-file support (files above 4 GB)
- Write modified WAV files back to disk
- A clear custom exception hierarchy rooted at `RiffyError`
- Pure Python, zero dependencies, fully typed

## Next steps

- Read the [Usage](usage.md) guide for runnable examples.
- See the [Recorder Metadata](metadata.md) guide for GUANO/INFO/bext/AudioMoth/iXML.
- Upgrading from v0.2.x? See the [Migration](migration.md) note.
- Browse the full [API Reference](api.md), generated from the source docstrings.

See the project [README](https://github.com/jmcmeen/riffy#readme) and
[CHANGELOG](https://github.com/jmcmeen/riffy/blob/main/CHANGELOG.md) on GitHub.
