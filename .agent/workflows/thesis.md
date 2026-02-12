---
description: Workflow for writing the master thesis chapter by chapter using LaTeX in Docker
---

# Master Thesis Writing Workflow

A systematic approach to writing the Twin2MultiCloud master thesis, designed so the AI agent can help draft, review, and refine each chapter.

---

## 🎯 Thesis Goal

The goal of this master thesis is to build a unified application that combines two existing bachelor thesis prototypes (a cost optimizer and a cloud deployer) into a single platform. The platform enables users to deploy a **fully functional digital twin environment**—based on a predefined 5-layer IoT architecture—across multiple cloud providers (**AWS, Azure, GCP**), from just configuration files and user inputs. The user configures IoT devices, selects cost-optimal providers per layer, and deploys the entire multi-cloud infrastructure through a single interface.

---

## ⚠️ CRITICAL RULES FOR AI AGENTS

> [!CAUTION]
> **ZERO HALLUCINATION POLICY**: Every statement in the thesis must be grounded in hard facts.
> - Only write content that can be verified from the actual codebase, documentation, or user-provided references.
> - If you are unsure about a detail, mark it with `% TODO: VERIFY —` and ask the user.
> - NEVER invent technical details, metrics, or descriptions. Read the source code first.
> - When describing the legacy projects, do NOT guess their original state — ask the user or verify from git history.

> [!CAUTION]
> **EXPLICIT APPROVAL REQUIRED**: Do NOT make any changes to `.tex` files, `main.tex`, or chapter structure without explicit user approval.
> 1. **Propose** the change (describe it in text or in an artifact).
> 2. **Wait** for the user to say "approved" or "go ahead".
> 3. **Only then** implement the change.
>
> This applies to: creating/deleting/renaming chapter files, editing prose, modifying `main.tex` includes, and restructuring sections.

### Content Quality Rules
- Be **concise, precise, and technical** — no filler, no fluff, no vague statements.
- Every sentence must carry information, but do NOT over-compress: the thesis must reach **80–120 pages (text only)**. Provide sufficient detail, context, and justification for design decisions.
- Use **technical terminology** appropriate for a computer science master's thesis. Avoid:
  - Bloated or philosophical phrasing (e.g., "paradigm shift", "central nervous system of the platform")
  - Overly complex or pretentious wording — keep it **high-level but accessible**
  - Metaphors that the author would not naturally use in conversation
- The tone should read like a **senior engineer explaining their system to a technical audience**: factual, structured, detailed, but not flowery.
- When drafting prose, always read the relevant source code first to ensure accuracy.
- Use `% TODO:` for any claim that needs a citation or verification.

---

## Prerequisites

### Start LaTeX Watch Mode
// turbo
```bash
mkdir -p twin2multicloud-latex/build/chapters
docker compose run --rm thesis-latex
```

> The PDF auto-compiles on save at `twin2multicloud-latex/build/main.pdf`.

### Clean Build (if stuck errors)
```bash
docker compose run --rm thesis-latex latexmk -C -cd /thesis/main.tex
```

---

## Writing Order (Recommended)

Write chapters in this order — **not** the order they appear in the thesis. This is the most efficient order because each chapter builds on the previous one.

| Phase | Chapter | Why This Order |
|-------|---------|----------------|
| 1 | **System Architecture** (Ch 4) | You know the system best right now — capture the design while it's fresh |
| 2 | **Implementation** (Ch 5) | Naturally follows from architecture — cover the "how" |
| 3 | **Evaluation** (Ch 6) | Document E2E tests, cost accuracy, deployment metrics you already have |
| 4 | **Background** (Ch 2) | Now you know exactly which concepts the reader needs |
| 5 | **Related Work** (Ch 3) | Position your work against others — easier after writing your own chapters |
| 6 | **Discussion** (Ch 7) | Reflect on results, compare with related work, state limitations |
| 7 | **Introduction** (Ch 1) | Write last — you now know your exact contributions and structure |
| 8 | **Conclusion** (Ch 8) | Summarize everything — easiest to write last |
| 9 | **Abstract** | Final polish — condense the entire thesis into one page |

---

## Per-Chapter Workflow

For each chapter, follow these steps:

### Step 1: Gather Source Material
Before writing, collect relevant inputs:
- Read the chapter's `.tex` file for the existing outline and comment prompts
- Review the relevant codebase (e.g., for Implementation → read the actual source code)
- Check Knowledge Items for technical details
- Review `integration_vision.md` for high-level context
- Check `docs/` folders in each project for existing documentation

### Step 2: Draft Section by Section
- **Propose** the draft to the user first — do NOT write directly into `.tex` files
- Replace the `% comment` prompts with actual LaTeX prose only after approval
- Write **one section at a time** — don't try to write the whole chapter at once
- Use `\gls{acronym}` for defined acronyms (see `styles/glossary.tex`)
- Include `\label{}` and `\ref{}` for cross-references
- Mark TODOs with `% TODO: VERIFY —` for any claim that needs verification

### Step 3: Add Figures and Tables
- Place figures in `twin2multicloud-latex/figures/`
- Use consistent figure naming: `chX-description.png`
- Every figure/table must be referenced in the text
- Use the AI image generation tool for diagrams if needed

### Step 4: Review and Refine
- Ask the AI to review for:
  - Logical flow and coherence
  - Academic writing style (formal, third person, precise)
  - Missing citations (`\cite{}` placeholders)
  - Consistency with other chapters
- Check the compiled PDF for formatting issues

### Step 5: Compile and Verify
// turbo
```bash
docker compose run --rm thesis-latex latexmk -pdf -interaction=nonstopmode -cd /thesis/main.tex
```

---

## Academic Writing Guidelines

When drafting thesis content, follow these rules:

1. **Voice**: Use passive voice for system descriptions ("The credentials are encrypted at rest..."). Use first-person **"I"** when describing design decisions, development experiences, or choices the author made ("I chose SSE over WebSockets because..."). Never use "we" — this is a single-author thesis.
2. **Tense**: Present tense for system descriptions ("The optimizer calculates..."), past tense for evaluation ("The test showed...")
3. **Citations**: Every claim needs a citation. Use `\cite{key}` and add entries to `bibliography/biblio.bib`. When drafting, **proactively insert `% TODO: CITE —` comments** for anything that will need a reference, even if the exact BibTeX entry does not exist yet. There are three categories:
   - **Tools & technologies** (e.g., FastAPI, Terraform, Flutter, Docker Compose) — cite official docs or websites (`@misc`)
   - **Standards & RFCs** (e.g., PBKDF2 → RFC 8018, WebSocket → RFC 6455, SSE → W3C spec, Fernet → spec repo) — cite the standard directly
   - **Academic concepts** (e.g., microservices architecture, Infrastructure as Code, digital twins, IoT reference architectures) — mark with `% TODO: CITE — find paper/book for [concept]` so we can investigate the right source later
   
   The goal is that **no technology, protocol, standard, or academic concept goes untagged** in a draft. We will resolve all TODOs in a dedicated bibliography pass.
4. **Figures**: Every figure must be referenced in text. Use `Figure~\ref{fig:name}` (with tilde for non-breaking space)
5. **Acronyms**: Define on first use via `\gls{}`. Never use an undefined acronym
6. **Avoid**: Contractions (don't → do not), vague language ("very", "a lot"), colloquialisms, philosophical phrases, bloated metaphors, **em dashes** (`---` / `—`) in prose text. Instead of em dashes for subordinate clauses, use commas, semicolons, parentheses, or restructure the sentence. Em dashes in code snippets and LaTeX comments are fine.
7. **Page target**: ~80–120 pages total text (excluding front/back matter, figures, and appendices)
8. **Detail level**: Write enough detail to be informative and fill the page target. Each design decision should include a brief justification (why, not just what). Avoid under-writing sections — a one-paragraph section is almost always too short.
9. **Code snippets**: When accurate and helpful, include **small code snippets** from the actual codebase to illustrate a specific point (e.g., a protocol definition, a key function signature, a configuration pattern). Keep snippets short (≤15 lines) and always accompany them with explanatory prose — never drop code without context. Use LaTeX `lstlisting` or `minted` environments. Snippets serve as evidence that grounds the text in the real implementation; they are especially valuable for design patterns, protocol interfaces, and non-obvious configurations.

### Author Voice & Tone

The target tone is a **technically precise, professional engineer** explaining their system to a technical audience. Not literary, not corporate, not basic — somewhere between casual and formal.

- **Be direct and practical.** Say what something does and why. Avoid decorative phrasing.
- **Narrate decisions naturally.** When justifying a design choice, prefer the story over the assertion. Write "I avoided hard-coded URLs because switching between configurations would have been fragile" rather than "Hard-coding URLs was considered and rejected early on as it would compromise configuration flexibility."
- **Use transition words freely.** The author naturally uses **Furthermore**, **Moreover**, **However**, **Thus**, **Additionally**, and **On the other hand** to connect ideas. These are part of the author's voice and should appear regularly. Do NOT strip them out or replace them with bare sentence juxtaposition.
- **Stay grounded.** Avoid over-polished phrasing that sounds like a conference keynote or corporate blog. Phrases like "This constraint is architectural, not incidental" are too stylized. Prefer: "This is intentional — if the UI called the Deployer directly, it would bypass credential decryption."
- **Lean toward precision over elegance.** When in doubt, choose the clearer, more specific phrasing even if it's less smooth.

---

## 🛡️ AI Detection Countermeasures (MANDATORY)

AI detection tools (Turnitin, GPTZero, Originality.AI) evaluate three signals: **perplexity** (how predictable word choices are), **burstiness** (variation in sentence length and complexity), and **token probability** (whether the text follows the "default" most-likely path an LLM would produce). The rules below **must** be applied to every paragraph of thesis prose.

### Signal 1: Increase Perplexity (Less Predictable Word Choices)

AI text tends to always pick the "obvious" next word. Human text is more surprising.

1. **Avoid default collocations.** Do not write "well-defined API", "seamless integration", "robust solution", "leverages", "facilitates", "comprehensive overview". These are the highest-probability LLM completions and are the #1 detection signal. Use more specific, less common phrasing instead.
2. **Vary vocabulary deliberately.** If you used "ensures" in one sentence, do not use it again within the same paragraph. Use a synonym, restructure the sentence, or drop the word entirely.
3. **Use domain-specific jargon naturally.** Prefer concrete technical terms over generic descriptions. Write "the Fernet token wraps AES-128-CBC ciphertext with an HMAC-SHA256 tag" rather than "the encryption provides strong security guarantees."
4. **Use the author's natural transitions.** The author regularly uses **Furthermore**, **Moreover**, **However**, **Thus**, **Additionally**, and **On the other hand** — these are a style fingerprint and should be used naturally throughout the text. Do NOT strip them to appear "less AI" — their absence actually makes the text less human. The only transitions to avoid are pure filler with no information: "It is worth noting that", "In this context", "It should be mentioned that".

### Signal 2: Increase Burstiness (Vary Sentence Structure)

AI text has suspiciously uniform sentence length and structure. Human writing is uneven.

5. **Mix sentence lengths aggressively.** Follow a long compound sentence (30+ words) with a short declarative one (5–10 words). Then use a medium one. Never write three consecutive sentences of similar length.
6. **Vary sentence openings.** Do NOT start 3+ consecutive sentences with the same grammatical structure (e.g., "The system...", "The module...", "The service..."). Mix: start with a prepositional phrase, a dependent clause, a short statement, a parenthetical, or a contrast.
7. **Break parallelism in lists.** When writing bullet points or enumerated lists, do NOT give every item the same structure (bold label + two uniform sentences). Vary: some items get one sentence, others get three. Some start with context, others start with the point. Some have sub-examples, others do not. The items should feel like they were written at different times, not batch-generated.
8. **Use asymmetric depth.** Spend more words on the novel or non-obvious aspects. Spend fewer words on the obvious ones. A human does not give equal weight to every point—they linger where it is interesting and skim where it is straightforward.

### Signal 3: Lower Token Probability (Deviate from the Default Path)

AI detectors check if the text follows the highest-probability sequence of tokens. Introduce controlled deviation.

9. **Include decision justifications with trade-offs.** Instead of just stating what was done, explain what alternatives existed and why they were rejected. Example: "SQLite was chosen over PostgreSQL because, in a single-user evaluation context, the operational overhead of a separate database server was not justified." This is low-probability text because it is specific to the author's situation—an LLM would not "default" to this reasoning.
10. **Add scope qualifiers.** Prefix claims with context like "In the current implementation," or "For the purposes of this thesis," or "Given the constraint that all services run locally,". These are human markers that signal awareness of limitations.
11. **Reference concrete artifacts.** Mention actual file names, class names, config keys, endpoint paths, and environment variable names where relevant. This grounds the text in the specific system and produces token sequences that no general-purpose LLM would generate by default.
12. **Show author awareness.** Occasionally acknowledge trade-offs, limitations, or imperfections: "This design does introduce a single point of failure at the Orchestrator, which is acceptable for the evaluation scope of this work but would need to be addressed in a production deployment." Detectors flag text that is too clean and too confident—real authors hedge.

### Self-Check Before Proposing a Draft

Before presenting any drafted section to the user, mentally verify:
- [ ] No paragraph has 3+ consecutive sentences with identical grammatical structure
- [ ] No paragraph starts with the same word/phrase pattern more than twice
- [ ] At least one sentence per section includes a decision justification or trade-off
- [ ] Natural transition words (Furthermore, However, Thus, Moreover) are used where they fit — text does not feel choppy or disconnected
- [ ] Every list has items of varying length and structure
- [ ] At least one scope qualifier or limitation acknowledgment per section
- [ ] No default collocations from the blocklist in rule 1
- [ ] Tone matches the Author Voice guidelines: direct, practical, not over-polished
- [ ] First-person "I" is used for design decisions; passive voice for system descriptions
- [ ] Every mentioned technology, protocol, standard, or academic concept has either a `\cite{}` or a `% TODO: CITE —` comment

---

## Chapter Page Targets

| Chapter | Target Pages | Notes |
|---------|-------------|-------|
| Abstract | 1 | Already drafted |
| Introduction | 4–6 | Problem, RQs, contributions, structure |
| Background | 10–15 | Theory the reader needs |
| Related Work | 8–12 | Survey + gap identification |
| Legacy Analysis | 6–10 | Analysis of predecessor systems |
| System Architecture | 15–20 | **Main chapter** — design & rationale |
| Implementation | 12–16 | Tech stack, patterns, key decisions |
| Evaluation | 12–18 | E2E tests, cost validation, metrics |
| Discussion | 6–10 | Comparison, limitations, threats |
| Conclusion | 3–5 | Summary + future work |

---

## How to Ask the AI for Help

Use these slash-command-style requests:

- **"Write section X of chapter Y"** — AI drafts prose based on the comment prompts and codebase
- **"Review chapter X"** — AI checks flow, style, and completeness
- **"Generate a diagram for X"** — AI creates a figure using the image tool
- **"Add bibliography entries for X"** — AI finds and formats BibTeX entries
- **"Polish section X"** — AI refines language and fixes academic style issues

---

## Bibliography Management

Add references to `bibliography/biblio.bib` in BibTeX format. Uncomment in `main.tex`:
```latex
\bibliographystyle{plain}
\bibliography{bibliography/biblio}
```

---

## Final Checklist (Before Submission)

- [ ] All `% TODO:` comments resolved
- [ ] All `% comment` prompts replaced with prose
- [ ] Every figure and table referenced in text
- [ ] All acronyms defined in glossary
- [ ] Bibliography complete — no `[?]` in PDF
- [ ] Spell check completed
- [ ] Affidavit and acknowledgements uncommented in `main.tex`
- [ ] Watermark removed (comment out `xwatermark` in `main.tex`)
- [ ] Page count within target range
- [ ] Supervisor review feedback incorporated