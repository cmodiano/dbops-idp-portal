# GitHub Actions — IDP Portal

**Important:** GitHub only runs workflows from the **repository root** `.github/workflows/` directory.

The workflows in this folder (`idp-portal/.github/workflows/`) are **not run by GitHub** when the repo root is the parent of `idp-portal/`. They have been **copied to the repo root** (e.g. `../.github/workflows/` or `<repo-root>/.github/workflows/`) with paths adjusted (e.g. `working-directory: idp-portal/django_backend`).

- **CI (lint, typecheck, test, build, security):** use the workflow at **repo root** `.github/workflows/ci.yml`.
- **Pre-commit (mypy + detect-secrets):** run `pre-commit install` from the **repo root** so the root `.pre-commit-config.yaml` is used; it runs mypy on `idp-portal/django_backend` and detect-secrets on `idp-portal/`.

You can keep these copies here as reference or remove them once the root workflows are confirmed working.
