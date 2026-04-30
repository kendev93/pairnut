---
name: pairnut-release
description: PairNut project release workflow. Use when preparing, validating, tagging, pushing, or troubleshooting a PairNut version release; updating pyproject/package version, pairnut.__version__, CHANGELOG.md, GitHub Actions packaging, GitHub Release notes, or Gitee Release handoff.
---

# PairNut Release

Use this skill to prepare and publish PairNut desktop releases without losing the project-specific details learned during `v1.1.0` and `v1.1.1`.

## Release Model

- Git tags use `vX.Y.Z`, for example `v1.1.1`.
- App/package version files use `X.Y.Z` without `v`:
  - `pyproject.toml`
  - `pairnut/__init__.py`
- `CHANGELOG.md` must include a matching `## vX.Y.Z` section.
- GitHub Actions build workflow triggers on `push` tags matching `v*`.
- GitHub Release is mainly used to collect Windows/macOS build artifacts.
- User-facing update checks read Gitee Releases, so GitHub Release assets and notes still need to be copied to Gitee manually unless explicit Gitee upload automation is added.

## Standard Workflow

1. Inspect current state:

   ```bash
   git status --short
   git log --oneline --decorate -8
   git tag --list "vX.Y.Z"
   rg -n "version =|__version__|## vX.Y.Z" pyproject.toml pairnut/__init__.py CHANGELOG.md
   ```

2. If `CHANGELOG.md` does not already contain `## vX.Y.Z`, generate it before changing versions:

   ```bash
   previous_tag="$(git describe --tags --abbrev=0 HEAD^ 2>/dev/null || true)"
   git log --oneline "${previous_tag}..HEAD"
   git diff --stat "${previous_tag}..HEAD"
   git diff --name-only "${previous_tag}..HEAD"
   ```

   If `previous_tag` is empty, inspect recent history instead:

   ```bash
   git log --oneline --max-count=30
   git diff --stat
   ```

   Then add a product-focused `## vX.Y.Z` section near the top of `CHANGELOG.md`. Summarize user-visible behavior from commits and diffs, not only commit messages. Mention implementation-only changes only when they affect release behavior, packaging, data safety, or user operations.
   If a release changes matching evidence sources, scoring weights, images, features, models, or 3D-model import direction, describe it using the PairNut architecture principle: input is open, evidence is optional, scoring combines available sources dynamically, and no scanner/model provider is required.

3. If version files do not match the target release, update:
   - `pyproject.toml`: `version = "X.Y.Z"`
   - `pairnut/__init__.py`: `__version__ = "X.Y.Z"`

4. Keep `CHANGELOG.md` product-focused. Include user-visible changes first:
   - `### 新增`
   - `### 改进`
   - `### 修复`
   - optional `### 注意事项`

5. Validate before tagging:

   ```bash
   pytest -q
   python3 -m compileall main.py pairnut tests scripts
   git diff --check
   ```

6. Commit release changes if needed:

   ```bash
   git add CHANGELOG.md pyproject.toml pairnut/__init__.py
   git commit -m "chore: release vX.Y.Z"
   ```

   If the user explicitly wants to write commit messages themselves, only `git add` and report staged files.

7. Create and push tag:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

   If the sandbox blocks local tag creation, rerun `git tag vX.Y.Z` with escalation. If network push is blocked, rerun `git push origin vX.Y.Z` with escalation.

## GitHub Actions Release Notes

The build workflow should create Release notes by combining:

1. the matching `CHANGELOG.md` section, extracted from `## vX.Y.Z`
2. GitHub generated notes from `gh api repos/<repo>/releases/generate-notes`

The final `gh release create` should use:

```bash
gh release create "$TAG_NAME" release-assets/* \
  --repo "${{ github.repository }}" \
  --title "PairNut ${TAG_NAME}" \
  --notes-file release-notes.md
```

Do not rely only on `--generate-notes`: it mostly lists PRs and contributors, and misses direct commits that contain product features.

## Packaging Details

Build artifacts should include the package version without `v`, read from `pyproject.toml`:

- `PairNut-X.Y.Z-windows-x64.exe`
- `PairNut-X.Y.Z-macOS-ARM64.dmg`
- `PairNut-X.Y.Z-macOS-X64.dmg`

Keep the tag with `v`; only artifact names drop the `v`.

## Troubleshooting

- If rerunning an old failed tag workflow still fails, remember that GitHub Actions uses the workflow file from the commit pointed to by that tag. Fixing workflow on `main` does not affect an old tag run.
- If the old tag has not produced a usable release, either move the tag intentionally or create a new patch tag. Prefer a new patch tag when the user says “推个新 tag”.
- `fatal: not a git repository` in the release job usually means `gh release create` ran without checkout and without `--repo`. Add `--repo "${{ github.repository }}"` or checkout the repo.
- GitHub generated notes can be sparse when changes were committed directly to `main`; keep `CHANGELOG.md` as the authoritative user-facing release content.
