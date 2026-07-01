# API Reference

The API reference is generated automatically from the source docstrings.

## Parser and data classes

::: riffy.wav
    options:
      show_root_heading: false
      members:
        - WAVParser
        - WAVFormat
        - WAVChunk

## Recorder metadata

The unified entry point and per-standard classes. See the
[Recorder Metadata](metadata.md) guide for worked examples.

::: riffy.metadata.recording
    options:
      show_root_heading: false
      members:
        - read_metadata
        - dump_metadata
        - RecordingMetadata

::: riffy.metadata.guano
    options:
      show_root_heading: false
      members:
        - GuanoMetadata

::: riffy.metadata.info
    options:
      show_root_heading: false
      members:
        - InfoMetadata

::: riffy.metadata.bext
    options:
      show_root_heading: false
      members:
        - BextMetadata

::: riffy.metadata.wamd
    options:
      show_root_heading: false
      members:
        - WamdMetadata

::: riffy.metadata.audiomoth
    options:
      show_root_heading: false
      members:
        - AudioMothMetadata

::: riffy.metadata.ixml
    options:
      show_root_heading: false
      members:
        - IXmlMetadata

## Diffing

::: riffy.diff
    options:
      show_root_heading: false
      members:
        - diff
        - WavDiff
        - ChunkDelta
        - FieldDelta

## Exceptions

::: riffy.exceptions
    options:
      show_root_heading: false
