# Stage 14 of 14 — Documentation, Versioning & Distribution

**Source roadmap section covered:** §19 (Documentation, versioning & distribution)
**Depends on:** Stage 13 — Docker images, docker-compose, and the CI pipeline must exist, since the quickstart and packaging depend on them.
**Followed by:** nothing — this is the final build stage. On completion, the framework is ready for its first release.

---

## 1. Project context

**Project:** RAG-implementation → `ragframework`

We are turning a working local RAG proof-of-concept into a distributable framework where adopters bring their own vector database and their own LLM API key. The framework supplies RAG orchestration, backend service scaffolding, a reference frontend, and observability — all runnable on the adopter's own infrastructure, never operated as a hosted service by us.

**Connector scope for the whole build:** only **FAISS** (vector store) and **Google Gemini** (LLM) are implemented. Every other backend (pgvector, Qdrant, Pinecone, Weaviate, OpenAI, Anthropic, etc.) is an intentional, documented extension point — adding one later means writing one new class and registering it, never touching core code. This is the single most important thing for this stage's documentation to communicate clearly, since external adopters will be making build-vs-extend decisions based on how well this is explained.

**Guiding principles (apply throughout):** bring your own backend; interface first, implementation second; sane defaults, everything swappable; observability and reliability built in from day one; the framework is not a hosted service.

**Baseline assumption:** the seven correctness fixes are already applied — this stage's documentation should not describe them as "fixed" in a changelog entry unless they were genuinely fixed within the version being documented; if this build is the first public release, they're simply not mentioned as a fix, since there's no prior public version that had the bug.

**What already exists when this stage starts:** a complete, tested (Stage 12), containerized (Stage 13) framework covering repo structure, connectors, config, API, caching, memory, logging, auth, async ingestion, reliability, observability, frontend, and security hardening (Stages 1–11).

---

## 2. Why this stage exists

A framework nobody can figure out how to install or extend is not meaningfully different from a private script. This stage produces the documentation and packaging that make `ragframework` actually adoptable: a working quickstart, a clear per-connector guide, a versioning discipline that protects adopters from silent breaking changes, and a real publish target.

## 3. README quickstart

Three steps, and it must actually be three steps:

```
pip install ragframework
# fill in .env (see Stage 2's Settings model / example .env)
ragframework serve
```

If getting a working instance running takes more than filling in `.env` and running one command, that's a signal something from Stage 13's `docker compose up` experience didn't make it into the pip-installed path — reconcile the two rather than documenting a rougher pip experience as acceptable just because compose already works well.

## 4. Per-connector setup guide

**One page for "using the FAISS + Gemini defaults,"** structured so a future "using pgvector + OpenAI" page slots in without restructuring the docs. Concretely: use a template structure (connector selection env vars → connector-specific config fields → known limitations of this specific connector pairing → a worked example) that a second connector guide could follow verbatim with different values.

This page is also where the FAISS-specific `allow_dangerous_deserialization=True` constraint (correctness fix #3, carried through Stage 2's docstring and Stage 11's security audit) gets its final, adopter-facing explanation — stated plainly as a known property of this specific connector, not buried in a code comment. Likewise, this page documents FAISS's O(n) `delete()` cost (Stage 2) as a known tradeoff, framed as a reason pgvector/Qdrant are natural next connectors rather than as a defect in the current build.

## 5. Semantic versioning

**A breaking change to `BaseVectorStore` or `BaseLLMProvider` is a major-version bump** — external adopters will be coding against these contracts (both directly, if they write their own connector, and indirectly, through every concrete connector that implements them). Treat any change to either contract's method signatures, required methods, or `from_config()` semantics as breaking, full stop — even a change that seems like it "just adds an optional parameter" needs scrutiny, since a parameter added to an abstract method with no default breaks every existing concrete implementation.

## 6. CHANGELOG.md

Maintained per release. For this build's first release, the changelog's initial entry should summarize the framework's scope as delivered (the two connectors, the backend architecture pieces from Stages 3–9, the reference frontend, security hardening, testing, and deployment artifacts) rather than listing every one of the fourteen internal build stages as if they were independent releases — the stages are a construction sequence, not a release history.

## 7. Packaging

`pyproject.toml` with `extras_require` so a FAISS + Gemini-only install doesn't pull in dependencies for connectors that don't exist yet — this scales cleanly the day a pgvector extra is added (e.g., a future `pip install ragframework[pgvector]`). Structure the base install to include only what FAISS + Gemini + the core framework actually need; anything connector-specific that a future connector would need (a database driver, a different vendor SDK) has no business being a base dependency now, since those connectors don't exist yet.

## 8. Publish target

PyPI, or at minimum a pip-installable GitHub URL, so both of the following work:

```
pip install ragframework
pip install git+https://github.com/...
```

---

## 9. What not to do in this stage

- **Do not document a quickstart that's rougher than the Stage 13 docker-compose experience.** If `docker compose up` "just works" but the pip-installed path needs extra undocumented steps, fix the packaging/docs gap rather than shipping the discrepancy.
- **Do not write the per-connector guide as a one-off, FAISS/Gemini-specific document that would need restructuring to add a second connector guide later.** Use a template shape from the start.
- **Do not treat an addition to `BaseVectorStore` or `BaseLLMProvider` as a minor or patch change**, even one that looks backward-compatible on the surface (e.g., a new method with a default implementation on the ABC itself can be fine, but a new *abstract* method or a changed signature on an existing one is breaking).
- **Do not write the changelog as a stage-by-stage build log.** It documents releases and their user-facing changes, not internal construction milestones.
- **Do not let the base package install pull in dependencies for connectors that don't exist.** Use `extras_require` from day one, even with only one extra group defined.
- **Do not bury the `allow_dangerous_deserialization=True` FAISS constraint or the O(n) delete cost in code comments only.** Both need a plain-language, adopter-facing explanation in the per-connector guide.
- **Do not skip verifying `pip install git+https://github.com/...` actually works** just because PyPI publishing is the primary target — adopters without PyPI access or during a pre-PyPI-approval period need this path to work too.

---

## 10. Instructions to the implementing agent

1. Write `README.md` with the three-step quickstart from Section 3, verified against a genuinely fresh environment (no leftover local state from earlier build stages).
2. Write the per-connector setup guide (e.g., `docs/connectors/faiss-gemini.md`) using a reusable template structure: connector selection env vars → connector-specific config fields → known limitations → worked example. Include the `allow_dangerous_deserialization=True` and O(n) `delete()` explanations plainly.
3. Write `CHANGELOG.md` with an initial release entry summarizing the framework's delivered scope, not a stage-by-stage log.
4. Write `pyproject.toml` with `extras_require`, defining a base install (core + FAISS + Gemini + FastAPI + the minimum needed for the shipped backend features) and structuring it so a future connector's dependencies would live in a new extras group, not the base.
5. Add a `CONTRIBUTING.md` or an "Adding a new connector" doc section explicitly walking through the extension-point steps described in Stage 1 (implement the base class, add a module, register it), so semantic versioning discipline (Section 5) has a companion doc explaining what adopters attempting this should watch for.
6. Verify both `pip install ragframework` (against a test PyPI index or a local build, if not yet published to real PyPI) and `pip install git+https://github.com/...` work from a clean environment.
7. Cross-check that every environment variable and every API endpoint introduced across Stages 1–13 is documented somewhere in the README or the per-connector guide — do a final pass reconciling documentation against the actual `Settings` model and router definitions, since documentation drift across a fourteen-stage build is the most likely place small gaps accumulate.
8. Tag the initial release version (e.g., `v1.0.0`) consistent with the semantic versioning policy in Section 5.

---

## 11. Definition of done

- [ ] `README.md`'s quickstart works verbatim in a genuinely fresh environment: `pip install ragframework` → fill in `.env` → `ragframework serve`.
- [ ] The per-connector setup guide exists, uses a template structure a second connector guide could reuse, and plainly documents the FAISS `allow_dangerous_deserialization=True` constraint and O(n) delete cost.
- [ ] `CHANGELOG.md` exists with a release-oriented (not stage-oriented) initial entry.
- [ ] `pyproject.toml` uses `extras_require` and the base install has no dependencies belonging to a connector that doesn't exist yet.
- [ ] Both `pip install ragframework` and `pip install git+https://github.com/...` succeed from a clean environment.
- [ ] Every environment variable and API endpoint from Stages 1–13 is documented and matches the actual implementation (no drift).
- [ ] A versioning policy explicitly treating `BaseVectorStore`/`BaseLLMProvider` changes as major-version events is documented for future contributors.
- [ ] An initial version is tagged.

## 12. What comes after this stage

This is the last stage in the production build roadmap. The framework, as delivered, supports exactly two connectors (FAISS, Gemini) behind a fully generalized, tested, documented extension mechanism. Any future work — adding pgvector, Qdrant, Pinecone, Weaviate, OpenAI, or Anthropic connectors — follows the extension-point process documented in this stage's output, governed by the semantic versioning policy in Section 5, and does not require revisiting any of the fourteen stages in this roadmap: that is the entire point of having built the contracts first, in Stage 1.
