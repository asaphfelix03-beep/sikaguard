# data/history — consumed test splits

A test split can be used **once**. After its errors have been read, it is
"consumed": its rows are archived here and `python -m sikaguard_lab.build
--consumed <file>` forces them (and their whole near-duplicate group) into the
train split of every later version.

| File | Version | Consumed on | Why |
|---|---|---|---|
| `test_0.1.0.dev0.csv` | 0.1.0.dev0 | 2026-10-01 | errors analysed in `reports/history/0.1.0.dev0/evaluation.md` |
| `test_0.1.0.dev1.csv` | 0.1.0.dev1 | 2026-10-02 | errors analysed in `reports/history/0.1.0.dev1/evaluation.md` |
