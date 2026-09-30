# data/raw — private

This folder holds raw collected SMS **with their detailed provenance** (URLs of
social-media posts, screenshots). Everything here except this README is ignored
by git and must never be published. Only the anonymized, validated output of
`python -m sikaguard_lab.build` (in `data/processed/`) is public.

Files placed here must follow the raw schema documented in
`docs/annotation_guide.md` (same columns as `data/seed/seed_sms.csv`).
