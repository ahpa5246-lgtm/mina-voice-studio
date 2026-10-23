# Security and privacy

Mina Voice Studio is an **alpha local-development application**. It runs on `127.0.0.1:7860` by default. **Do not expose it to the public internet** or deploy it as a multi-user service: it does not provide account authentication, tenant isolation or hardened production upload handling.

## Reporting a vulnerability

Please **do not post exploit details, tokens, sensitive voice data or private files in a public GitHub issue**.

On the repository **Security → Advisories** page, use **Report a vulnerability** if private reporting is enabled. If it is not available, first open a non-sensitive issue requesting a private disclosure channel without including exploit details. Maintainers should use the private channel to coordinate triage and a patch before publishing specifics.

## Voice and model data

- Obtain permission before cloning, converting or training on any person's voice.
- Speaker references and generated media are stored locally. Saved references persist until deleted.
- Job cleanup occurs during later job admission after the configured retention period; it is **not a secure-delete service**.
- External models can download weights on first run. Verify checkpoint source, license and Python dependencies.
- Do not upload secrets, speaker embeddings, identifying recordings or full local file paths in GitHub issues or test fixtures.
