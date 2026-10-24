# ثمانية GitHub Issues جاهزة للنسخ وإعطائها للمتطوعين

هذه **مسودات** لا تُفتح تلقائيًا كقضايا عامة. قبل إنشاء أي Issue تأكدي أنها لم تُحل وأن الوسوم موجودة. للتكليف افتحي: https://github.com/ahpa5246-lgtm/mina-voice-studio/issues/new/choose ، ثم انشري الوصف، واطلبي من المساهم التعليق بخطة عمل، وبعد موافقتك يستخدم Fork → PR. لا يحتاج أي مساهم إلى صلاحية Admin.

## 1. docs: first-run Windows troubleshooting with real error messages

**Priority:** P0 · **Difficulty:** beginner · **Suggested labels:** good first issue,documentation.

**Problem:** Users who run start.ps1 may not have Python 3.11 or may be blocked by PowerShell execution policy.

**Scope:** Only docs/INSTALL_AR.md, README.md and tests/test_community_docs.py; no model downloads.

**Implementation plan:**
1. Document Python version verification on Windows PowerShell
2. Show safe manual alternative when start.ps1 is blocked
3. Explain separate UI installation vs Qwen/Chatterbox model weights
4. Include tested commands and language for each expected failure

**Acceptance criteria:**
- [ ] Instructions use actual checked-in script names
- [ ] A user can locate a missing Python error and recover
- [ ] No recommendation to disable all system security globally
- [ ] All existing README/docs tests pass

**Evidence / tests:** Markdown diff + command outputs from a real Windows host if available; otherwise explicitly mark commands untested.

**Out of scope:** Don't invent acoustic benchmarks or add model weights/credentials. Preserve third-party licenses and the founder/community attribution.

**Contributor instructions:** Comment your proposed approach before starting, submit a PR linked to this Issue, and list tested vs untested paths.

---

## 2. a11y: keyboard focus and clear status in Cartoon Cast

**Priority:** P1 · **Difficulty:** beginner/intermediate · **Suggested labels:** help wanted,accessibility.

**Problem:** Multi-speaker dialogue is hard to edit without a mouse; progress/errors need readable status announcements.

**Scope:** studio/static/index.html, studio/static/cast.js, studio/static/style.css, tests/test_browser.py.

**Implementation plan:**
1. Document current Tab order
2. Ensure actionable controls have accessible labels
3. Add visible focus styles without changing actual generation behavior
4. Verify status and errors announced through existing live regions

**Acceptance criteria:**
- [ ] Keyboard can add/remove a dialogue row
- [ ] No new browser exceptions
- [ ] RTL and English UI work
- [ ] Chromium test demonstrates a keyboard-only path

**Evidence / tests:** Before/after screenshots and Playwright command output.

**Out of scope:** Don't invent acoustic benchmarks or add model weights/credentials. Preserve third-party licenses and the founder/community attribution.

**Contributor instructions:** Comment your proposed approach before starting, submit a PR linked to this Issue, and list tested vs untested paths.

---

## 3. test: verify WAV/SRT timestamps and ZIP paths for episode exports

**Priority:** P0 · **Difficulty:** beginner · **Suggested labels:** good first issue,testing.

**Problem:** An animator needs reliable captions and individual audio clips that match their script.

**Scope:** tests/test_episode_workflow.py and studio/cast.py only if a real defect is found.

**Implementation plan:**
1. Create a two/three line PCM fixture
2. Check WAV format, durations and pause bounds
3. Check subtitle order and timestamp monotonicity
4. Check ZIP contains only expected safe relative paths

**Acceptance criteria:**
- [ ] Test fails when deliberately corrupting timestamps
- [ ] Baseline passes on main
- [ ] No fake neural output is claimed
- [ ] No private voice datasets

**Evidence / tests:** Pytest test names and results; sample small generated WAV fixture.

**Out of scope:** Don't invent acoustic benchmarks or add model weights/credentials. Preserve third-party licenses and the founder/community attribution.

**Contributor instructions:** Comment your proposed approach before starting, submit a PR linked to this Issue, and list tested vs untested paths.

---

## 4. models: preflight readiness with exact missing dependency explanations

**Priority:** P0 · **Difficulty:** intermediate · **Suggested labels:** help wanted,engine-integration.

**Problem:** Current engine presence may be confused with successful inference and weights readiness.

**Scope:** scripts/manage_engines.py, studio/verification.py and small UI status changes.

**Implementation plan:**
1. Specify structured JSON states: missing python/package/checkpoint/GPU/locally tested
2. Do not start model download during status check
3. Show actionable recovery commands
4. Retain separation of Chatterbox/Qwen/Applio environments

**Acceptance criteria:**
- [ ] Missing packages yield explicit not-ready state
- [ ] No silent downloads or fabricated WAV
- [ ] Existing verification tests green
- [ ] Document model-specific manual prerequisites

**Evidence / tests:** CPU-only regression test plus optional real GPU run with identifiable hardware.

**Out of scope:** Don't invent acoustic benchmarks or add model weights/credentials. Preserve third-party licenses and the founder/community attribution.

**Contributor instructions:** Comment your proposed approach before starting, submit a PR linked to this Issue, and list tested vs untested paths.

---

## 5. feature: A/B two takes of one Cartoon Cast dialogue line

**Priority:** P1 · **Difficulty:** intermediate · **Suggested labels:** help wanted,cartoon-workflow.

**Problem:** A cartoon director needs to compare two deliveries and choose one without regenerating the whole scene.

**Scope:** studio/cast.py, studio/cast_api.py, studio/static/cast.js, tests/test_episode_workflow.py.

**Implementation plan:**
1. Agree on data model and error semantics in the issue before implementation
2. Render replacement take as new immutable asset
3. Add UI playback for original/alternative
4. Select one and re-export ZIP/SRT while leaving original intact

**Acceptance criteria:**
- [ ] Both takes playable separately
- [ ] Original episode remains identical
- [ ] Only target line sent to neural engine
- [ ] Tests cover missing model and corrupt WAV

**Evidence / tests:** Browser and API test logs + licensed/demo speech if GPU tests are claimed.

**Out of scope:** Don't invent acoustic benchmarks or add model weights/credentials. Preserve third-party licenses and the founder/community attribution.

**Contributor instructions:** Comment your proposed approach before starting, submit a PR linked to this Issue, and list tested vs untested paths.

---

## 6. research: independent Arabic Chatterbox QA benchmark

**Priority:** P0 · **Difficulty:** advanced/GPU · **Suggested labels:** help wanted,evaluation.

**Problem:** Qwen Kaggle evidence doesn't validate Arabic voice quality or Chatterbox.

**Scope:** scripts/verify_real_audio.py, docs/EVALUATION.md; own benchmark dataset outside Git unless redistribution permitted.

**Implementation plan:**
1. Define 10 short Arabic phrases without private voice data
2. Run official Chatterbox checkpoint with versions and exact GPU model
3. Collect WAV hashes, RTF, measured clipping and optional ASR WER/CER
4. Describe limitations of ASR and solicit consented blind listening

**Acceptance criteria:**
- [ ] Every result points to real generated WAV
- [ ] Failed inference is reported failed
- [ ] No comparison to commercial services without matched test
- [ ] Model/checkpoint licenses documented

**Evidence / tests:** Report JSON, reproducible commands, human listening summary when available.

**Out of scope:** Don't invent acoustic benchmarks or add model weights/credentials. Preserve third-party licenses and the founder/community attribution.

**Contributor instructions:** Comment your proposed approach before starting, submit a PR linked to this Issue, and list tested vs untested paths.

---

## 7. security: local upload and path validation audit

**Priority:** P0 · **Difficulty:** advanced · **Suggested labels:** help wanted,security.

**Problem:** Local-first UI must not accidentally become a production-open service or expose uploads/temporary paths.

**Scope:** studio/app.py, API handlers, SECURITY.md, security tests.

**Implementation plan:**
1. Write threat model for local uploads and directory traversal
2. Design regression tests using sanitized fixtures
3. Fix validated defects in a scoped PR
4. Report sensitive exploit details privately first

**Acceptance criteria:**
- [ ] No arbitrary local file access through artifact URLs
- [ ] No secrets logged
- [ ] Limit controls are explicit
- [ ] Tests pass without external network/GPU

**Evidence / tests:** Sanitized test output; private security reporting for exploitable bugs.

**Out of scope:** Don't invent acoustic benchmarks or add model weights/credentials. Preserve third-party licenses and the founder/community attribution.

**Contributor instructions:** Comment your proposed approach before starting, submit a PR linked to this Issue, and list tested vs untested paths.

---

## 8. docs: complete Arabic-English contributor walkthrough

**Priority:** P1 · **Difficulty:** beginner · **Suggested labels:** good first issue,documentation.

**Problem:** First-time contributors need clear examples from a new branch to a reviewed PR.

**Scope:** CONTRIBUTING.md, docs/community/04_ISSUE_ASSIGNMENT_AND_REVIEW_AR.md.

**Implementation plan:**
1. Create an end-to-end beginner walkthrough
2. Clarify what tests run without GPU
3. Link 3 existing suitable Issues without claiming they remain open forever
4. Add troubleshooting for failed tests and an example PR body

**Acceptance criteria:**
- [ ] A new contributor can follow steps without maintainer write access
- [ ] Instructions include fork, branch, test and PR
- [ ] Security note for recording/token exclusions
- [ ] No broken internal links

**Evidence / tests:** Peer walkthrough / screenshot and docs test.

**Out of scope:** Don't invent acoustic benchmarks or add model weights/credentials. Preserve third-party licenses and the founder/community attribution.

**Contributor instructions:** Comment your proposed approach before starting, submit a PR linked to this Issue, and list tested vs untested paths.

---

