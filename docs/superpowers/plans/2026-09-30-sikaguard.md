# sikaguard v0.1.0.dev0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Execution method chosen by the author: **Native** (the user asked for no further questions and a working result; the plan is executed inline, TDD per task, one commit per task).

**Goal:** Build a working, tested, documented French/West-African SMS scam detector (library + CLI + API + Docker + demo) with a data pipeline and an honest evaluation, trained on a clearly-labelled seed dataset.

**Architecture:** A runtime package `sikaguard` (normalization → expert signals + TF-IDF → two-stage logistic regression → explanations) that ships a skops model with a SHA-256-checked manifest; a non-shipped `sikaguard_lab` package (schema validation, dedup/grouping, anti-leak split, training, evaluation, robustness); a FastAPI app as an optional extra; a Gradio demo outside the package.

**Tech Stack:** Python ≥ 3.10, scikit-learn, numpy, scipy, skops; FastAPI/uvicorn (extra `api`); Gradio (demo); pytest, hypothesis, pytest-cov, ruff, mypy; hatchling; GitHub Actions; Docker.

**Spec:** `docs/superpowers/specs/2026-09-30-sikaguard-design.md`

## Global Constraints

- Python `>=3.10`; runtime deps limited to `scikit-learn`, `numpy`, `scipy`, `skops`.
- Never use `pickle`/`joblib` for the model; `skops` with an explicit allow-list; SHA-256 verified before load.
- Labels: `arnaque` | `legitime`; verdicts: `arnaque` | `suspect` | `legitime`.
- Scam categories: `faux_transfert`, `usurpation_operateur`, `faux_gain`, `phishing_lien`, `investissement_emploi`, `autre_arnaque`; legit: `notification_transaction`, `otp`, `promo_operateur`, `personnel`.
- Placeholders: `<TEL>`, `<NOM>`, `<REF>`, `<CODE>`, `<EMAIL>`, `<URL>`; published links defanged (`hxxp`, `[.]`).
- The exact same `pii`/`normalize` code is used by the dataset pipeline and at inference.
- API text length 1–1 000 chars; batch ≤ 100; SMS text never logged.
- Seed-trained model version `0.1.0.dev0`, flagged "not for production" in manifest, report and model card.
- No operator logos/branding; "independent project, not affiliated" notice in README and demo.
- Coverage ≥ 90 % on `src/sikaguard`; ruff clean; mypy strict clean on `src/sikaguard`.

## Review Focus

1. Empty, whitespace-only, emoji-only or punctuation-only input → library raises `ValueError` for empty/whitespace, returns a normal `Result` (no crash) for emoji-only; API returns 422 for empty. (Task 7, Task 12)
2. Input longer than 1 000 chars → API 422 with explicit message; library still analyzes. (Task 7, Task 12)
3. Tampered, missing or truncated model file → `ModelIntegrityError` with a clear message, never deserialization of untrusted content. (Task 6)
4. CLI on a Windows `cp1252` console printing accents/emojis → no `UnicodeEncodeError`. (Task 7)
5. Concurrent first calls to `analyze()` from several threads → model loaded exactly once, no race. (Task 7)

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | build (hatchling), deps, extras `api`/`dev`/`demo`, ruff/mypy/pytest/coverage config, `sikaguard` console script |
| `src/sikaguard/pii.py` | find/refang/defang URLs; mask phones, emails, refs, codes (shared by dataset + inference) |
| `src/sikaguard/normalize.py` | `normalize(text, *, enabled=True) -> str` anti-evasion normalization |
| `src/sikaguard/urls.py` | `UrlInfo`, `inspect_url(url)` (shortener, IP, punycode, suspicious TLD, lookalike brand) |
| `src/sikaguard/signals.py` | `SIGNALS`, `SIGNAL_CODES`, `detect_signals(text, *, normalized=None) -> list[str]`, `SIGNAL_MESSAGES` |
| `src/sikaguard/features.py` | sklearn transformers `TextNormalizer`, `SignalTransformer`; `build_features(normalize=True) -> FeatureUnion` |
| `src/sikaguard/explain.py` | `top_terms(pipeline, text, *, toward, k=3) -> list[str]` |
| `src/sikaguard/result.py` | `Reason`, `Result` dataclasses, `ADVICE` |
| `src/sikaguard/model.py` | `ModelIntegrityError`, `Manifest`, `LoadedModel`, `save_model`, `load_model`, `ALLOWED_TYPES` |
| `src/sikaguard/analyzer.py` | `Analyzer`, `analyze`, lazy thread-safe default model |
| `src/sikaguard/cli.py` | `main(argv=None) -> int` |
| `src/sikaguard/api.py` | FastAPI `create_app()`, `app` (extra `api`) |
| `src/sikaguard_lab/schema.py` | enumerations, `read_csv`, `write_csv`, `validate_rows` |
| `src/sikaguard_lab/dedup.py` | `shingles`, `jaccard`, `drop_exact_duplicates`, `assign_groups` |
| `src/sikaguard_lab/split.py` | `group_stratified_split` |
| `src/sikaguard_lab/build.py` | `python -m sikaguard_lab.build` → `data/processed/dataset.csv`, `stats.json` |
| `src/sikaguard_lab/train.py` | `python -m sikaguard_lab.train` → `src/sikaguard/assets/` |
| `src/sikaguard_lab/perturb.py` | adversarial perturbations |
| `src/sikaguard_lab/evaluate.py` | `python -m sikaguard_lab.evaluate` → `reports/metrics.json`, `reports/evaluation.md` |
| `data/seed/seed_sms.csv` | seed dataset (amorçage) |
| `demo/app.py`, `demo/render.py` | Gradio demo + pure HTML rendering |
| `Dockerfile`, `.dockerignore` | API image |
| docs & community files | README(.fr), datasheet, model card, annotation guide, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, CITATION.cff, ROADMAP, CHANGELOG, LICENSE, CI, issue form |

---

### Task 1: Scaffolding and tooling

**Files:** Create `pyproject.toml`, `.gitignore`, `LICENSE`, `src/sikaguard/__init__.py` (version only), `src/sikaguard/py.typed`, `src/sikaguard_lab/__init__.py`, `tests/test_smoke.py`.

- [ ] Write `tests/test_smoke.py`: `import sikaguard; assert sikaguard.__version__ == "0.1.0.dev0"`.
- [ ] Create venv `.venv`, `pip install -e ".[dev,api]"`; run `pytest` → FAIL before `__init__` exists, PASS after.
- [ ] `ruff check .` and `mypy` pass on the empty package.
- [ ] Commit `chore: scaffold project`.

### Task 2: PII masking and URL helpers (`pii.py`)

**Produces:** `find_urls(text) -> list[str]`, `refang(text) -> str`, `defang(text) -> str`, `mask_urls(text, token="<URL>") -> str`, `mask_phones(text, token="<TEL>") -> str`, `mask_emails(text, token="<EMAIL>") -> str`, `mask_refs(text, token="<REF>") -> str`, `mask_codes(text, token="<CODE>") -> str`, `anonymize(text) -> str` (emails, URLs defanged not masked, phones, refs, codes — for the dataset), `PHONE_DIGITS_RE` helper `has_phone_number(text) -> bool`.

- [ ] Failing tests (`tests/test_pii.py`):
  - phones: `"+225 07 08 09 10 11"`, `"0022507080910 11"`, `"07.08.09.10.11"`, `"+221 77 123 45 67"`, `"70 12 34 56"`(8 digits) → `<TEL>`; amounts `"25 000 FCFA"`, `"10000000 F"`, `"1 500 000 FCFA"` untouched; dates `"12/05/2025"` untouched.
  - Hypothesis: any generated CI/SN/BF/ML number in any separator style embedded in text → `has_phone_number(mask_phones(t))` is `False`.
  - codes: `"Votre code est 483920"` → `"Votre code est <CODE>"`; `"solde 125000 FCFA"` untouched; `"en 2025"` untouched.
  - refs: `"Ref: MP240930.1234.C56789"` → `"Ref: <REF>"`.
  - urls: `"hxxp://orange-bonus[.]xyz/gain"` found after `refang`; `defang("http://a.com")=="hxxp://a[.]com"`; `find_urls("bit.ly/abc et www.x.com")` finds both; `"M. Kone."` finds nothing.
  - emails: `"ecrire a jean.kone@gmail.com"` → `<EMAIL>`.
- [ ] Run → FAIL; implement; run → PASS; commit `feat: pii masking and url helpers`.

### Task 3: Normalization (`normalize.py`)

**Consumes:** `pii.*`. **Produces:** `normalize(text: str, *, enabled: bool = True) -> str` (disabled → `text.lower()` only).

- [ ] Failing tests (`tests/test_normalize.py`), each `normalize(x) == y`:
  - `"0range M0ney"` → `"orange money"`; `"c0de s3cret"` → `"code secret"`; `"Оrange"` (Cyrillic О) → `"orange"`; `"c o d e"` → `"code"`; `"URGEEEENT"` → `"urgeent"`; `"Félicitations"` → `"felicitations"`; `"fél​icitations"` → `"felicitations"`; `"gag🎉né"` → `"gagne"`; `"25000F"` stays `"25000f"`; `"1ère"` → `"1ere"`; `"appelez +225 0708091011"` → `"appelez <tel>"`; `"hxxps://bit[.]ly/x"` → `"<url>"`; `"<TEL>"` → `"<tel>"`; idempotence `normalize(normalize(x)) == normalize(x)` on a list; `normalize("x", enabled=False)` lowercases only.
- [ ] Run → FAIL; implement; run → PASS; commit `feat: anti-evasion normalization`.

### Task 4: URL inspection and expert signals (`urls.py`, `signals.py`)

**Produces:** `UrlInfo(host: str, is_shortener: bool, is_ip: bool, is_punycode: bool, suspicious_tld: bool, brand_lookalike: bool)`, `.is_suspect`; `inspect_url(url) -> UrlInfo`; `SIGNAL_CODES: tuple[str, ...]` (15 codes of spec §4.2, fixed order); `SIGNAL_MESSAGES: dict[str, str]`; `detect_signals(text: str, *, enabled_normalization: bool = True) -> list[str]` (codes in `SIGNAL_CODES` order).

- [ ] Failing tests: `inspect_url("hxxp://bit[.]ly/x")` shortener; `"http://41.202.10.5/login"` IP; `"orange-money-bonus.xyz"` suspicious + lookalike; `"www.orange.ci"` not suspect. For each signal one positive and one negative example, notably:
  - `demande_code_secret` positive `"Envoyez votre code secret au <TEL>"`, negative `"Ne communiquez jamais votre code secret."`
  - `frais_a_payer` positive `"payez les frais de dossier de 5000F"`, negative `"Frais: 100 FCFA."`
  - `demande_renvoi_argent` positive `"je vous ai envoyé par erreur 25000F, renvoyez svp"`.
  - `majuscules_excessives` positive `"VOTRE COMPTE EST BLOQUE"`.
  - Every code in `SIGNAL_CODES` has a message.
- [ ] Run → FAIL; implement; → PASS; commit `feat: url inspection and expert signals`.

### Task 5: Result, features and explanation (`result.py`, `features.py`, `explain.py`)

**Produces:** `Reason(code, message)`, `Result(verdict, score, category, category_score, reasons, advice, model_version)` + `to_dict()`, `is_scam`; `ADVICE: dict[str, str]` keyed by category and by `"suspect"`/`"legitime"`; `TextNormalizer(normalize=True)`, `SignalTransformer(normalize=True)` (fit/transform/get_feature_names_out); `build_features(normalize: bool = True) -> FeatureUnion` with blocks `chars` (char_wb 2–5, sublinear), `words` (1–2, token pattern `<[a-z]+>|\b\w\w+\b`), `signals`; `top_terms(pipeline, text, *, toward: int, k: int = 3) -> list[str]` (word features only, no placeholders).

- [ ] Failing tests: `SignalTransformer().fit_transform([...])` shape `(n, 15)`; `build_features()` feature names start with `chars__`/`words__`/`signals__`; fit a tiny LR pipeline on 6 texts and assert `top_terms(..., toward=1)` returns words from scam texts; `Result.to_dict()` JSON-serializable; `ADVICE` covers every category.
- [ ] Run → FAIL; implement; → PASS; commit `feat: feature extraction and explanations`.

### Task 6: Secure model persistence (`model.py`)

**Produces:** `ModelIntegrityError(RuntimeError)`, `Manifest` (dataclass: `model_version, dataset_version, sklearn_version, threshold_high, threshold_low, sha256, categories, created_at, not_for_production`), `LoadedModel(binary, category, manifest)`, `save_model(binary, category, directory, *, model_version, dataset_version, threshold_high, threshold_low, not_for_production) -> Manifest`, `load_model(directory=None) -> LoadedModel`, `DEFAULT_MODEL_DIR`.

- [ ] Failing tests (`tests/test_model.py`, tiny models in `tmp_path`): round-trip; flipping one byte of `model.skops` → `ModelIntegrityError` mentioning "SHA-256"; missing file → `ModelIntegrityError`; missing manifest → `ModelIntegrityError`; untrusted type not in allow-list (monkeypatched `ALLOWED_TYPES`) → `ModelIntegrityError`; sklearn version mismatch → `UserWarning`.
- [ ] Run → FAIL; implement; → PASS; commit `feat: skops persistence with integrity check`.

### Task 7: Analyzer, public API and CLI (`analyzer.py`, `__init__.py`, `cli.py`)

**Produces:** `Analyzer(threshold_high=None, threshold_low=None, model=None)`, `.analyze(text) -> Result`, `.analyze_batch(texts) -> list[Result]`, `.info() -> dict`; module-level `analyze(text) -> Result`; `sikaguard.__all__ = ["analyze", "Analyzer", "Result", "Reason", "ModelIntegrityError", "__version__"]`; `cli.main(argv) -> int`.

- [ ] Failing tests using a tiny fixture model saved in `tmp_path`: verdict thresholds (score ≥ high → `arnaque`, < low → `legitime`, else `suspect`); invalid thresholds (`low > high`, outside [0,1]) → `ValueError`; `analyze("")`/`"   "` → `ValueError`; `analyze(42)` → `TypeError`; emoji-only text → `Result`; category is `None` when verdict `legitime`; reasons include triggered signal codes; batch equals individual calls; 8 threads calling the default `analyze` concurrently → loader invoked once (monkeypatched counter); CLI `--json` prints parseable JSON, `-f` file mode, `--version`; CLI with `PYTHONIOENCODING=cp1252` subprocess printing emoji input → exit 0.
- [ ] Run → FAIL; implement; → PASS; commit `feat: analyzer, public api and cli`.

### Task 8: Dataset tooling (`sikaguard_lab.schema`, `dedup`, `split`, `build`)

**Produces:** `COLUMNS`, `RAW_COLUMNS`, `read_csv(path) -> list[dict[str,str]]`, `write_csv(path, rows, columns)`, `validate_rows(rows, *, raw=True) -> list[str]`; `shingles(text, k=5) -> set[str]`, `jaccard(a, b) -> float`, `drop_exact_duplicates(rows) -> tuple[list, int]`, `assign_groups(texts, threshold=0.8) -> list[int]`; `group_stratified_split(labels, groups, *, test_size=0.2, seed=42) -> list[str]`; `build.main(argv) -> int`.

- [ ] Failing tests: validator flags missing column, bad label, category/label mismatch, unmasked phone, empty and > 1000-char text; `assign_groups` puts near-identical scams in one group and different ones apart; split: no group in both splits, both labels in test, ~20 % test; `build.main` on a tmp seed writes dataset + stats with `id`, `group_id`, `split`.
- [ ] Run → FAIL; implement; → PASS; commit `feat: dataset validation, grouping and anti-leak split`.

### Task 9: Seed dataset and annotation guide

**Files:** `data/seed/seed_sms.csv` (~170 scams across 6 categories, ~230 legit across 4 categories incl. hard negatives: legit messages mentioning "code secret" warnings, "bloqué", "urgent", personal money requests), `docs/annotation_guide.md`.

- [ ] `python -m sikaguard_lab.build` → exit 0, validator clean, stats printed; every scam category ≥ 15 rows.
- [ ] Commit `data: add seed dataset (amorçage) and annotation guide`.

### Task 10: Training (`sikaguard_lab.train`) and behavioral tests

**Produces:** `choose_thresholds(y_true, scores, *, min_precision=0.95, min_recall=0.95) -> tuple[float, float]`; `build_binary_pipeline(normalize=True, C=...)`, `build_category_pipeline(...)`; CLI writes `src/sikaguard/assets/{model.skops,manifest.json}`.

- [ ] Failing unit tests for `choose_thresholds` (perfectly separable scores → high ≥ low; guarantees precision/recall on the given data).
- [ ] Implement, train, commit assets.
- [ ] Behavioral tests on the bundled model (`tests/test_behavior.py`): canonical scams per category → `arnaque`; canonical legit notification/OTP/personal → `legitime`; invariance (amount/name changes keep verdict); direction (appending "envoie ton code secret au <TEL>" raises score); leetspeak/homoglyph variant of a scam keeps verdict ≠ `legitime`.
- [ ] Commit `feat: training pipeline and bundled seed model`.

### Task 11: Evaluation and robustness (`perturb.py`, `evaluate.py`)

**Produces:** perturbations `leetspeak, homoglyphs, spaced_letters, strip_accents, upper, emojis, zero_width` (all `(text, rng) -> str`), `PERTURBATIONS: dict[str, Callable]`; `bootstrap_ci(metric, y, s, n=1000, seed=0)`; `python -m sikaguard_lab.evaluate` → `reports/metrics.json`, `reports/evaluation.md` (benchmark B0–B4 CV + test with CIs, per-source, per-category F1, error list, robustness with/without normalization, seed-data disclaimer).

- [ ] Failing tests: each perturbation changes the text but keeps it non-empty and deterministic under a fixed seed; `bootstrap_ci` returns `(low, point, high)` with `low ≤ point ≤ high`.
- [ ] Implement; run evaluation; commit reports `feat: benchmark, bootstrap CIs and adversarial robustness`.

### Task 12: REST API and Docker

**Produces:** `create_app(analyzer: Analyzer | None = None) -> FastAPI`; routes `POST /v1/analyze`, `POST /v1/analyze/batch`, `GET /v1/info`, `GET /health`.

- [ ] Failing tests (`tests/test_api.py`, `TestClient`): 200 + schema; empty/whitespace → 422; 1 001 chars → 422; batch 101 → 422; `/v1/info` has versions; `/health` ok; `caplog` never contains the submitted text; unexpected exception → 500 `{"detail": "Internal server error"}`.
- [ ] Implement; `Dockerfile` (python:3.12-slim, non-root, HEALTHCHECK); `docker build` + `docker run` + `curl /health` if Docker daemon available.
- [ ] Commit `feat: rest api and docker image`.

### Task 13: Demo

**Produces:** `demo/render.py: render_result(result: Result) -> str` (HTML, escaped), `demo/app.py` (Gradio Blocks, examples, privacy banner, report link, non-affiliation notice), `demo/requirements.txt`.

- [ ] Failing test: `render_result` escapes `<script>` in reasons, contains verdict label.
- [ ] Implement; launch locally and check in browser.
- [ ] Commit `feat: gradio demo`.

### Task 14: Documentation, community files, CI

- [ ] README.md (EN) + README.fr.md, `docs/datasheet.md`, `docs/model_card.md` (numbers from `reports/metrics.json`), CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, CITATION.cff, ROADMAP, CHANGELOG, `.github/workflows/{ci,release}.yml`, `.github/dependabot.yml`, `.github/ISSUE_TEMPLATE/nouvelle-arnaque.yml`, `Makefile`.
- [ ] Commit `docs: documentation, community files and ci`.

### Task 15: Final verification

- [ ] `ruff check .`, `ruff format --check .`, `mypy`, `pytest --cov` (≥ 90 %), `pip-audit`, `python -m build`, install wheel in a fresh venv and run `sikaguard "..."`, Docker smoke test. Record results; fix anything red.
