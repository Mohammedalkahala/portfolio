# Portfolio site

Source for my detection engineering portfolio. Plain Markdown and JSON, built by `build.py` and published to GitHub Pages by the workflow in `.github/workflows/pages.yml` on every push to `main`.

- **New write-up:** add `content/posts/YYYY-MM-DD-slug.md` with front matter (`title`, `date`, `slug`, `summary`).
- **New detection:** add an entry at the top of `data/detections.json` (newest first; the first one feeds the receipt on the home page).
- **New contribution:** add it to `data/contributions.json` and change `status` when it's merged.
- **Links and domain:** edit `config.json` (`linkedin`, `email`, `resume_pdf`, `custom_domain`).
- **Preview locally:** `pip install markdown && python3 build.py && python3 -m http.server -d _site 8000`
