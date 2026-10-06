# 420VaultBot Universal Manual Updater

This version fixes both earlier limitations.

It accepts:
- a normal full-build `.zip`
- an already extracted full-build folder
- the older `update_manifest.json` + `payload/` format

## Installation

Copy `update.py` and `update.bat` into the ROOT of the CURRENT bot installation
you want to upgrade.

Example:

    v5.8.1/
      build_v5.8.1/
        update.py
        update.bat
        ...current bot...

Run `update.bat` from there.

When prompted for `NEW update ZIP/folder path`, select the NEW release, e.g.:

    C:\Users\miron\Downloads\420VaultBot_v5.8.3_FULL.zip

or:

    C:\Users\miron\Downloads\420VaultBot_v5.8.3_FULL\

Do NOT select the current v5.8.1 installation as the update source.

## Preserved automatically

`.env`, `data/`, `config/`, `linklists/`, `credentials/`, `google_drive/`,
`vault_index/`, `preview_cache/`, `backups/`, and `logs/`.

A timestamped backup is created before copying the new application files.
