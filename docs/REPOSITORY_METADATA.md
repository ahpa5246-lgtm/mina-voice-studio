# GitHub repository metadata

The README, issue templates and release workflow are committed in this repository. **Repository description and topics are settings** requiring repository-administration access, which the connected integration does not expose.

An owner using [GitHub CLI](https://cli.github.com/) can apply the prepared settings:

```bash
bash scripts/configure_github_metadata.sh
```

**Description:** Open-source AI voice acting studio for cartoons: design character voices, generate dialogue, export WAV/SRT with Qwen3-TTS, Chatterbox and Applio.

**Topics:** `text-to-speech`, `voice-cloning`, `ai-voice`, `voice-conversion`, `animation`, `cartoon`, `qwen3-tts`, `chatterbox-tts`, `rvc`, `open-source`.

**Verify:** Refresh the repository homepage or run `gh repo view ahpa5246-lgtm/mina-voice-studio --json description,repositoryTopics`. Never mark these settings completed until GitHub reflects them.
