# Speech quality, training and release acceptance

**Current status:** The project has adapter code and HTTP/unit tests. It does **not** include a trained voice model, new checkpoints, permissioned speaker corpus, or evidence that it matches ElevenLabs quality.

## Model-quality acceptance protocol

1. Collect permissioned Arabic MSA, Iraqi dialect and English test speakers. Record clean 16–24kHz+ speech, consent, exact transcripts, and train/validation/test splits by speaker. Keep personal recordings off the public repository.
2. Generate identical held-out sentences from each engine (Chatterbox V3, Applio voice conversion, future installed engines) and a licensed commercial reference only if terms permit.
3. Measure **WER/CER** with an independent speech recognizer and report model, version, language, and dataset. Human annotation is required for dialect spelling and code-switching.
4. Measure speaker similarity with a frozen speaker-verification model on **held-out** speakers; report uncertainty. No model can guarantee an exact copy of any individual's voice.
5. Conduct blinded paired listener tests of naturalness, accent, intelligibility and preference. Recruit native Iraqi Arabic and MSA listeners separately. Record sample size, intervals, and raw distributions.
6. Track real-time factor on available GPU, VRAM peak, failure rate, clean/dirty sample sensitivity, and long-form drift.
7. Run CLI WAV diagnostics: \`python scripts/quality_report.py generated.wav\`. Silence and clipping reports are engineering signals, **not** speech quality scores.

## Training gate (not yet passed)

Fine-tuning cannot begin responsibly until a legally usable and auditable training dataset exists, the model's own weight license allows it, a reproducible training recipe exists, and GPU/storage are available. For an RVC voice, prefer Applio's upstream supported training procedure instead of inventing a custom checkpoint format. Chatterbox V3 training support and hyperparameters must be independently verified before claiming in-repository fine-tuning.

Before training: version datasets, consent records, baseline audio, random seeds, model revisions, compute time and evaluation splits. Do not train on celebrities, public figures, or other third-party speakers without appropriate authorization.

## Release quality gates

- Unit and API regression tests green on Python 3.11 / 3.12
- JavaScript syntax and static UI checks green
- Local browser interaction and responsive accessibility checks
- At least 50 Arabic, 50 Iraqi dialect and 50 English held-out synthesis examples with verified outputs
- No severe clipping or silent audio; track WAV metrics across runs
- Run real RVC conversion with at least 2 licensed speakers and Chatterbox V3 with 2 languages
- Document GPU, inference speed, VRAM use and frequent failures
- Separate disclosure of all limitations rather than a blanket «flawless» claim

## Security notes

Loopback-only hosting, allowed hosts, origin checks and bounded queues reduce local exposure. This is not a public authenticated SaaS. Do not make the HTTP listener publicly reachable without an authentication layer, rate limiting, encryption at rest, data retention controls and abuse investigation.
