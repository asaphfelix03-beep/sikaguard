# Contributing to sikaguard

Thank you! Contributions in French or English are welcome.

## 1. Data (the most valuable contribution)

Report a scam SMS with the
[issue form](https://github.com/asaphfelix03-beep/sikaguard/issues/new?template=nouvelle-arnaque.yml).
Remove every personal detail first (`<TEL>`, `<NOM>`, `<CODE>`, `<REF>`). Maintainers
review each report against the [annotation guide](docs/annotation_guide.md) before it
enters a dataset version.

## 2. Code

```bash
git clone https://github.com/asaphfelix03-beep/sikaguard && cd sikaguard
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev,api]"
pytest && ruff check . && ruff format --check . && mypy
```

Rules:

- Tests first: every behavior change comes with a test (`tests/`).
- `ruff`, `ruff format` and `mypy --strict` (on `src/sikaguard`) must pass; coverage
  stays ≥ 90 %.
- Never log, print or store SMS text in library or API code.
- Never load models with `pickle`/`joblib`; use `sikaguard.model.load_model`.
- **Do not tune anything on the test split.** Model and threshold choices use
  cross-validation on the train split only.
- If you change `normalize`, `pii` or `signals`, retrain (`python -m sikaguard_lab.train`)
  and re-run the evaluation; commit the updated `src/sikaguard/assets/` and `reports/`.

## 3. Pull requests

Small and focused, with a clear description of *why*. Mention any change in the
evaluation numbers. By contributing you agree that your code is released under the MIT
license.
