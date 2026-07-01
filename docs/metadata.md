# Recorder Metadata

Bioacoustics field recorders embed rich metadata directly inside the WAV
container. riffy decodes the standards that matter in practice into typed Python
objects, while always keeping the raw chunk bytes reachable for anything it does
not model.

The metadata layer is additive: the core [`WAVParser`](api.md) stays a generic
chunk engine, and the classes here *consume* the chunk bytes it exposes. If you
only need chunk access, you pay nothing for this layer.

## Quick start

The one-call entry point detects and parses whatever standards a file contains:

```python
from riffy import read_metadata

meta = read_metadata("recording.wav")

meta.sources        # e.g. ('guano',) or ('info', 'audiomoth')
meta.guano          # GuanoMetadata | None
meta.info           # InfoMetadata  | None
meta.bext           # BextMetadata  | None
meta.audiomoth      # AudioMothMetadata | None
meta.wamd           # WamdMetadata  | None
```

`read_metadata` deliberately does **no** cross-standard reconciliation: it
surfaces each standard side by side, close to its raw parsed form, and leaves
"which timestamp/location wins" to downstream policy. That keeps riffy
predictable and avoids baking one consumer's opinions into the library.

## The standards

| Standard | Chunk | Encoding | riffy class | Read | Write |
|---|---|---|---|---|---|
| GUANO | `guan` | UTF-8 `key: value` text | `GuanoMetadata` | ✅ | ✅ |
| RIFF INFO | `LIST`/`INFO` | ZSTR sub-chunks | `InfoMetadata` | ✅ | ✅ |
| Broadcast Wave | `bext` | fixed binary (EBU 3285) | `BextMetadata` | ✅ | ✅ |
| WAMD | `wamd` (or `junk`) | packed binary entries | `WamdMetadata` | ✅ | ✅ |
| AudioMoth comment | `ICMT` free text | firmware-dependent | `AudioMothMetadata` | ✅ | — |
| iXML | `iXML` | UTF-8 XML | `IXmlMetadata` | ✅ | — |

### GUANO (`guan`)

GUANO (Grand Unified Acoustic Notation Ontology) is the closest thing the field
has to a vendor-neutral standard, emitted by Wildlife Acoustics Song Meters,
Titley, Pettersson, Open Acoustic Devices, and others. Well-known fields are
typed attributes; vendor and arbitrary fields round-trip verbatim.

```python
from riffy import WAVParser, GuanoMetadata

g = GuanoMetadata.from_parser(WAVParser("bat.wav"))
g.version               # "1.0"
g.timestamp             # datetime, UTC offset preserved
g.loc_position          # (37.1878, -86.1057)
g.make, g.model, g.serial
g.species_manual_id     # ["Myotis lucifugus"]

g.get("WA", "Song Meter|Prefix")   # vendor-namespaced access
g.fields                           # full (namespace, key) -> raw value

# Edit and write back
g.species_manual_id = ["MYLU"]
g.set("WA", "Temperature Int", "12.5")
parser = WAVParser("bat.wav")
g.write_to_parser(parser)
parser.write_wav("bat-tagged.wav")
```

Unknown fields and namespaces are preserved untouched on round-trip — a hard
requirement of the GUANO spec. Non-UTF-8 payloads fall back to latin-1 with a
warning rather than failing.

### RIFF INFO (`LIST`/`INFO`)

Standard INFO tags are exposed with friendly names while raw FOURCC access is
retained. This is also the carrier the AudioMoth decoder reads from.

```python
from riffy import WAVParser, InfoMetadata

info = InfoMetadata.from_parser(WAVParser("clip.wav"))
info.title, info.artist, info.comment, info.software
info.get("ICMT")                 # raw FOURCC access
info.tags                        # full FOURCC -> value mapping

info.artist = "Field Team"
info.write_to_parser(parser)     # updates only the INFO list, leaves others alone
```

### Broadcast Wave (`bext`)

`bext` is a fixed binary layout, parsed with `struct`. riffy reads and writes
all three versions, gating version-specific fields (`umid` needs v1+, loudness
needs v2+). Loudness values are preserved verbatim on write but never computed.

```python
from riffy import WAVParser, BextMetadata

b = BextMetadata.from_parser(WAVParser("bwf.wav"))
b.description, b.originator, b.time_reference, b.version

# Author a bext chunk
new = BextMetadata(
    version=1,
    description="Dawn chorus survey",
    originator="riffy",
    origination_date="2026-07-01",
    time_reference=0,
)
new.write_to_parser(parser)
parser.write_wav("bwf-tagged.wav")
```

### WAMD (`wamd`)

WAMD (Wildlife Acoustics Metadata) is the vendor format Song Meter recorders
embed — alongside GUANO, or, on older firmware, in a `junk` chunk instead. It is
a packed binary stream of length-prefixed entries (a 16-bit id, a 32-bit length,
then the value). riffy reads and writes it, exposing `loc_position` as a
`(lat, lon)` tuple (decoding both the Song Meter `N/S/E/W` and EMTouch signed GPS
dialects) plus `model`, `serial`, `firmware`, `timestamp`, and `notes`. Unknown
tags, opaque blobs, and alignment padding round-trip byte-for-byte, so editing
one field leaves the rest of the chunk untouched.

```python
from riffy import WAVParser, WamdMetadata

parser = WAVParser("songmeter.wav")
w = WamdMetadata.from_parser(parser)
w.loc_position          # (10.31796, -84.07411)
w.model, w.firmware

# Correct the coordinates in place (only the GPS field changes)
w.loc_position = (10.31801, -84.07399)
w.write_to_parser(parser)
parser.write_wav("songmeter-fixed.wav")
```

The WAMD-in-`junk` variant is read only when the `junk` chunk carries the
unmistakable WAMD signature, so ordinary `junk` padding is never mistaken for
metadata.

### AudioMoth comment

AudioMoth packs device ID, timestamp, gain, battery, and (on newer firmware)
temperature and trigger settings into the `ICMT` free-text string, in a format
that drifts between firmware versions. riffy decodes each field with its own
tolerant regex, so extraction is **partial** — a failure in one clause never
discards the others.

```python
from riffy import WAVParser, AudioMothMetadata

am = AudioMothMetadata.from_parser(WAVParser("audiomoth.wav"))
am.timestamp            # timezone-aware datetime
am.device_id            # "0FE081F80FE081F0"
am.gain                 # "medium" (numeric firmware gains are normalized)
am.battery_voltage, am.temperature_c

# Normalize into GUANO shape (within-standard convenience)
g = am.to_guano()       # GuanoMetadata with Make/Model/Serial/Timestamp/...
```

!!! warning "AudioMoth parsing is best-effort"
    The comment format is undocumented and firmware-dependent. riffy's decoder
    is derived from the [`metamoth`](https://github.com/mbsantiago/metamoth)
    library and the [AudioMoth firmware source](https://github.com/OpenAcousticDevices/AudioMoth-Firmware-Basic),
    and validated against real recordings, but newer or unusual firmware may
    leave some fields unparsed. The raw string is always available on
    `AudioMothMetadata.comment`.

### iXML (`iXML`, read-only)

Production recorders (Sound Devices, Zoom) embed structured XML. riffy parses it
into a nested dict for inspection. Authoring iXML is out of scope.

```python
from riffy import WAVParser, IXmlMetadata

ix = IXmlMetadata.from_parser(WAVParser("take.wav"))
if ix is not None:
    ix.find("PROJECT")
    ix.to_dict()
```

## Device support matrix

Which standard each recorder family emits, and what riffy extracts:

| Device | Emits | riffy extracts |
|---|---|---|
| Wildlife Acoustics Song Meter | GUANO (`guan`), WAMD (`wamd`/`junk`) | full typed GUANO + vendor `WA` namespace; WAMD location, device, timestamp |
| Titley | GUANO | full typed GUANO |
| Pettersson | GUANO | full typed GUANO |
| Open Acoustic Devices | GUANO | full typed GUANO |
| AudioMoth (device firmware) | INFO `ICMT` comment | timestamp, device/deployment ID, gain, battery, temperature, threshold/filter (firmware-dependent) |
| Sound Devices / Zoom | iXML (+ `bext`) | iXML tree, `bext` fields |
| Any BWF producer | `bext` | typed Broadcast Wave fields |

## Command-line inspector

`python -m riffy` prints the detected standards and parsed fields, using only
the standard library:

```console
$ python -m riffy recording.wav
File:      recording.wav
RIFF form: RIFF
Format:    44100 Hz, 1 ch, 16-bit
Metadata:  guano

[guano]
  GUANO|Version: 1.0
  Make: Wildlife Acoustics, Inc.
  ...

$ python -m riffy --json recording.wav      # JSON-serializable dump
```

The same structured dump is available programmatically:

```python
from riffy import dump_metadata
import json

data = dump_metadata("recording.wav")   # plain, JSON-serializable dict
print(json.dumps(data, indent=2))
```

## Comparing and verifying files

`riffy.diff(a, b)` compares two WAV files at two levels — which chunks changed,
and which decoded metadata fields changed — so you can confirm a batch edit did
exactly (and only) what you intended.

```python
from riffy import diff

d = diff("original.wav", "corrected.wav")
d.identical            # False
d.changed_chunks       # [ChunkDelta(chunk_id='guan', status='changed', ...)]
for f in d.fields:
    print(f.standard, f.key, f.old, "->", f.new)
    # guano Loc Position 35.9 -83.9 -> 36.31 -82.34
```

Chunk comparison is insensitive to chunk reordering (occurrences are matched per
ID), so a re-written file diffs clean except for the fields you actually changed.

From the command line:

```console
$ python -m riffy diff original.wav corrected.wav
$ python -m riffy diff --json original.wav corrected.wav
```

The [`batch_correct_guano.py`](https://github.com/jmcmeen/riffy/blob/main/examples/batch_correct_guano.py)
example uses this to bulk-fix a GUANO field across a folder (e.g. a wrong
`Loc Position` from a stale GPS fix) with a `--verify` mode that diffs each file
against its original to confirm only the intended field changed.

## Known limitations

- **AudioMoth firmware 1.8+ frequency trigger.** The `Frequency trigger (...)`
  clause is not decoded into a dedicated field (no real sample was available to
  validate it). It remains in the raw `comment` string and is deliberately not
  mistaken for a frequency filter.
- **RIFF INFO encoding.** INFO values are treated as latin-1 (byte-preserving,
  matching the ASCII/codepage heritage). UTF-8 metadata belongs in GUANO.
- **RF64 `fact` chunk.** riffy's RF64/BW64 writer emits `ds64` but not a `fact`
  chunk; the sample count is carried in `ds64`. Most readers (including ffmpeg)
  accept this.
- **iXML is read-only** and parsed with the standard library, which is not
  hardened against maliciously crafted XML — treat recorder output as trusted
  input.
