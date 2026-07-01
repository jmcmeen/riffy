# Riffy Examples

Runnable scripts demonstrating riffy, from basic WAV parsing through the v0.3.0
recorder-metadata layer. There are two parallel suites:

- **`python/`** — library examples using the `riffy` Python API directly.
- **`bash/`** — shell examples driving the `riffy` command-line interface.

Each script is self-contained and cleans up after itself.

## Running

Install riffy (Python 3.10 or newer); this also puts the `riffy` command on your
PATH, which the bash examples use:

```bash
pip install -e .   # from the riffy root, or: pip install riffy
```

```bash
make examples            # both suites, from the project root
make examples-python     # just the Python suite
make examples-bash       # just the bash suite

python examples/python/run_all.py        # all Python examples (add -v to stream)
python examples/python/guano_metadata.py # just one Python example

bash examples/bash/run_all.sh            # all bash examples (add -v to stream)
bash examples/bash/set_guano.sh          # just one bash example
```

The bash suite needs `riffy` on PATH. If it isn't installed as a command, set
`RIFFY="python -m riffy"` (see `bash/_helpers.sh`).

## Python suite (`python/`)

### Core & chunk modification

| Script | Use case |
| --- | --- |
| `example.py` | Basic parsing — format info, audio data, chunk iteration, JSON output. |
| `export_chunks.py` | Export individual chunks and raw audio to `.bin` files. |
| `replace_chunk.py` | Replace an existing chunk's data with `replace_chunk()`. |
| `add_chunk.py` | Add metadata chunks with `add_chunk()`. |
| `set_chunk.py` | Add-or-replace with `set_chunk()`. |
| `copy_chunk.py` | Copy chunks between files with `copy_chunk_from_parser()`. |
| `overwrite_wav.py` | The `overwrite=True` guard on `write_wav()`. |
| `complete_workflow.py` | Full pipeline: parse → replace audio → add metadata → write → verify. |
| `practical_demo.py` | Bundles the chunk-modification operations into one smoke-test run. |

### Recorder metadata (v0.3.0)

| Script | Use case |
| --- | --- |
| `guano_metadata.py` | GUANO (`guan`) — typed fields and vendor namespaces. |
| `info_metadata.py` | RIFF INFO (`LIST`/`INFO`) via friendly attributes and raw FOURCCs. |
| `bext_metadata.py` | Broadcast Wave (`bext`), with version-gated fields. |
| `audiomoth_comment.py` | Decode an AudioMoth `ICMT` comment, then normalize with `to_guano()`. |
| `ixml_metadata.py` | Read an `iXML` document as a nested dict / via `find()`. |
| `rf64_largefile.py` | Write the RF64/BW64 large-file form with `write_wav(force_rf64=True)`. |
| `read_metadata_unified.py` | Detect every standard at once with `read_metadata()` / `dump_metadata()`. |
| `batch_correct_guano.py` | Batch-fix a GUANO field across a folder — dry-run, atomic writes, `--backup`, verified. |

## Bash suite (`bash/`)

Each bash example mirrors a Python example's intent, but performs the work
through the `riffy` CLI. It synthesizes a sample WAV in a scratch directory (via
a short Python snippet in `_helpers.sh`, since the CLI is about editing existing
files) and then operates on it.

| Script | CLI exercised | Mirrors |
| --- | --- | --- |
| `inspect.sh` | `riffy inspect` (text + `--json`) | `example.py`, `read_metadata_unified.py` |
| `chunks.sh` | `riffy chunks` | `example.py` |
| `info.sh` | `riffy info` | `example.py` |
| `export_chunks.sh` | `riffy export --chunk/--audio` | `export_chunks.py` |
| `set_guano.sh` | `riffy set --guano` | `guano_metadata.py` |
| `set_info.sh` | `riffy set --info` / `--remove-info` | `info_metadata.py` |
| `set_bext.sh` | `riffy set --bext` | `bext_metadata.py` |
| `chunk_add.sh` | `riffy chunk add` | `add_chunk.py` |
| `chunk_replace_set.sh` | `riffy chunk set` / `replace` | `set_chunk.py`, `replace_chunk.py` |
| `chunk_copy.sh` | `riffy chunk copy --from` | `copy_chunk.py` |
| `chunk_remove.sh` | `riffy chunk remove` | (new — no library-example equivalent) |
| `overwrite_guard.sh` | dry-run vs `--apply` write guard | `overwrite_wav.py` |
| `workflow.sh` | `set` + `chunk add` + `diff` + `inspect` | `complete_workflow.py` |
| `audiomoth_inspect.sh` | `riffy inspect` on an AudioMoth `ICMT` file | `audiomoth_comment.py` |
| `ixml_inspect.sh` | `riffy inspect` on an iXML file | `ixml_metadata.py` |
| `rf64_largefile.sh` | `riffy set --force-rf64` | `rf64_largefile.py` |
| `diff.sh` | `riffy diff` (text + `--json`) | round-trip verification |
| `batch_correct_guano.sh` | `find … -exec riffy set --guano …` | `batch_correct_guano.py` |

`practical_demo.py` has no standalone bash mirror — it is a bundled smoke test,
a role `bash/run_all.sh` already fills for the bash suite. The AudioMoth and iXML
decoders have no dedicated CLI verb, so their bash examples surface those fields
through `riffy inspect` rather than a like-for-like command.

## Notes

- `python/example.py` keeps an `example.wav` (git-ignored) beside it for reuse;
  every other example writes to a temporary directory and leaves nothing behind.
- Not seeing riffy? Install it (above) and check `python --version` is 3.10+.

## More

- [Documentation site](https://jmcmeen.github.io/riffy/) — usage guide,
  [Recorder Metadata guide](https://jmcmeen.github.io/riffy/metadata/),
  [CLI reference](https://jmcmeen.github.io/riffy/cli/), and API reference
- [Main README](../README.md) and [tests](../tests/)
