# Notes: kaggle_metadata.py

**Script:** `Pipeline/kaggle_metadata.py`
**Purpose:** Fill in the Kaggle dataset page's text before each version push: live row counts, the "About Dataset" description, and a description for every column.

---

## In plain English

Kaggle shows three things that used to need editing by hand on the website: the short subtitle under the title, the long "About Dataset" text, and a description next to each column in each file. This script writes all three into the upload's `dataset-metadata.json` right before the daily push, so the Kaggle page always matches the repo.

---

## What it does

Run by the "Push to Kaggle" step of `.github/workflows/daily_scrape.yml` on the copy in `/tmp/kaggle_push`, never on the committed files:

1. **Row counts.** Rewrites the Rows and Cols cells of the Files table in `README.md` from the actual CSVs. It exits with an error if a file's table row is missing or duplicated, so a README restructure fails loudly instead of silently showing stale numbers.
2. **Subtitle and About text.** Sets `subtitle` (Kaggle requires 20 to 80 characters) and sets `description` to the README after step 1.
3. **Column descriptions.** Adds a `resources` entry per CSV: a one-line file description (the `FILES` dict in the script) and one field per column, in the CSV's own column order. Each field reads "Unit. Source. From (schema start date). Notes" from that file's sheet in `Dataset/data_dictionary.xlsx`. It exits with an error if any CSV column is missing from the dictionary. No column `type` is sent; Kaggle infers it.

`kaggle datasets version` applies `subtitle`, `description` and the per-file `resources` on every push, so hand edits on the Kaggle page are overwritten. Edit the README, the dictionary (via `build_data_dict.py`) or the `FILES` dict instead.

## Tags

`keywords` in `Dataset/dataset-metadata.json` are sent as the dataset's tags on every `kaggle datasets version` push (added 2026-11-09). They must be existing Kaggle tag names, in lower case.

## License is not pushed

`kaggle datasets version` (kaggle 2.2.5) sends subtitle, description and file resources, but not `licenses`. The license in `Dataset/dataset-metadata.json` (CC-BY-SA-4.0 since 2026-11-09, matching `Dataset/README.md` and the attribution the NDSAP source needs) only applies on first creation; on the live dataset it is set by hand in Kaggle's dataset settings. Do not switch to `kaggle datasets metadata --update` to push it: that call also replaces the collaborator list with the file's (none), which would drop collaborators.

## Refreshing the repo README

The committed README is not touched in CI. To bring its counts up to date locally:

```
python Pipeline/kaggle_metadata.py --update-readme
```

Line endings are preserved as found.

## History

- 2026-11-09: added. Before this the README's counts were from an older snapshot (for example `study2_scada` showed 57,084 rows against 68,604 actual) and Kaggle had no column descriptions, which held the usability score at 0.88.
