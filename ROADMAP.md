# Roadmap

## Done in 0.1.0.dev1

- [x] Real legitimate SMS: 88milSMS corpus (CC BY 4.0) checked, sampled, capped at 40 %
      of the legitimate class; 1 000 more messages kept as an external benchmark.
- [x] 12 real, dated scam campaigns from Côte d'Ivoire and Senegal documented and
      reconstructed with their sources; campaign-level split.
- [x] Fixed the two false-positive rules found in the dev0 error analysis
      (refunds, "code … pour confirmer").
- [x] Latency below 10 ms p95 per SMS.

## Done in 0.1.0.dev2

- [x] 811 real French scam SMS (IMC'25) with a published human review.
- [x] Balanced dataset (2 063 SMS, 1 611 real); evaluation on real SMS only.

## Done after 0.1.0.dev2

- [x] First real West/Central-African benchmark (23 messages quoted verbatim, sources on
      every row): 73.7 % of scams flagged, 2 of 4 real notifications flagged. It is now
      opened: the next version may train on it only if a new, blind real benchmark
      replaces it.
- [x] First real Ivorian SMS contributed (fake Wave gift on a free host) and a link check
      that recognises brand names in subdomains and on free hosts.

## v0.1.0 — real West-African data (next)

- [ ] Collect ≥ 300 **real** scam SMS from Côte d'Ivoire first (screenshots shared by
      victims, PLCC and operator alerts), following the
      [annotation guide](docs/annotation_guide.md); provenance in `data/raw/` (private).
- [ ] Collect real **legitimate West-African** SMS (operator notifications, personal
      messages, with consent) to reduce the France/2011 bias of 88milSMS.
- [ ] Re-annotate 10 % of each batch after one week; publish Cohen's kappa.
- [ ] Freeze a new test split made of real messages only; re-run the pre-registered
      objectives; flip `not_for_production` only if they hold.
- [ ] Publish the dataset on Hugging Face (datasheet, CC BY 4.0), the package on PyPI,
      the demo as a Hugging Face Space.

## Known limitations to address (validated on the next test split)

- Fake operator gifts written like real promotions ("Orange Money – Célébrons
  l'Assomption ! Recevez 35 000 F CFA"), missed on the real West-African benchmark.
- Real Mobile Money receipts that end with an operator link (Max it) flagged as phishing:
  an allow-list of official operator domains in the link signal.
- Legitimate West-African credits and refunds ("prêt remboursé", "compte crédité")
  flagged after learning from real French refund scams: collect real legitimate
  West-African notifications.
- Scam *type* (80.5 % accuracy): more examples per category, and a category model that
  can say "unknown".
- Marketplace scams that move the conversation to e-mail, without a link.
- Secrecy requests in less common forms ("ne dis rien à papa").
- A dedicated signal for fake-authority threats (fake PLCC agent, fake fines, "arrestation").
- Commercial operator promotions occasionally flagged.

## Later

- Code-switching and local languages (Nouchi, Wolof, Dioula, Bambara).
- A French CamemBERT-family model as a benchmark, kept only if it beats the linear
  model on the real test split **and** stays explainable enough.
- WhatsApp / Telegram bot that answers "is this a scam?".
- Android SMS-filter demo app (on-device, no data leaves the phone).
- Temporal evaluation: train on older scams, test on newer ones (scams evolve).
