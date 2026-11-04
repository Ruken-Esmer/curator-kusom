# MİMAR — technical notes

## Module map (`backend/app/mimar/`)

| File | Responsibility | Application section |
|---|---|---|
| `text.py` | fixed, versioned preprocessing (TR-safe case folding, stop-words, Bloom verbs, light stemming) | §2.6, §3.2 |
| `rankers.py` | BM25 (sparse, exact), embedding (sentence-transformers or local TF-IDF+LSA; FAISS search), concept graph (Adamic–Adar + damped 2-hop), RRF | §3.2 |
| `analysis.py` | analysis config/hash, per-method and hybrid pair lists, content families, family split, stability check | §2.6, §3.3 |
| `sampling.py` | allocation, stratified sampling with inclusion probabilities, AS1 strata incl. unlisted pairs | §3.4, §4.4, §7 |
| `metrics.py` | κ, AC1, weighted detection metrics, cluster bootstrap, H1, ΔMU/H2a, H2b, power simulation, H5, H6 | §2.7 |
| `qc.py` | import parsers and QC with exclusion reasons | §2.1–2.2 |
| `findings.py` | UÇEP correspondence, MİMAR findings (redundancy / gap / integration), matching, blinded pool, validation resolution | §4 |
| `impact.py` | version diff, impact alerts, evaluation against expected effects, controlled scenarios | §8 |
| `store.py` | SQLite documents, content-addressed artifacts, hash-chained audit log | §2.3, §2.6 |
| `security.py` | roles, capabilities, token hashing, independence error | §2.5 |
| `service.py` | the workflow and every protocol gate | all |
| `fake_data.py`, `demo.py` | synthetic MSKL data, simulated raters, full end-to-end run | testing only |

## Protocol gates enforced in code
* analyses only on frozen dataset versions; frozen versions are immutable
* the locked test sample can be drawn once, only after the plan (depth, comparator, thresholds) is locked; the plan lock hash binds config, dataset and split hashes
* list depth and comparator are chosen on development data only (max hybrid F1; PPV then F1)
* reviewers see only the two LO texts in an individual random order; decisions are locked; only disagreements are adjudicated; initial decisions are preserved
* the person who drew a sample cannot review it; report authors cannot standardise; authors/standardiser cannot validate; admin is not a reviewer
* validation pool sources are sealed until every validation decision is final
* expected change effects must be registered and locked before the impact report and are hidden from the technical team

## Performance (single CPU, no GPU)
| LOs | fit | lists + RRF | families | peak RAM |
|---|---|---|---|---|
| 2 000 | 2.2 s | 0.6 s | 0.4 s | 0.28 GB |
| 8 700 | 5.4 s | 8.6 s | 6.1 s | 0.55 GB |

## Known limitations / next steps
* The default embedding backend is a local TF-IDF + LSA model so the system runs fully offline. On the research workstation, install `requirements-optional.txt` and select `sentence-transformers` (or a biomedical model) in the configuration; the model is part of the locked configuration hash.
* The concept extractor is lexicon-free n-gram extraction; a verified MeSH/UÇEP synonym lexicon can be passed via `concept.synonyms`. The secondary MeSH analysis (§3.7) is prepared in the data model (activity-level verified MeSH terms) but not yet a separate ranked list.
* MİMAR findings are template-based and deterministic (required for 5-run stability); an LLM wording layer can be added later as a separately versioned component.
* Authentication uses bearer tokens; on the institutional deployment put the API behind Koç SSO/MFA and TLS.
