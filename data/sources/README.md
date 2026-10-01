# data/sources — real-world material

Two kinds of public, citable material complement the hand-written seed set.

## 1. `88milsms_sample.csv` — real legitimate SMS (150 rows)

Random sample of the **88milSMS** corpus: authentic French SMS collected in 2011
in the Montpellier area and anonymised by their authors.

> Panckhurst R., Détrie C., Lopez C., Moïse C., Roche M., Verine B. (2014).
> *88milSMS. A corpus of authentic text messages in French.* Produced by the
> Université Paul-Valéry Montpellier 3 and the CNRS, in partnership with the
> Université catholique de Louvain. ISLRN 024-713-187-947-8. Distributed by
> Ortolang/CoMeRe under **CC BY 4.0**: <https://hdl.handle.net/11403/comere/cmr-88milsms>

Changes made by sikaguard: name tags (`[_forename_]`, `[_surname_]`,
`[_nickname_]`) → `<NOM>`, `[_tel_]` → `<TEL>`; messages carrying other tags
(address, location, brand, code, e-mail, URL), chain letters, links and
messages shorter than 15 characters were left out. Imported reproducibly with
`python -m sikaguard_lab.import_88milsms` (seed 2011). A disjoint sample of
1 000 messages (`data/eval/88milsms_eval.csv`) is **never** used for training.

Known bias: France, 2011, mostly students. It is capped at 40 % of the
legitimate class and its effect is measured separately in the evaluation.

## 2. `ci_campagnes_documentees.csv` — documented scam campaigns (45 rows)

Real, dated campaigns described by an authority, an operator or the press. The
sources describe the scheme but do **not** reproduce the SMS verbatim, so each
row is a *reconstruction* consistent with the description (`derive_de_modele=true`).
Links are illustrative unless the source published the domain. Rows of one
campaign share a `campagne` id and are never split between train and test.

| `campagne` | Country / date | Scheme | Source |
|---|---|---|---|
| `ci-2026-09-wave-cadeau` | CI 2026-09 | fake 37 000 F Wave gift, form asks number + secret code (PLCC: 503 complaints, 231 M FCFA) | [AIP](https://www.aip.ci/cote-divoire-aip-cybercriminalite-la-plcc-demantele-un-reseau-darnaque-aux-faux-cadeaux-mobile-money/) |
| `ci-2026-08-lien-apk` | CI 2026-08 | attractive offers + link to install an Android APK (PLCC alert) | [KOACI](https://www.koaci.com/article/2026/08/08/cote-divoire/societe/cote-divoire-larnaque-au-mobile-money-par-liens-frauduleux-se-repand-actuellement-ce-quil-faut-faire-pour-eviter-de-tomber-dans-le-piege_199362.html) |
| `ci-2026-04-faux-agent-wave` | CI 2026-04 | fake Wave customer-service agents (San Pedro police) | [AIP](https://www.aip.ci/353937/cote-divoire-aip-la-police-de-san-pedro-met-en-garde-contre-la-recrudescence-des-arnaques-au-mobile-money/) |
| `ci-orange-faux-agent` | CI | fake Orange agents, codes to dial, OTP requests | [Orange CI](https://www.orange.ci/fr/assistance-stop-arnaques-orange-money.html) |
| `ci-orange-demande-aide` | CI | strangers asking for help by SMS | [Orange CI](https://www.orange.ci/fr/assistance-stop-arnaques-orange-money.html) |
| `ci-depot-par-erreur` | CI | "deposit by mistake": check balance, withdraw, send back | [Africa Cybersecurity Mag](https://cybersecuritymag.africa/mobile-money-et-vacances-la-saison-des-arnaques/) |
| `ci-2026-05-recrutement-aeroport` | CI 2026-05 | fake FHB airport recruitment (386 internships, Gmail contact) | [Yessouan](https://www.yessouan.ci/Recrutement-aeroport-Felix-Houphouet-Boigny-FHB-d-Abidjan-une-arnaque-circule-en-ligne-la-PLCC-saisie_a8074.html) |
| `ci-2026-09-recrutement-fonction-publique` | CI 2026-09 | fake direct recruitment (Customs, Taxes, Treasury) | [Yeclo](https://www.yeclo.com/fonction-publique-cote-divoire-une-fausse-offre-de-recrutement-douanes-impots-tresor-denoncee/) |
| `ci-2026-03-concours-eaux-forets` | CI 2026-03 | fake Eaux et Forêts contest admissions | [Kaweru](https://www.kaweru.com/politique-societe/2026/03/23/cote-divoire-concours-des-eaux-et-forets-le-ministere-alerte-sur-des-arnaques-en-ligne/) |
| `ci-2025-02-sunpower` | CI 2025-02 | SUNPOWER solar "investment" platform (PLCC: > 1 000 complaints) | [KOACI](https://www.koaci.com/article/2025/02/17/cote-divoire/societe/cote-divoire-fin-de-parcours-pour-les-arnaqueurs-de-la-plateforme-sunpower-la-plcc-met-en-lumiere-lampleur-des-fraudes-en-ligne_184587.html) |
| `ci-2022-02-faux-plcc` | CI 2022-02 | impersonation of the PLCC itself to collect "fees" | [KOACI](https://www.koaci.com/article/2022/02/05/cote-divoire/societe/cote-divoire-il-cree-un-compte-denomme-plcc-pour-arnaquer-les-victimes-invitees-a-porter-plainte_157432.html) |
| `sn-2026-08-fausses-amendes` | SN 2026-08 | fake traffic fines, domains `amendes-sn[.]click`, `amendsc-sn[.]help` (Police nationale) | [allAfrica](https://fr.allafrica.com/stories/202608080106.html) |
| `ci-officiel-*` (5 rows) | CI | **legitimate** official notices (Fonction publique, Eaux et Forêts, PLCC, Orange): hard negatives | same sources |

Facts were extracted from the articles; no article text is reproduced.
