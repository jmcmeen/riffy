# Migrating to v0.3.0

v0.3.0 adds the recorder-metadata layer and RF64/BW64 large-file support. It
also makes **one breaking change** to the core parser that every v0.2.x user
should be aware of.

## Breaking: `chunks` is now `dict[str, list[WAVChunk]]`

A WAV file can legitimately contain more than one chunk with the same ID (for
example several `LIST` chunks). v0.2.x keyed `WAVParser.chunks` by ID and so
silently kept only the **last** occurrence. v0.3.0 fixes the data model:
`chunks` now maps each ID to an **ordered list of every occurrence**, in file
order.

### What changed, and how to update

Fetching a single chunk — use the new convenience accessor:

```python
# v0.2.x
fmt = parser.chunks["fmt "]          # a WAVChunk

# v0.3.0
fmt = parser.get_chunk("fmt ")       # the first WAVChunk, or None
# or, explicitly:
fmt = parser.chunks["fmt "][0]
```

Iterating all chunks — iterate the inner list:

```python
# v0.2.x
for chunk_id, chunk in parser.chunks.items():
    ...

# v0.3.0
for chunk_id, chunk_list in parser.chunks.items():
    for chunk in chunk_list:
        ...
```

New accessors for the common cases:

| Method | Returns |
|---|---|
| `parser.get_chunk(id)` | the first chunk with that ID, or `None` |
| `parser.get_chunks(id)` | every chunk with that ID, in file order (`[]` if none) |
| `parser.get_chunk_bytes(id)` | raw bytes of the first such chunk, or `None` |

Other affected surfaces:

- **`get_info()["chunks"]`** values changed from `int` (a size) to `list[int]`
  (one size per occurrence).
- **`list_chunks()`** values changed from a `{"size", "offset"}` dict to a
  **list** of such dicts, one per occurrence.
- **`add_chunk(id, data)`** no longer raises `ValueError` when the ID already
  exists — it **appends** a new occurrence. Use `set_chunk()` to add-or-replace
  the first occurrence, or `replace_chunk()` to overwrite it.

### Why

v0.3.0 already takes on core-parser changes (RF64/BW64), and riffy is still
young, so this was the right moment to fix the data model properly rather than
work around it. With multi-chunk-per-ID in place, `LIST` chunks (including RIFF
INFO) are just ordinary chunks the metadata layer decodes — no dedup
special-casing needed.

## New: large files write as RF64/BW64 automatically

`write_wav` still produces byte-for-byte identical classic WAV when the sizes
fit. Only when a size crosses the 4 GB 32-bit limit does it switch to the
RF64/BW64 form (emitting a `ds64` chunk). You can force the large-file form with
`parser.write_wav(path, force_rf64=True)`. See the
[Recorder Metadata](metadata.md) guide and the [API Reference](api.md) for the
new `is_rf64` / `riff_form` attributes.
