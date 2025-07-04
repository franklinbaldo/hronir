# Plan for UUID-based Chapter Storage

This document outlines the proposed changes to store chapters using
content-derived UUIDs rather than the current numeric structure.

## Directory layout

- `the_library/` – root folder containing every chapter.
- `forking_path/` – sequence of chapters that form narrative branches.
- Each chapter will be referenced by a UUID v5 computed from its Markdown
  contents.
- Each Hrönir is stored in a directory named after its UUID. Example for UUID `01234567-89ab-cdef-0123-456789abcdef`:
  `the_library/01234567-89ab-cdef-0123-456789abcdef/index.md`.

## Chapter folder contents

Inside each chapter's UUID-named directory:

1. `index.md` (or another extension as needed) – the chapter text.
2. `metadata.json` – stores metadata such as the chapter's UUID.

## Forking paths

`forking_path/` will contain CSV files with the reading order.
Each row stores `position`, `prev_uuid`, and `uuid`.
The row also includes a deterministic `fork_uuid` computed from those
three pieces of data. This allows referencing individual branching events.

## Steps to implement

- [x] Create utilities to compute UUID v5 from chapter text.
- [ ] Migrate existing chapters into `the_library/` using their generated UUIDs.
- [x] Write `metadata.json` for each chapter storing its UUID.
- [ ] Generate initial `forking_path/canonical.csv` representing the current
      reading order.
- [ ] Update CLI commands to read and write chapters using the new structure.
- [ ] Adjust tests and documentation accordingly.

This approach keeps chapter identifiers stable even if positions change and
lays the groundwork for scalable branching and deduplication.
