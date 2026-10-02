# data/eval — benchmarks never used for training

| File | Rows | Content |
|---|---|---|
| `88milsms_eval.csv` | 1 000 | real French personal SMS (88milSMS, CC BY 4.0), all legitimate: measures false alarms |
| `afrique_reel.csv` | 23 | real West- and Central-African messages quoted verbatim: 19 scams, 4 Mobile Money notifications |

Both are read by `python -m sikaguard_lab.evaluate`. Neither may be used to tune a model:
once a version has been evaluated on a benchmark, the next version can train on it only
if a new, blind benchmark replaces it.

## `afrique_reel.csv`

No public dataset of real West-African scam SMS exists (Hugging Face, Kaggle, Zindi,
GitHub and research papers were searched in September–October 2026). This file gathers
the real messages that can be cited with their source:

- **Scams (19)**: texts quoted word for word in fact-checks by
  [PesaCheck](https://pesacheck.org) (Code for Africa), where the impersonated operator,
  bank or government denied the offer, and one fake MTN Mobile Money credit SMS published
  by the Cameroonian site StopBlaBlaCam (2018). Countries: Cameroon 6, Guinea 5, Côte
  d'Ivoire 3, Benin 2, Burkina Faso 1, Senegal 1, Mali 1.
- **Legitimate (4)**: real Mobile Money receipts from Burkina Faso (Orange Money, Moov
  Money, Telecel Money) found in the tests of
  [kulturman/mobile-money-sms-parser](https://github.com/kulturman/mobile-money-sms-parser)
  (MIT License, Copyright (c) 2026 Arnaud). Only messages with real-looking identifiers
  were kept; synthetic test strings (`TEST-001`, `NOM PRENOM`) were left out.

Extra columns: `canal` (`sms`, `site_web`, `facebook`, `tiktok`, `instagram`) and
`citation` (`exacte` for the whole quoted text, `extrait` when the source quotes or the
file keeps only part of it). Most scams here are the text of phishing pages or social
posts, not SMS: they share the vocabulary of SMS scams but not always their form.

Anonymisation: names, phone numbers and transaction ids of private persons are replaced
by `<NOM>`, `<TEL>` and `<REF>`; links are defanged (`hxxps://`, `[.]`). Public figures
whose identity the scam impersonates (presidents, a minister) keep their name, as in the
fact-checks. The quotes are short and kept for research and evaluation, with their source
on every row; the copyright of the articles stays with their authors.
