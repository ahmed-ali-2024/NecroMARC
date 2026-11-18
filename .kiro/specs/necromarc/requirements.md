# Requirements Document

## Introduction

NecroMARC is an AI-powered "Bibliographic Necromancer" built for Kiroween 2026 (Resurrection category). MARC 21 is an actively maintained standard of the Library of Congress. The problem NecroMARC addresses is the 1960s ISO 2709 binary flat-file container, a legacy format built for magnetic tape. That container leaves millions of historical records in unindexed silos with broken encodings, missing summaries (520), and no Linked Open Data compatibility (BIBFRAME, JSON-LD).

NecroMARC ingests raw or corrupted `.mrc` (ISO 2709) files and parses them with pymarc. It computes a deterministic Decay Score, heals and enriches metadata through an OpenRouter LLM, and converts each record to JSON-LD (schema.org Book, BIBFRAME-inspired). It indexes 768-dimension embeddings in Supabase pgvector and presents the results in a Dark-Academia knowledge graph interface.

Deployment targets:
- Frontend: static Astro site at `https://3aai.in/necromarc/` (base `/necromarc`, TailwindCSS, Cytoscape.js).
- API: Flask on cPanel Setup Python App (Python 3.11.18, Passenger, `passenger_wsgi.py`) at `https://3aai.in/necromarc/api`.
- Database: Supabase (`https://rgslhkioqynhgfqrwagm.supabase.co`) with pgvector.
- Repository: `https://github.com/ahmed-ali-2024/NecroMARC`.

Constraints from the project constitution: no local machine learning, no hardcoded secrets, and `.kiro/` always tracked in version control.

## Glossary

- **NecroMARC**: The complete system comprising the Frontend, the API, the Parser, the Decay_Calculator, the Resurrection_Engine, the Embedding_Service, the Exporter, and the Database.
- **API**: The Flask backend served through Passenger at `/necromarc/api`.
- **Frontend**: The statically built Astro and TailwindCSS web application, including the Cytoscape.js graph.
- **Parser**: The backend module (Module A) that reads ISO 2709 bytes using pymarc and returns structured results.
- **MARC_Record**: A single bibliographic record in ISO 2709 or MARCXML form.
- **Parsed_Record**: The structured Parser output for one MARC_Record, containing extracted fields, anomaly flags, and structured errors.
- **Anomaly**: A detected defect in a MARC_Record, such as an encoding fault, a structural fault, or an invalid field value.
- **Decay_Calculator**: The backend module that computes the Decay_Score for a Parsed_Record.
- **Decay_Score**: A deterministic integer from 0 to 100 measuring how degraded a MARC_Record is (higher means more decayed).
- **Decay_Breakdown**: The list of Decay_Score rules that fired, each with its rule name and point value.
- **Vitality_Score**: An integer from 0 to 100 shown on the resurrected card measuring completeness of the healed record.
- **Resurrection_Engine**: The backend module that calls OpenRouter to heal and enrich a Parsed_Record.
- **Resurrection_Result**: The validated JSON object returned by the LLM, containing `healed_summary`, `inferred_subjects`, `normalized_year`, `language_name`, and `json_ld`.
- **OpenRouter**: The LLM gateway at `https://openrouter.ai/api/v1/chat/completions`.
- **Embedding_Service**: The backend module that calls the Gemini embedding model and returns L2-normalized 768-dimension vectors.
- **Exporter**: The backend module that serializes records to ISO 2709, MARCXML, and JSON-LD.
- **Database**: The Supabase Postgres instance containing `marc_records`, `knowledge_edges`, and `rate_limits`.
- **Archive**: The set of resurrected records stored in `marc_records`.
- **Knowledge_Graph**: The graph of Archive records (nodes) and `knowledge_edges` rows (edges) shown with Cytoscape.js.
- **Edge_Type**: One of SHARED_SUBJECT, SAME_AUTHOR, SAME_ERA, SEMANTIC_SIMILARITY.
- **Guest**: A visitor who has not authenticated.
- **Judge**: A user authenticated through Judge / Archivist Login.
- **Judge_Token**: A stateless JWT issued by the API after successful Judge login.
- **Resurrection_Chamber**: The split-screen view with the Terminal_Panel on the left and the Resurrected_Card on the right.
- **Terminal_Panel**: The green-phosphor panel that shows raw MARC lines (for example `=LDR`, `=008`, `=245 10$a...`) with decay indicators.
- **Resurrected_Card**: The Dark-Academia card that shows the healed summary, subject badges, Vitality_Score, and export buttons.
- **Sample_Tomb**: A bundled sample `.mrc` file used by the "Summon & Resurrect Sample Tomb" action.
- **Seed_Script**: The local developer script that produces the 60 pre-resurrected Archive records.
- **Rate_Limiter**: The API component that counts requests per client using the `rate_limits` table.
- **Config**: Environment variables loaded from `.env`.
- **AI_Provenance_Subfield**: The MARC subfield `$9` with value `NecroMARC-AI`, appended to AI-written fields.
- **Hook**: A Kiro Agent Hook stored in `.kiro/hooks/`.
- **i18n_Dictionary**: A JSON file of translated interface strings, one per supported language (English, Arabic).

## Requirements

### Requirement 1: MARC 21 Parsing (Module A)

**User Story:** As an archivist, I want raw `.mrc` files parsed into structured data, so that every record can be analyzed and healed.

#### Acceptance Criteria

1. WHEN ISO 2709 bytes are submitted, THE Parser SHALL return one Parsed_Record per MARC_Record found in the bytes, in the same order as the records appear in the input.
2. WHEN the Parser parses a MARC_Record, THE Parser SHALL extract the Leader, 001, 008, 020 `$a`, 100 `$a` and `$d`, 245 `$a` `$b` `$c`, 260 or 264 `$a` `$b` `$c`, 500 `$a`, 520 `$a`, and 650 `$a` `$x` `$y` `$z` into the Parsed_Record, and THE Parser SHALL represent each field or subfield absent from the MARC_Record as absent (not as an empty string) and SHALL keep every occurrence of a repeatable field or subfield in input order.
3. WHEN the Leader is at least 24 characters long, THE Parser SHALL read Leader positions 05, 06, and 07 into the Parsed_Record.
4. WHEN the 008 field is exactly 40 characters long, THE Parser SHALL read 008 positions 07-10, 15-17, and 35-37 into the Parsed_Record.
5. IF the Leader is shorter than 24 characters or the 008 field is shorter than 40 characters, THEN THE Parser SHALL set each position that cannot be read to absent, SHALL record an Anomaly identifying the affected field in the Parsed_Record, and SHALL still return the Parsed_Record.
6. WHEN a MARC_Record uses MARC-8, Latin-1, or UTF-8 encoding, THE Parser SHALL decode the record text into Unicode.
7. WHEN the Parser detects an encoding that differs from the encoding declared by Leader position 09 (blank = MARC-8, `a` = UTF-8), THE Parser SHALL record an encoding Anomaly in the Parsed_Record stating the declared and detected encodings, and SHALL decode the text using the detected encoding.
8. IF a byte sequence cannot be decoded in the detected encoding, THEN THE Parser SHALL replace each undecodable byte with U+FFFD, SHALL record an encoding Anomaly in the Parsed_Record, and SHALL still return the Parsed_Record.
9. IF a MARC_Record is malformed, truncated, or unreadable, THEN THE Parser SHALL return a structured error containing an error code, a message, and the zero-based byte offset of the start of that record in the input, SHALL return no Parsed_Record for that MARC_Record, and SHALL continue with the remaining records.
10. IF the input is empty or contains no recognizable record, THEN THE Parser SHALL return an empty record list and exactly one structured error containing an error code, a message, and the byte offset 0.
11. THE Parser SHALL return results and errors as values and SHALL NOT raise an exception for any byte input, including input of 0 bytes and input of at least 100 MB.
12. WHEN a batch contains the Project Gutenberg catalog dumps, the Library of Congress SRU sample records, or the intentionally corrupted sample records, THE Parser SHALL return a Parsed_Record for every readable MARC_Record and a structured error for every unreadable MARC_Record, and SHALL complete the batch without aborting.
13. WHEN a Parsed_Record is submitted to the Pretty_Printer, THE Pretty_Printer SHALL serialize it into ISO 2709 bytes with a Leader record length, base address, and directory entries consistent with the serialized content, the field terminator (0x1E) after each field, and the record terminator (0x1D) at the end of the record.
14. FOR ALL valid UTF-8 MARC_Records with a full 24-character Leader and a 40-character 008 field, parsing, then printing, then parsing SHALL produce a Parsed_Record equal to the first parsed result in every extracted field, subfield, Leader position, and Anomaly (strict round-trip property).
15. FOR ALL other parsed MARC_Records, including records in MARC-8 or Latin-1 encoding and records with a short Leader or a short 008 field, printing the result of parsing the printed output of the first parse SHALL produce bytes equal to the printed output of the first parse, that is, print(parse(print(parse(x)))) equals print(parse(x)) (normalized round-trip property).

### Requirement 2: Decay Score

**User Story:** As an archivist, I want a deterministic Decay Score with a breakdown, so that I can see exactly why a record is considered decayed.

#### Acceptance Criteria

1. THE Decay_Calculator SHALL compute the Decay_Score as the sum of the points of all rules in criteria 2 to 6 that apply to the Parsed_Record, where each rule contributes its points at most once per Parsed_Record.
2. IF the Parsed_Record has no 520 field, THEN THE Decay_Calculator SHALL add 30 points under the rule name "missing_520".
3. IF the Parsed_Record has no 650 field, THEN THE Decay_Calculator SHALL add 25 points under the rule name "missing_650".
4. IF the 008 field is absent, is shorter than 11 characters, or its publication year (positions 07-10, 0-indexed, 4 characters) is not a valid year, THEN THE Decay_Calculator SHALL add 20 points under the rule name "invalid_year". A valid year is exactly four ASCII digits forming an integer from 1000 to the current calendar year plus 1 inclusive. Values such as "uuuu", "||||", "    " (four spaces), "9999", and any value containing a non-digit character are not valid.
5. IF the Parsed_Record has no 100 field, or no 100 field contains a `$d` subfield with at least one non-whitespace character, THEN THE Decay_Calculator SHALL add 15 points under the rule name "missing_100d".
6. IF the Parsed_Record has at least one encoding Anomaly or structural Anomaly, THEN THE Decay_Calculator SHALL add 10 points once under the rule name "anomaly", regardless of the number of Anomalies.
7. THE Decay_Calculator SHALL return the Decay_Score as an integer from 0 to 100 inclusive, where a Parsed_Record to which no rule applies scores 0 and a Parsed_Record to which all five rules apply scores 100.
8. THE Decay_Calculator SHALL return a Decay_Breakdown containing one entry for each applied rule, each entry holding the rule name and its points, ordered as in criteria 2 to 6, such that the sum of the entry points equals the Decay_Score. WHEN no rule applies, THE Decay_Calculator SHALL return an empty Decay_Breakdown.
9. THE Decay_Calculator SHALL return the same Decay_Score and Decay_Breakdown, including entry order, for identical Parsed_Record input and an identical current calendar year on every invocation, without dependence on random values, invocation count, or the time of day.
10. THE Decay_Calculator SHALL return a Decay_Score and Decay_Breakdown for every Parsed_Record, including a Parsed_Record that carries structured errors or has missing fields, and SHALL NOT raise an exception. IF a Parsed_Record carries structured errors, THEN THE Decay_Calculator SHALL evaluate the rules in criteria 2 to 6 against the fields that are present and treat absent fields as missing.
11. THE Decay_Calculator SHALL compute the Vitality_Score of the healed record as an integer from 0 to 100 inclusive, equal to 100 minus the Decay_Score that the Decay_Calculator would compute for the healed record under criteria 1 to 6. A healed record with no applicable rule SHALL have a Vitality_Score of 100, and a healed record to which all five rules apply SHALL have a Vitality_Score of 0.

### Requirement 3: AI Resurrection via OpenRouter

**User Story:** As an archivist, I want missing metadata healed and enriched by an LLM, so that decayed records become useful again.

#### Acceptance Criteria

1. WHEN a Parsed_Record is submitted for resurrection, THE Resurrection_Engine SHALL send one HTTPS POST request to the OpenRouter endpoint `https://openrouter.ai/api/v1/chat/completions` using the model named in `OPENROUTER_MODEL`, with a request timeout of 30 seconds.
2. IF the request to the primary model fails, times out after 30 seconds, or returns a non-2xx status, THEN THE Resurrection_Engine SHALL try each model in `OPENROUTER_FALLBACK_MODELS` in the configured order, one attempt per model with a 30-second timeout each, until one returns a 2xx response.
3. THE Resurrection_Engine SHALL request strict JSON output containing exactly these fields:
   - `healed_summary`: string of 50 to 1000 characters, for MARC 520 `$a`.
   - `inferred_subjects`: array of 3 to 5 unique non-empty strings, each at most 100 characters, for MARC 650.
   - `normalized_year`: integer from 1000 to the current calendar year inclusive.
   - `language_name`: non-empty string of at most 50 characters, decoded from 008 positions 35-37.
   - `json_ld`: object whose `@context` equals `https://schema.org` and whose `@type` equals `Book`.
4. WHEN a 2xx LLM response is received, THE Resurrection_Engine SHALL validate the parsed JSON content against the JSON Schema defined in criterion 3 using jsonschema, rejecting any response that has missing required fields, wrong types, out-of-range values, or additional properties at the top level.
5. IF the response is not parseable as JSON or fails schema validation, THEN THE Resurrection_Engine SHALL retry the request once to the same model, with a 30-second timeout.
6. IF the retry also fails validation, or the primary model and every fallback model have failed, THEN THE Resurrection_Engine SHALL set the record status to `failed`, SHALL leave the raw parsed data byte-for-byte unchanged, and SHALL return an error indication identifying the failure reason (validation failure or all models unavailable).
7. WHEN a Resurrection_Result passes schema validation, THE API SHALL store the result, the Decay_Score, the Decay_Breakdown, and the Vitality_Score together with the record in the Database as a single atomic write, and SHALL leave the record unchanged if the write fails.
8. THE Resurrection_Engine SHALL send requests with httpx and SHALL NOT import or execute any locally run machine learning library.
9. THE Resurrection_Engine SHALL read the OpenRouter API key from Config only, and SHALL NOT include the key in any response body, stored record, or log output.

### Requirement 4: Embeddings and Similarity

**User Story:** As a researcher, I want records embedded as vectors, so that I can find semantically similar records.

#### Acceptance Criteria

1. WHEN a record is resurrected, THE Embedding_Service SHALL request an embedding from the Gemini model named in the Config embedding-model variable, with the default `gemini-embedding-001` and `output_dimensionality` 768.
2. WHEN THE Embedding_Service builds the embedding input for a record, THE Embedding_Service SHALL concatenate the title, author, healed summary, and subjects in that order, separated by a single newline, and SHALL omit any field that is null or empty after trimming whitespace.
3. IF the concatenated embedding input exceeds 8,000 characters, THEN THE Embedding_Service SHALL truncate the input to its first 8,000 characters before requesting the embedding.
4. IF the embedding input is empty after omitting null and empty fields, THEN THE Embedding_Service SHALL NOT call the Gemini API and SHALL return a structured error indicating that no embeddable text exists.
5. WHEN THE Embedding_Service receives a vector from the Gemini API, THE Embedding_Service SHALL L2-normalize it so that its Euclidean norm equals 1 within a tolerance of 1e-6.
6. THE Database SHALL store each embedding in a `vector(768)` column of `marc_records` with an HNSW index using cosine distance.
7. IF the Gemini API returns an error, does not respond within 30 seconds, or returns a vector whose length is not 768, THEN THE Embedding_Service SHALL return a structured error and THE API SHALL store the record with a null embedding and SHALL still complete the resurrection of that record.
8. WHEN a client requests similar records for an Archive record that has a stored embedding, THE API SHALL call the `match_marc_records` RPC with the stored vector of that record, SHALL exclude that record from the results, and SHALL return at most 10 records ordered by cosine similarity from highest to lowest, each with a cosine similarity of at least 0.5, without calling the Gemini API.
9. IF a client requests similar records for an Archive record whose embedding is null, THEN THE API SHALL return an empty result list and an indication that the record has no embedding, and SHALL NOT call the Gemini API.
10. WHEN a Judge submits free-text semantic search with a query of 1 to 1,000 characters after trimming whitespace, THE API SHALL embed the query with the Embedding_Service and SHALL call `match_marc_records` with the resulting vector, returning at most 10 records ordered by cosine similarity from highest to lowest, each with a cosine similarity of at least 0.5.
11. IF a Judge submits free-text semantic search with a query that is empty after trimming whitespace or longer than 1,000 characters, THEN THE API SHALL reject the request with a validation error and SHALL NOT call the Gemini API.
12. IF a Guest submits free-text semantic search, THEN THE API SHALL respond with HTTP 401 and SHALL NOT call the Gemini API.
13. THE API SHALL read the Gemini API key from Config only.

### Requirement 5: Knowledge Graph Data

**User Story:** As a researcher, I want relationships between records computed and stored, so that I can explore the collection as a graph.

#### Acceptance Criteria

1. THE Database SHALL store graph edges in `knowledge_edges` with a source record, a target record, an Edge_Type from SHARED_SUBJECT, SAME_AUTHOR, SAME_ERA, and SEMANTIC_SIMILARITY, and a numeric weight between 0.0 and 1.0 inclusive.
2. WHEN a record is stored, THE API SHALL create a SHARED_SUBJECT edge to each existing record that shares at least one normalized 650 `$a` subject value, with a weight equal to the number of shared normalized subjects divided by the number of distinct normalized subjects of the record with the larger subject count.
3. WHEN a record is stored, THE API SHALL create a SAME_AUTHOR edge with a weight of 1.0 to each existing record whose normalized 100 `$a` value equals that of the stored record.
4. WHEN a record is stored, THE API SHALL create a SAME_ERA edge to each existing record whose normalized year falls in the same decade (years 1990 to 1999 form one decade), with a weight of 1.0.
5. WHEN a record has a stored embedding, THE API SHALL create a SEMANTIC_SIMILARITY edge to each existing record whose cosine similarity is at least the Config similarity threshold, with a weight equal to the cosine similarity value.
6. THE API SHALL define normalization of author and subject values as Unicode NFKD decomposition, removal of combining diacritical marks, case-folding to lowercase, replacement of each punctuation character with nothing, collapsing of whitespace runs to a single space, and trimming of leading and trailing whitespace.
7. THE API SHALL define a normalized year as the first four-digit year from 260 `$c` or 264 `$c`, within the range 1000 to 2999.
8. IF a record has no 650 subject, no 100 `$a` value, no valid normalized year, or no stored embedding, THEN THE API SHALL skip creation of the corresponding edge types for that record, store the record, and not return an error.
9. THE API SHALL store at most one edge per unordered record pair and Edge_Type combination, and WHEN the Edge_Type is SHARED_SUBJECT, SAME_AUTHOR, SAME_ERA, or SEMANTIC_SIMILARITY, THE API SHALL store the edge with the source record set to the record with the lower identifier and the target record set to the record with the higher identifier.
10. IF an edge would have the same record as both source and target, THEN THE API SHALL not create that edge.
11. WHEN the Frontend requests the graph, THE API SHALL return a list of nodes, each with a unique identifier and a label, and a list of edges, each with a unique identifier, a source node identifier, a target node identifier, an Edge_Type, and a weight, in the element format that Cytoscape.js loads without transformation.

### Requirement 6: Database Schema and Security

**User Story:** As the project owner, I want the Database locked down, so that only the backend can write data.

#### Acceptance Criteria

1. THE Database SHALL contain the tables `marc_records`, `knowledge_edges`, and `rate_limits` and the function `match_marc_records`.
2. THE Database SHALL enable row level security on `marc_records`, `knowledge_edges`, and `rate_limits`.
3. THE Database SHALL allow SELECT on `marc_records` and `knowledge_edges` for the `anon` and `authenticated` roles.
4. THE Database SHALL define no row level security policy on `rate_limits`, so that the `anon` and `authenticated` roles can neither read nor write any row of `rate_limits`.
5. THE Database SHALL grant no INSERT, UPDATE, or DELETE privilege on `marc_records`, `knowledge_edges`, or `rate_limits` to the `anon` or `authenticated` roles.
6. IF a request authenticated as the `anon` or `authenticated` role attempts an INSERT, UPDATE, or DELETE on `marc_records`, `knowledge_edges`, or `rate_limits`, THEN THE Database SHALL reject the statement with a permission or row level security error and leave all rows unchanged.
7. THE Function `match_marc_records` SHALL perform read-only operations and SHALL NOT insert, update, or delete any row in any table.
8. THE API SHALL perform all writes with the service role key read from Config.
9. THE Frontend SHALL read data only through the API and SHALL NOT contain a Supabase URL, an anon key, or a service role key.
10. THE `marc_records` table SHALL store the raw MARC fields, the Anomaly list, the Decay_Score, the Decay_Breakdown, the Vitality_Score, the Resurrection_Result, the record status, the `source`, the `control_number`, and the embedding.
11. THE `marc_records` table SHALL constrain Decay_Score to values from 0 to 100 inclusive and SHALL reject any INSERT or UPDATE that sets a value outside that range.
12. THE `marc_records` table SHALL constrain the record status to exactly one of `decayed`, `resurrected`, or `failed` and SHALL reject any INSERT or UPDATE that sets another value.
13. THE `marc_records` table SHALL enforce uniqueness on the combination of (`source`, `control_number`) and SHALL reject an INSERT that duplicates an existing combination, leaving the existing row unchanged.
14. THE repository SHALL contain the schema, including the constraints, row level security settings, and grants defined in this requirement, as versioned SQL migration files that, when applied in order to an empty Database, produce the schema described in criteria 1 to 13.

### Requirement 7: Judge Authentication

**User Story:** As the project owner, I want expensive actions restricted to authenticated judges, so that API credits are protected.

#### Acceptance Criteria

1. WHEN a client posts credentials that exactly match `JUDGE_USERNAME` and `JUDGE_PASSWORD`, THE API SHALL return a Judge_Token signed with `JWT_SECRET_KEY` using the HS256 algorithm, with an expiry of `JUDGE_TOKEN_TTL_SECONDS` seconds after issuance (default 3600, allowed range 60 to 86400).
2. IF a client posts credentials that do not match `JUDGE_USERNAME` and `JUDGE_PASSWORD`, or posts a request with a missing or empty username or password field, THEN THE API SHALL respond with HTTP 401, SHALL NOT issue a token, and SHALL return a response body containing a single generic error indication that does not reveal whether the username or the password was incorrect.
3. THE API SHALL compare submitted credentials to `JUDGE_USERNAME` and `JUDGE_PASSWORD` in constant time, evaluating both the username and the password comparison on every login attempt.
4. IF `JUDGE_PASSWORD` is shorter than 16 characters or equals `JUDGE_USERNAME`, THEN THE API SHALL refuse to start with a non-zero exit status and SHALL log a reason identifying which rule failed, without including the password value in any log output.
5. IF a required Config secret (`JUDGE_USERNAME`, `JUDGE_PASSWORD`, or `JWT_SECRET_KEY`) is missing or empty at startup, THEN THE API SHALL refuse to start with a non-zero exit status and SHALL log the name of each missing variable, without including any secret value.
6. IF `JWT_SECRET_KEY` is shorter than 32 characters at startup, THEN THE API SHALL refuse to start with a non-zero exit status and SHALL log a reason stating the minimum length, without including the secret value.
7. IF a request to `POST /api/resurrect` or `POST /api/upload-mrc` lacks a valid Judge_Token in the `Authorization: Bearer <token>` header, THEN THE API SHALL respond with HTTP 401, SHALL include a `WWW-Authenticate: Bearer` response header, SHALL return a response body containing a single generic error indication that does not reveal the reason the token was rejected, and SHALL NOT perform the requested action.
8. WHEN verifying a Judge_Token, THE API SHALL accept only tokens whose header declares the HS256 algorithm and SHALL reject tokens declaring any other algorithm, including `none`, as unauthenticated.
9. WHEN a Judge_Token is expired, has an invalid signature, is malformed, or declares an algorithm other than HS256, THE API SHALL treat the request as unauthenticated and SHALL apply the 401 response defined in criterion 7.
10. THE API SHALL keep no server-side session state for Judge_Tokens, so that token validity is determined solely from the token contents and `JWT_SECRET_KEY`.
11. WHEN a single client IP address exceeds 5 login attempts (successful or failed, every attempt counting toward the limit) within 60 seconds, THE API SHALL respond to further login attempts from that address with HTTP 429 and a `Retry-After` header stating the remaining seconds until the window ends, and SHALL NOT evaluate the submitted credentials during that period.
12. WHERE the deployer sets own keys in `.env`, THE API SHALL run in open-source self-hosted mode using those keys.

### Requirement 8: Public Guest Access

**User Story:** As a visitor, I want to explore the archive without logging in, so that I can see the project's value immediately.

#### Acceptance Criteria

1. THE API SHALL serve Archive browsing, single-record retrieval, raw-versus-resurrected comparison, and Knowledge_Graph data to Guests without requiring authentication credentials.
2. WHEN a Guest submits a full-text search request, THE API SHALL return Archive records matching the query using Postgres full-text search, optionally filtered by title, author, era, and topic, without requiring authentication credentials.
3. WHEN a Guest submits a search request with more than one filter, THE API SHALL return only records that satisfy all supplied filters (logical AND).
4. WHERE an era filter is supplied as a start year and an end year, THE API SHALL return only records whose year falls within the range, inclusive of both bounds.
5. IF an era filter has a start year greater than its end year, or either value is not an integer, THEN THE API SHALL respond with HTTP 400 and a structured error body, and SHALL NOT return any records.
6. WHEN a Guest selects "Similar records" on an Archive record, THE API SHALL return results using the stored vector as defined in Requirement 4.
7. WHEN a Guest requests an Archive list or search results, THE API SHALL return results in pages that accept a page number (integer, minimum 1, default 1) and a page size (integer, minimum 1, default equal to the Config default page size), and SHALL include in each response the total result count and the page number and page size applied.
8. IF a Guest requests a page size greater than the Config maximum page size, THEN THE API SHALL respond with HTTP 400 and a structured error body, and SHALL NOT return any records.
9. IF a Guest supplies a page number or page size that is not an integer or is less than 1, THEN THE API SHALL respond with HTTP 400 and a structured error body.
10. WHEN a Guest requests a page number beyond the last page, THE API SHALL respond with HTTP 200 and an empty result list together with the total result count.
11. IF a Guest requests a record identifier that is not in the valid identifier format, THEN THE API SHALL respond with HTTP 400 and a structured error body.
12. IF a Guest requests a well-formed record identifier that does not exist, THEN THE API SHALL respond with HTTP 404 and a structured error body.
13. THE API SHALL format every structured error body as an object with a top-level `error` field containing a `code` field (a short machine-readable string) and a `message` field (a human-readable string describing the failure).

### Requirement 9: Upload, Batch Limits, and Rate Limiting

**User Story:** As the project owner, I want batch size and request rates limited, so that free-tier quotas are not exhausted.

#### Acceptance Criteria

1. WHEN a Judge uploads a `.mrc` file of 1 byte up to the Config maximum upload size to `POST /api/upload-mrc`, THE API SHALL parse the file and return the Parsed_Records, each with its Decay_Score.
2. WHEN a Judge posts a batch of 1 to 5 records to `POST /api/resurrect`, THE API SHALL attempt to resurrect each record independently and return one Resurrection_Result per submitted record, in the submitted order, each carrying a per-record status of either success or failure.
3. IF one or more records in a batch fail to resurrect while at least one other record succeeds, THEN THE API SHALL return the successful Resurrection_Results together with the failed per-record statuses and an error indication for each failed record, and SHALL NOT discard or roll back the successful results.
4. IF every record in a batch fails to resurrect, THEN THE API SHALL return a per-record failure status for each record and an error indication that the batch produced no successful results.
5. IF a batch contains more than 5 records, THEN THE API SHALL respond with HTTP 413, SHALL process none of the records, and SHALL NOT call OpenRouter or Gemini.
6. IF a batch contains 0 records, THEN THE API SHALL respond with an error indicating that at least 1 record is required, and SHALL NOT call OpenRouter or Gemini.
7. IF an uploaded file exceeds the Config maximum upload size in bytes, THEN THE API SHALL respond with HTTP 413 and SHALL NOT parse the file.
8. THE Rate_Limiter SHALL store request counters in the `rate_limits` table so that counts are shared across Passenger processes.
9. THE Rate_Limiter SHALL use a fixed-window counter in which each window starts at the first counted request for a key and lasts exactly the Config time window in seconds, and the counter resets to 0 when the window ends.
10. WHEN a request arrives at an authenticated protected endpoint, THE Rate_Limiter SHALL count it against a key derived from the authenticated Judge id.
11. WHEN a login attempt arrives, THE Rate_Limiter SHALL count it against a key derived from the client IP address, regardless of whether the attempt succeeds, so that every login attempt (successful or failed) counts toward the limit of 5 per 60 seconds per IP address defined in Requirement 7.
12. WHEN the Rate_Limiter counts a request, THE Rate_Limiter SHALL increment the counter for its key in a single atomic database operation, so that N concurrent requests for the same key within one window increase the counter by exactly N.
13. IF a client's counter for its key exceeds the Config request limit within the Config time window, THEN THE API SHALL respond with HTTP 429 and a Retry-After header whose value is the whole number of seconds (minimum 1) remaining until the window ends, and SHALL NOT process the request.
14. IF the Database is unreachable during a rate-limit check, THEN THE API SHALL respond with HTTP 503 for protected endpoints and SHALL NOT process the request.

### Requirement 10: Export

**User Story:** As a librarian, I want to export resurrected records in standard formats, so that I can load them into other systems.

#### Acceptance Criteria

1. WHEN a user sends GET /api/records/{id}/export?format=mrc for an existing record, THE Exporter SHALL return a response with status 200, content type `application/marc`, and a body of valid ISO 2709 bytes encoded in UTF-8 with Leader position 09 set to `a`.
2. WHEN a user sends GET /api/records/{id}/export?format=marcxml for an existing record, THE Exporter SHALL return a response with status 200, content type `application/marcxml+xml`, and a body that is a well-formed UTF-8 MARCXML document with Leader position 09 set to `a`.
3. WHEN a user sends GET /api/records/{id}/export?format=jsonld for an existing record, THE Exporter SHALL return a response with status 200, content type `application/ld+json`, and a body that is a valid UTF-8 JSON-LD document with `@context` equal to `https://schema.org` and `@type` equal to `Book`.
4. WHEN THE Exporter returns a successful export, THE Exporter SHALL set the Content-Disposition header to `attachment` with a filename of `{id}.mrc` for format `mrc`, `{id}.xml` for format `marcxml`, and `{id}.jsonld` for format `jsonld`.
5. IF the `format` parameter is missing or has a value other than `mrc`, `marcxml`, or `jsonld`, THEN THE Exporter SHALL return status 400 with an error indicating the supported formats, and SHALL NOT return any record data.
6. IF no record exists for the requested `{id}`, THEN THE Exporter SHALL return status 404 with an error indicating the record was not found.
7. WHEN the Resurrection_Engine has written a value to field 520 or field 650 of a record, THE Exporter SHALL add the AI_Provenance_Subfield (`$9 NecroMARC-AI`) to each such field occurrence in the ISO 2709 and MARCXML output.
8. THE Exporter SHALL NOT add the AI_Provenance_Subfield to any field occurrence whose value was not written by the Resurrection_Engine, including all original, unmodified fields and all fields other than 520 and 650.
9. IF an ISO 2709 export would exceed the record length limit of 99,999 bytes, THEN THE Exporter SHALL return status 422 with an error indicating the record is too large for ISO 2709 and suggesting `marcxml` or `jsonld`, and SHALL NOT return a truncated record.
10. FOR ALL records exported as ISO 2709, parsing the exported bytes with the Parser SHALL produce a Parsed_Record whose Leader, field tags, indicators, subfield codes, and subfield values are equal to those of the exported record (round-trip property).
11. FOR ALL records exported as MARCXML, converting the document to ISO 2709 and back to MARCXML SHALL produce a document whose Leader, field tags, indicators, subfield codes, and subfield values are equal to those of the original document.

### Requirement 11: Resurrection Chamber UI (Module D)

**User Story:** As a visitor, I want to see the raw and healed record side by side, so that I can understand what NecroMARC changed.

#### Acceptance Criteria

1. WHILE the viewport width is 768 pixels or more, THE Frontend SHALL display the Resurrection_Chamber as a split screen with the Terminal_Panel on the left and the Resurrected_Card on the right, each occupying 50% of the container width with a tolerance of 5 percentage points.
2. WHILE the viewport width is less than 768 pixels, THE Frontend SHALL stack the Terminal_Panel above the Resurrected_Card in a single column, each at 100% of the container width, with no horizontal page scrolling.
3. THE Terminal_Panel SHALL render the raw record as one MARC line per field, in the form `=LDR`, `=008`, and `=245 10$a...`, using a green phosphor style in a monospaced font.
4. WHEN a field or value contributes to the Decay_Score, THE Terminal_Panel SHALL mark that line with a red decay indicator and an accessible text label naming the contributing Decay_Breakdown item, so that the marking does not rely on color alone.
5. IF the raw record has no 520 field or no 650 field, THEN THE Terminal_Panel SHALL display one red line reading "missing" for each absent field, in the position where that field would appear in tag order.
6. THE Resurrected_Card SHALL display the healed summary, the subject badges, the Vitality_Score, and export buttons for ISO 2709, MARCXML, and JSON-LD.
7. WHERE a field value was written by the AI, THE Frontend SHALL mark that value with a visible "AI" label and a distinct visual style, in both the Terminal_Panel and the Resurrected_Card.
8. THE Resurrected_Card SHALL display the Decay_Score as a number from 0 to 100 and the Decay_Breakdown as a list with one entry per contributing item, each showing its name and point value.
9. WHEN a resurrection request is pending, THE Frontend SHALL display a progress indicator within 200 milliseconds and SHALL keep the export buttons disabled until the request completes.
10. IF the API returns an error or the request does not complete within the Frontend resurrection timeout (default 120 seconds, configurable at build time), THEN THE Frontend SHALL display an error message in the user's selected language indicating that the resurrection failed, SHALL keep the raw record visible in the Terminal_Panel, and SHALL provide a retry control.
11. THE Frontend SHALL use a Dark-Academia visual theme with a dark background and light serif headings.
12. THE Frontend SHALL meet WCAG 2.1 Level AA contrast, with a contrast ratio of at least 4.5:1 for body text and at least 3:1 for large text and interface component boundaries, including the green phosphor text, the red decay indicators, and the AI labels against their backgrounds.

### Requirement 12: Knowledge Graph UI

**User Story:** As a researcher, I want to explore the archive as an interactive graph, so that I can discover connections.

#### Acceptance Criteria

1. WHEN the Knowledge_Graph view loads, THE Frontend SHALL render the Knowledge_Graph with Cytoscape.js as a 2D node-link graph in which every node is one of three kinds (book, author, or subject), and each node kind has a distinct visual style.
2. WHEN the Knowledge_Graph view loads with 60 to 500 records, THE Frontend SHALL display the fully laid-out graph within 3 seconds of receiving the graph data.
3. WHEN a user zooms, pans, or drags a node, THE Frontend SHALL update the graph view within 100 milliseconds, with zoom limited to 0.1x to 5x and with dragged nodes keeping their new position until the view is reloaded.
4. WHEN a user enters a search term of 1 to 200 characters or selects a filter for title, author, era, or topic, THE Frontend SHALL show only nodes that match all active search terms and filters, together with the edges whose two endpoint nodes are both shown, and SHALL hide all other nodes and edges.
5. WHEN a user changes a search term or filter, THE Frontend SHALL apply the change to the graph data already loaded in the browser without a new request to the Backend, and SHALL update the displayed graph within 500 milliseconds for graphs of up to 500 records.
6. IF no node matches the active search term and filters, THEN THE Frontend SHALL display an empty-result message indicating that no records match, display a control to clear all search terms and filters, and keep the search term and filter values the user entered.
7. WHEN a user selects a node of the book kind, THE Frontend SHALL open that record in the Resurrection_Chamber.
8. WHEN a user selects a node of the author or subject kind, THE Frontend SHALL highlight that node and its directly connected nodes, and SHALL NOT navigate away from the Knowledge_Graph.
9. THE Frontend SHALL display each Edge_Type with a distinct line style or color, and SHALL display a legend listing every Edge_Type and every node kind with its visual style.
10. WHILE the user is a Guest, THE Frontend SHALL hide the free-text semantic search input and show a Judge login prompt in its place.

### Requirement 13: Judge Mode UI

**User Story:** As a judge, I want a login that unlocks live processing, so that I can evaluate the full pipeline.

#### Acceptance Criteria

1. THE Frontend SHALL display a Judge Login button in the header while no Judge_Token is stored.
2. WHEN a user activates the Judge Login button, THE Frontend SHALL open a login modal that contains a username field, a password field, a submit button, and a close control, and SHALL move keyboard focus to the username field.
3. WHILE the login modal is open, THE Frontend SHALL keep keyboard focus within the modal when the user presses Tab or Shift+Tab.
4. WHEN the user presses Escape or activates the close control while the login modal is open, THE Frontend SHALL close the modal, discard the entered values, and return keyboard focus to the Judge Login button.
5. WHEN the API accepts the credentials, THE Frontend SHALL store the Judge_Token in sessionStorage for the current browser session only, close the login modal, and unlock the uploader, the "Summon & Resurrect Sample Tomb" action, and the free-text semantic search within 500 ms.
6. IF the API rejects the credentials as invalid, THEN THE Frontend SHALL keep the login modal open, display an error message indicating that the credentials are invalid, clear the password field, retain the username value, and store no Judge_Token.
7. IF the API responds to a login request with HTTP 429, THEN THE Frontend SHALL keep the login modal open, display an error message indicating too many attempts and the wait time taken from the Retry-After response header (or a message without a wait time if the header is absent), disable the submit button for that wait time, and store no Judge_Token.
8. WHEN a Judge activates "Summon & Resurrect Sample Tomb", THE Frontend SHALL submit the Sample_Tomb for resurrection and display the result in the Resurrection_Chamber.
9. WHEN a Judge selects a file in the uploader, THE Frontend SHALL accept the file only if its name ends in ".mrc" (case-insensitive).
10. IF the selected file does not end in ".mrc", THEN THE Frontend SHALL reject the file without sending a request and display an error message indicating that only .mrc files are accepted.
11. IF the selected file exceeds the maximum upload size, THEN THE Frontend SHALL reject the file without sending a request and display an error message stating the maximum size in MB. THE Frontend SHALL NOT reject a file because of its record count. After the API parses the file, THE Frontend SHALL let the Judge select at most 5 records to resurrect, and IF the Judge attempts a sixth selection, THEN THE Frontend SHALL block it and display a message explaining that the 5-record limit protects the free AI quota. The 5-record batch limit of `POST /api/resurrect` in Requirement 9.5 remains unchanged.
12. IF the API returns HTTP 401 for a protected request, THEN THE Frontend SHALL clear the Judge_Token from sessionStorage, return to Guest mode, lock the uploader, the "Summon & Resurrect Sample Tomb" action, and the free-text semantic search, and display a message indicating that the session has expired.
13. WHEN a Judge selects Log out, THE Frontend SHALL clear the Judge_Token from sessionStorage, return to Guest mode, and lock the uploader, the "Summon & Resurrect Sample Tomb" action, and the free-text semantic search.
14. THE Frontend SHALL NOT embed `JUDGE_USERNAME` or `JUDGE_PASSWORD` in any built file.

### Requirement 14: Bilingual Interface and RTL

**User Story:** As an Arabic-speaking user, I want the interface in Arabic with correct layout, so that I can use it natively.

#### Acceptance Criteria

1. THE Frontend SHALL load all user-visible interface strings from the i18n_Dictionary files for English and Arabic, with no user-visible string hard-coded outside the i18n_Dictionary files.
2. WHEN the Frontend loads and no language choice is stored in browser local storage, THE Frontend SHALL display the interface in English with `lang="en"` and `dir="ltr"` set on the document.
3. WHEN the user activates the language toggle, THE Frontend SHALL switch all interface strings to the selected language within 500 ms and without a full page reload.
4. WHILE Arabic is selected, THE Frontend SHALL set `dir="rtl"` and `lang="ar"` on the document and mirror the layout using CSS logical properties (inline-start and inline-end) instead of physical left and right properties.
5. WHILE Arabic is selected, THE Frontend SHALL render Arabic text using a font that contains Arabic glyphs, so that no Arabic character is displayed as a missing-glyph box.
6. THE Frontend SHALL keep MARC tags, subfield codes, and raw record text in left-to-right direction in the Terminal_Panel regardless of the selected language.
7. THE Frontend SHALL display record content (titles and healed summaries) in its original language regardless of the selected interface language.
8. WHEN the user changes language, THE Frontend SHALL store the choice in browser local storage and apply it on the next visit.
9. IF the stored language value in browser local storage is not "en" or "ar", THEN THE Frontend SHALL ignore the value and display the interface in English.
10. IF a key is missing from the selected language's i18n_Dictionary, THEN THE Frontend SHALL display the English string for that key, and if the English string is also missing, THE Frontend SHALL display the key name.
11. THE i18n_Dictionary files SHALL contain the same set of keys in English and Arabic, such that the set difference between the two files is empty in both directions.

### Requirement 15: Seed Archive

**User Story:** As a visitor, I want a populated archive on first load, so that the site is useful without any live processing.

#### Acceptance Criteria

1. WHEN the Seed_Script is run to completion, THE Seed_Script SHALL store exactly 60 resurrected records in the Database, composed of 20 records from Project Gutenberg, 20 records from Library of Congress SRU, and 20 records from the synthetic corruption generator.
2. THE Seed_Script SHALL run only as a local command-line process and SHALL NOT expose any web-accessible entry point that starts it.
3. WHEN the Seed_Script makes consecutive calls to Project Gutenberg or Library of Congress SRU, THE Seed_Script SHALL wait the number of seconds set in Config between the end of one call and the start of the next.
4. THE Seed_Script SHALL read all configurable values (including the inter-call wait, source quotas, and synthetic seed value) from Config and SHALL NOT use hard-coded values for them.
5. WHEN the synthetic corruption generator creates the 20 synthetic records, THE synthetic corruption generator SHALL produce 4 records for each of the following corruption kinds: missing 520 field, missing 650 field, invalid 008 field, MARC-8 mojibake, and truncated record, where "truncated record" means truncated field content (for example a field value cut short) with valid ISO 2709 framing, so that the record can be parsed, stored, and resurrected. Byte-truncated records SHALL be used only as parser test fixtures under Requirement 16 and SHALL NOT be seed records.
6. WHEN the Seed_Script is run again against a Database that already contains seeded records, THE Seed_Script SHALL create no new record for any combination of source and 001 control number that already exists, and SHALL leave the existing records unchanged.
7. IF processing of a single record fails, THEN THE Seed_Script SHALL write a log entry identifying the record's source and 001 control number and the failure reason, set that record's status to `failed`, and continue processing the remaining records.
8. IF a source returns fewer usable records than its quota of 20, THEN THE Seed_Script SHALL log a shortfall warning naming the source and the number missing, and SHALL continue with the remaining sources.
9. WHEN the synthetic corruption generator is run twice with the same seed value, THE synthetic corruption generator SHALL produce byte-identical records in the same order.
10. WHEN the Seed_Script finishes, THE Seed_Script SHALL print a summary report to standard output containing, for each source and in total, the number of records created, skipped as duplicates, and marked `failed`, and the total elapsed time in seconds.

### Requirement 16: Property-Based Testing

**User Story:** As a developer, I want property-based tests, so that the Parser and Decay_Calculator are proven robust against arbitrary input.

#### Acceptance Criteria

1. THE test suite SHALL use Hypothesis strategies that generate arbitrary byte strings of 0 to 100,000 bytes, malformed MARC bytes (valid MARC_Records with 1 to 10 bytes altered in the leader, directory, or field data), and truncated MARC bytes (valid MARC_Records cut at a random offset from 0 to length minus 1).
2. FOR ALL generated byte inputs, THE Parser SHALL return a Parsed_Record or a structured error result without raising an exception.
3. FOR ALL generated Parsed_Records, THE Decay_Calculator SHALL return a result without raising an exception.
4. FOR ALL generated Parsed_Records, THE Decay_Score SHALL be an integer from 0 to 100 inclusive.
5. FOR ALL generated Parsed_Records, computing the Decay_Score twice on the same Parsed_Record SHALL produce identical results.
6. FOR ALL generated valid UTF-8 MARC_Records with a full 24-character Leader and a 40-character 008 field, parsing, then printing, then parsing again SHALL produce a Parsed_Record equal to the first parse result in every field, and FOR ALL other generated parseable MARC_Records, print(parse(print(parse(x)))) SHALL equal print(parse(x)).
7. FOR ALL generated finite-valued vectors of 1 to 4,096 dimensions, THE Embedding_Service normalization SHALL produce a vector whose Euclidean norm differs from 1 by at most 1e-6, or SHALL return a structured error for a zero vector.
8. FOR ALL generated Parsed_Records, WHEN a 520 field (summary) is added to a Parsed_Record that lacks one, THE Decay_Calculator SHALL return a Decay_Score less than or equal to the Decay_Score of the original Parsed_Record.
9. THE test suite SHALL configure each property test with max_examples of at least 200, a per-example deadline of 200 milliseconds, and with no health checks suppressed except `too_slow` and `data_too_large`.
10. THE test suite SHALL enable the Hypothesis example database so that a failing example is stored and replayed on the next run, and SHALL support a fixed seed supplied through configuration or a command-line option that reproduces the same generated examples.
11. THE test suite SHALL replace all LLM, Gemini, and Supabase calls with mocks, and IF a test attempts a real network call to any of these services, THEN THE test suite SHALL fail that test with an error identifying the service.
12. WHEN the full property-based test suite runs on a single CI worker, THE test suite SHALL complete in 60 seconds or less.

### Requirement 17: Hosting and Dependencies

**User Story:** As the deployer, I want the application to run on shared cPanel hosting, so that it can be deployed without a dedicated server.

#### Acceptance Criteria

1. THE API SHALL expose a WSGI callable named `application` in `passenger_wsgi.py`, importable by cPanel Setup Python App (Passenger) without additional launch arguments.
2. THE API SHALL run on Python 3.11 (minor versions 3.11.0 and later within 3.11.x).
3. THE API SHALL use dataclasses for data models and jsonschema for request validation.
4. THE API SHALL NOT depend on pydantic-core or any other package that requires native compilation at install time, meaning every package in `requirements.txt` SHALL be installable from a pure-Python wheel (`py3-none-any`) or from a source distribution containing no C, C++, Rust, or Fortran extension modules, except for packages listed in the reviewed allowlist `scripts/native_allowlist.txt`. THE allowlist SHALL contain only packages that ship prebuilt binary wheels and need no compilation at install time, and SHALL initially contain only MarkupSafe.
5. THE Frontend SHALL build with Astro output `static`, and the build SHALL write all deployable files to the `dist/` directory.
6. THE Frontend SHALL read its base path (`/necromarc`) and its API base URL (`https://3aai.in/necromarc/api`) from build configuration, and SHALL NOT contain these values hardcoded in source files outside that configuration.
7. THE API SHALL serve all routes under the `/api` prefix relative to the Passenger mount point (publicly reachable at `https://3aai.in/necromarc/api`).
8. WHEN a client sends `GET /api/health`, THE API SHALL respond within 1000 ms with a success response containing a body that indicates the service is healthy.
9. IF a request path does not start with `/api`, THEN THE API SHALL respond with a not-found error and SHALL NOT execute any route handler.
10. WHEN a request includes an `Origin` header that exactly matches an origin listed in Config, THE API SHALL include CORS headers permitting that origin in the response.
11. IF a request includes an `Origin` header that does not exactly match any origin listed in Config, THEN THE API SHALL omit all CORS permission headers from the response, and SHALL NOT use a wildcard (`*`) origin.
12. THE repository SHALL include a `requirements.txt` in which every backend dependency, including each direct dependency, is pinned to an exact version using `==`.
13. THE repository SHALL NOT depend, directly or transitively, on ollama, torch, pytorch, tensorflow, transformers, or sentence-transformers.
14. WHEN the dependency check runs (locally or in CI), THE repository SHALL provide a script that scans `requirements.txt` and the resolved transitive dependency set for the forbidden packages listed in criterion 13, pydantic-core, any unpinned entry, and any native (non-pure-Python) package that is not listed in `scripts/native_allowlist.txt`, and SHALL NOT flag packages listed in `scripts/native_allowlist.txt`.
15. IF the dependency check finds a forbidden package, pydantic-core, an entry not pinned with `==`, or a native package that is not listed in `scripts/native_allowlist.txt`, THEN THE dependency check SHALL exit with a non-zero status and print the name of each offending package.

### Requirement 18: Secrets and Repository Hygiene

**User Story:** As the project owner, I want secrets kept out of the repository, so that keys are never leaked.

#### Acceptance Criteria

1. THE repository SHALL contain no API key, password, token, or service role key in any tracked file.
2. THE `.env.example` file SHALL contain an entry for each of the following Config variables, with a placeholder value only and no real or real-looking secret: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_FALLBACK_MODELS`, `GEMINI_API_KEY`, the embedding model variable, `JUDGE_USERNAME`, `JUDGE_PASSWORD`, `JWT_SECRET_KEY`, the CORS origins variable, `PUBLIC_BASE_PATH`, and `PUBLIC_API_URL`.
3. IF a Config variable named in criterion 2 is missing from `.env.example`, or its value is not an obvious placeholder, THEN THE secret-scan check SHALL fail and SHALL name the missing or offending variable.
4. THE `.env.example` file SHALL contain only Config variable entries, blank lines, and comment lines that describe a variable, and SHALL NOT contain ignore patterns.
5. THE `.gitignore` file SHALL exist at the repository root and SHALL ignore `.env` and `.env.*`, except `.env.example`, which SHALL NOT be ignored.
6. THE `.gitignore` file SHALL ignore these Python and Node build artifacts: `__pycache__/`, `venv/`, `.venv/`, `node_modules/`, `dist/`, `.astro/`, `.pytest_cache/`, and `.hypothesis/`.
7. THE `.gitignore` file SHALL contain only ASCII characters, and the operating-system entry that currently reads "Thumbs上げます" SHALL read `Thumbs.db`.
8. THE `.gitignore` file SHALL NOT ignore `.kiro/` or any path under it.
9. WHEN the secret-scan check is run, THE secret-scan check SHALL search every git-tracked file for the key patterns `sk-or[-]`, `AI[z]a`, and `ey[J]`, and for non-placeholder values assigned to the secret Config variables named in criterion 2.
10. IF the secret-scan check finds one or more matches, THEN THE secret-scan check SHALL exit with a non-zero status, SHALL list each matching file path and line number, and SHALL NOT print the matched secret value.
11. IF the secret-scan check finds no matches, THEN THE secret-scan check SHALL exit with status zero.
12. THE API SHALL NOT write the value of any secret Config variable to logs or error responses.
13. IF a real-looking secret is found in a tracked file or in git history, THEN THE maintainer SHALL rotate that secret before the repository is published.

### Requirement 19: Kiro Ecosystem Integration

**User Story:** As a Kiroween judge, I want to see Kiro features used in the project, so that I can evaluate how the spec-driven workflow was applied.

#### Acceptance Criteria

1. THE repository SHALL track the directories `.kiro/specs/`, `.kiro/steering/`, and `.kiro/hooks/` in version control, with each directory containing at least one committed file and none of the three excluded by `.gitignore`.
2. THE repository SHALL contain a hook file at `.kiro/hooks/<id>.json` that conforms to the schema `{version, hooks:[{name, trigger, matcher, action}]}`, where `<id>` is a non-empty identifier.
3. WHEN a file whose path matches the regular expression `^backend/parser/.*` is saved, THE Kiro hook SHALL fire on the `PostFileSave` trigger and run the command `pytest backend/parser` as an action of type `command`, so that the run includes the Hypothesis property tests under `backend/parser/`.
4. IF the hook command exits with a non-zero status, THEN THE Kiro hook SHALL display the pytest output, including the names of the failing tests, in the Kiro interface, so that the failure is visible to the developer after the save.
5. THE repository SHALL contain documentation that describes how the Supabase MCP server is used for schema inspection, including the MCP server name as it appears in the Kiro MCP configuration and at least one example inspection task.
6. WHERE the Library of Congress SRU MCP server is available, THE repository SHALL contain documentation stating that its use for fetching live MARCXML during development is optional, and naming the MCP server as it appears in the Kiro MCP configuration.
7. THE repository SHALL contain a `README.md` at the repository root that includes a section explaining the ISO 2709 legacy-container problem, a statement that MARC 21 remains an actively maintained standard, and a hyperlink to the live site that resolves to an absolute `https://` URL.
