# Roadmap

## v0.1.0 — first real data (next)

- [ ] Collect ≥ 300 confirmed scam SMS from public sources (operator and authority
      alerts, press, social-media reports) following the [annotation guide](docs/annotation_guide.md).
- [ ] Verify the license of the 88milSMS research corpus for legitimate personal SMS;
      cap it at 40 % of the legitimate class to avoid dialect/era bias.
- [ ] Re-annotate 10 % of each batch after one week; publish Cohen's kappa.
- [ ] Fix the known false positives found in the `0.1.0.dev0` error analysis, and
      validate the fixes on the **new** test split:
  - *money request* signal fires on refund notifications (`rembours-`);
  - *secret code request* signal fires on OTPs saying "code … pour confirmer".
- [ ] Freeze the new test split, re-run the pre-registered objectives, publish the
      dataset on Hugging Face (datasheet, CC BY 4.0) and the package on PyPI.
- [ ] Deploy the demo as a Hugging Face Space.

## Later

- Code-switching and local languages (Nouchi, Wolof, Dioula, Bambara).
- A French CamemBERT-family model as a benchmark, kept only if it beats the linear
  model on the real test split **and** stays explainable enough.
- WhatsApp / Telegram bot that answers "is this a scam?".
- Android SMS-filter demo app (on-device, no data leaves the phone).
- Temporal evaluation: train on older scams, test on newer ones (scams evolve).
