# Riffy Examples

Runnable scripts demonstrating riffy, from basic WAV parsing through the v0.3.0
recorder-metadata layer. Each script is self-contained.

## Running

Install riffy (Python 3.10 or newer):

```bash
pip install -e .   # from the riffy root, or: pip install riffy
```

Run them all with a pass/fail summary, or one at a time:

```bash
make examples                        # all, from the project root
python examples/run_all.py           # all (add -v to stream output)
python examples/guano_metadata.py    # just one
```

## Core

| Script | Use case |
| --- | --- |
| `example.py` | Basic parsing — format info, audio data, chunk iteration, JSON output. |
| `export_chunks.py` | Export individual chunks and raw audio to `.bin` files. |

## Chunk modification

Each embeds a single modification operation, verifying the result by re-parsing
the output.

| Script | Use case |
| --- | --- |
| `replace_chunk.py` | Replace an existing chunk's data with `replace_chunk()`. |
| `add_chunk.py` | Add metadata chunks (`INFO`, `ICMT`, `ICOP`) with `add_chunk()`. |
| `set_chunk.py` | Add-or-replace with `set_chunk()`. |
| `copy_chunk.py` | Copy chunks between files with `copy_chunk_from_parser()`. |
| `overwrite_wav.py` | The `overwrite=True` guard on `write_wav()`. |
| `complete_workflow.py` | Full pipeline: parse → replace audio → add metadata → write → verify. |

## Recorder metadata (v0.3.0)

Each builds a WAV, embeds metadata of one kind, then reads it back.

| Script | Use case |
| --- | --- |
| `guano_metadata.py` | GUANO (`guan`) — typed fields (timestamp, location, species) and vendor namespaces. |
| `info_metadata.py` | RIFF INFO (`LIST`/`INFO`) tags via friendly attributes and raw FOURCCs. |
| `bext_metadata.py` | Broadcast Wave (`bext`), with version-gated fields (UMID v1+, loudness v2+). |
| `audiomoth_comment.py` | Decode an AudioMoth `ICMT` comment, then normalize it with `to_guano()`. |
| `ixml_metadata.py` | Read an `iXML` document as a nested dict / via `find()`. |
| `rf64_largefile.py` | Write the RF64/BW64 large-file form with `write_wav(force_rf64=True)`. |
| `read_metadata_unified.py` | Detect every standard at once with `read_metadata()` + `dump_metadata()`. |
| `batch_correct_guano.py` | Batch-fix a GUANO field (e.g. a wrong `Loc Position`) across a whole folder — dry-run by default, atomic writes, `--backup`, verified. |

## `practical_demo.py`

Bundles the chunk-modification operations into one run — a quick end-to-end
smoke test of the modification API.

## Notes

- `example.py` keeps `example.wav` (git-ignored) for reuse; every other example
  writes to a temporary directory and leaves nothing behind.
- Not seeing riffy? Install it (above) and check `python --version` is 3.10+.

## More

- [Documentation site](https://jmcmeen.github.io/riffy/) — usage guide,
  [Recorder Metadata guide](https://jmcmeen.github.io/riffy/metadata/), and API
  reference
- [Main README](../README.md) and [tests](../tests/)
