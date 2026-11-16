# NecroMARC - Project Constitution & Steering Rules

## 1. Anti-Hallucination & Clarification Protocol (CRITICAL)
- **DO NOT GUESS OR ASSUME:** Whenever a requirement, data structure, UI behavior, or architectural choice is ambiguous, incomplete, or can be interpreted in multiple ways, you MUST STOP immediately and ask the user clarifying questions BEFORE generating specs or writing code.
- **Language of Communication:** Always communicate with the user and ask your clarifying questions in clear **Arabic**, while keeping code, variable names, git commits, and technical SDD specifications (`requirements.md`, `design.md`, `tasks.md`) in professional **English**.
- **Token Economy:** Keep your questions concise, numbered, and grouped together so the user can answer them in a single turn.

## 2. Domain Accuracy: MARC 21 vs. Legacy ISO 2709 Architecture
- **Scientific Precision:** Never describe MARC 21 itself as a "dead standard" (it is actively maintained by the Library of Congress). Instead, accurately frame the problem: MARC 21's underlying **1960s ISO 2709 binary flat-file architecture** is an obsolete legacy relic ("undead" tech built for magnetic tapes) that isolates millions of historical records in dark, unindexed silos with broken encodings, missing summaries (`520`), and zero Semantic Web / Linked Open Data (BIBFRAME / JSON-LD) compatibility.

## 3. Hardware & AI Provider Constraints (NO LOCAL ML)
- **STRICTLY FORBIDDEN:** Never use or install `ollama`, `torch`, `pytorch`, `tensorflow`, `transformers`, or `sentence-transformers`. The local machine and hosting environment must remain lightweight.
- **LLM Text Generation & JSON Repair:** Use **OpenRouter API** (`https://openrouter.ai/api/v1/chat/completions`) via lightweight HTTP requests (`httpx` or `openai` SDK pointed to OpenRouter). Default to free/low-cost models configurable via `.env` (e.g., `google/gemini-2.0-flash-exp:free` or `meta-llama/llama-3.3-70b-instruct:free`).
- **Vector Embeddings (Semantic Search):** Use **Google Gemini API** free tier (`models/gemini-embedding-001`, `output_dimensionality=768) via REST/SDK for Supabase `pgvector` indexing.

## 4. Security, Judge Authentication & Hosting Architecture
- **ZERO HARDCODED SECRETS:** Never place API keys (`OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `JUDGE_ACCESS_PASSWORD`) in source code or frontend Astro files.
- **API Credit Protection (Judge Auth Gate):**
  - Public visitors have unrestricted read access to browse resurrected records, explore the Knowledge Graph, and run semantic searches (using pre-computed or lightweight query paths).
  - Live AI Resurrection endpoints (`POST /api/resurrect`, `POST /api/upload-mrc`) MUST be protected by a backend authentication token/session (`Judge / Archivist Login` using credentials configured in `.env`).
- **Hosting Compatibility:** The Astro frontend must be buildable as a static site (`output: 'static'`) with a configurable `base` path (to support deployment inside a dedicated subdirectory or subdomain on paid cPanel/Linux hosting). The Flask backend must include a standard WSGI entry point (`passenger_wsgi.py`) for seamless shared/cPanel Python hosting deployment.
- **Kiroween 2026 Compliance:** The `/.kiro/` directory (`/specs`, `/steering`, `/hooks`) MUST NEVER be added to `.gitignore` and must remain public on GitHub (`https://github.com/ahmed-ali-2024/NecroMARC`).

## 5. MARC 21 Bibliographic Reference
When building the parser with `pymarc`, adhere strictly to MARC 21 (ISO 2709):
- **Leader (24 bytes):** Pos `05` (Status), Pos `06` (Type: `a` = Language material, `t` = Manuscript), Pos `07` (Bibliographic level: `m` = Monograph).
- **001:** Control Number.
- **008 (40 bytes Fixed Data):** Pos `07-10` (Publication Year), Pos `15-17` (Place code), Pos `35-37` (Language code, e.g., `eng`, `ara`, `fre`, `lat`).
- **020 `$a`:** ISBN.
- **100 `$a`, `$d`:** Main Entry - Personal Name (Author & dates).
- **245 `$a`, `$b`, `$c`:** Title Statement (`$a` Main title, `$b` Subtitle, `$c` Responsibility).
- **260 / 264 `$a`, `$b`, `$c`:** Publication info (`$a` Place, `$b` Publisher, `$c` Date).
- **500 `$a` & 520 `$a`:** General Note & Summary/Abstract *(Primary target for AI Resurrection)*.
- **650 `$a`, `$x`, `$z`, `$y`:** Subject Added Entry - Topical Term *(Primary target for AI Enrichment & Knowledge Graph edges)*.