# Publishing Fireline Planner to the Official QGIS Plugin Repository

This is a one-time checklist to get the plugin listed on plugins.qgis.org,
where any QGIS user can find and install it via
**Plugins → Manage and Install Plugins → All / Search**.

## 1. Your details (already filled in)

`metadata.txt` already has:
- `author=Karthick V`
- `email=karthickvifs@gmail.com`
- `homepage`, `tracker`, `repository` → pointing to `https://github.com/karthickvifs/fireline_planner`

The GitHub repository itself still needs to be created and pushed to (step 2) —
these links won't actually work until that repo exists.

## 2. Create a public GitHub repository

The official repository REQUIRES your code to also live in a public,
browsable code repository (not just the zip you upload) — this is how
reviewers and users can inspect the source.

1. Create a free account at https://github.com if you don't have one.
2. Create a new **public** repository, e.g. named `fireline_planner`.
3. Push this entire `fireline_planner` folder's contents to that repository:
   ```bash
   cd fireline_planner
   git init
   git add .
   git commit -m "Initial release of Fireline Planner"
   git branch -M main
   git remote add origin https://github.com/karthickvifs/fireline_planner.git
   git push -u origin main
   ```
4. Confirm `metadata.txt` already has (no edit needed unless you rename the repo):
   - `homepage=https://github.com/karthickvifs/fireline_planner`
   - `tracker=https://github.com/karthickvifs/fireline_planner/issues`
   - `repository=https://github.com/karthickvifs/fireline_planner`

These links are checked by reviewers and must actually work — broken links
are a common reason for rejection.

## 3. Create an OSGeo user ID

You need this to log into plugins.qgis.org.
Register (free) at: https://www.osgeo.org/community/getting-started-osgeo/osgeo-userid/

## 4. Re-package the plugin cleanly

Before zipping, make sure there is NO `__pycache__`, `.git`, `.pyc`, or
`__MACOSX` folder inside. From one level above the `fireline_planner` folder:

```bash
find fireline_planner -name "__pycache__" -type d -exec rm -rf {} +
zip -r fireline_planner.zip fireline_planner -x "*.git*"
```

The zip must contain the `fireline_planner` folder at its root (not the
files loose at the top level) — this is already how it's structured.

## 5. Upload

1. Log in at https://plugins.qgis.org with your OSGeo ID.
2. Click "Share a plugin" (or go to https://plugins.qgis.org/plugins/add/).
3. Upload `fireline_planner.zip`. Most metadata fields auto-fill from
   `metadata.txt` — double check the homepage/tracker/repository links
   are filled in and correct.
4. Choose a license matching the included `LICENSE` file (GPL v2 or later).
5. Submit.

## 6. Wait for approval

A QGIS staff reviewer checks the plugin (usually within a business day,
longer over weekends/holidays). They will:
- Verify metadata links work
- Spot-check that it installs and runs without crashing QGIS
- Check for a README and LICENSE (both already included)

You'll get a notification once approved. New plugins start as
**experimental** — users need to enable "Show also experimental plugins"
in Plugin Manager → Settings to find it initially. After it's been stable
and used for a while, you can request it be marked as a regular
(non-experimental) plugin.

## 7. Releasing updates later

To publish a new version: bump the `version=` field in `metadata.txt`,
update the `changelog=` field with what changed, re-zip, and upload again
through the same "Share a plugin" flow (log in, go to your plugin's page,
upload a new version).
