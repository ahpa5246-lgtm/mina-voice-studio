#!/usr/bin/env bash
# Run with an account authorized to edit this repository's metadata.
# The connected GitHub API here does not expose repository settings mutation.
set -euo pipefail

repo='ahpa5246-lgtm/mina-voice-studio'
description='Open-source AI voice acting studio for cartoons: design character voices, generate dialogue, export WAV/SRT with Qwen3-TTS, Chatterbox and Applio.'
topics='{"names":["text-to-speech","voice-cloning","ai-voice","voice-conversion","animation","cartoon","qwen3-tts","chatterbox-tts","rvc","open-source"]}'

if ! command -v gh >/dev/null 2>&1; then
  echo 'Install GitHub CLI (https://cli.github.com/) and authenticate with gh auth login.' >&2
  exit 1
fi

gh auth status >/dev/null
gh repo edit "$repo" --description "$description"
printf '%s\n' "$topics" | gh api --method PUT "repos/$repo/topics" \
  --header 'Accept: application/vnd.github+json' --input -

echo 'Repository metadata updated successfully:'
gh repo view "$repo" --json description,repositoryTopics
