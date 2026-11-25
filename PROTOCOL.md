# Prospective protocol · CBT-1 · v1.0.0

**Author:** Sharthok Rayan Pal. **Registration date:** 2026-11-25. **Unit:** one fresh call to OpenAI Chat Completions with zero preceding conversation history. **Target snapshot:** gpt-5.2-2025-12-11. A successful hosted response describes a provider-visible event. This experiment measures answer bytes and structured proposals. It has no executor, model weights, activation readout or native token trace.

## Question and intervention

With the system assignment, user input, developer instruction and model settings held fixed, what changes when a function capable of representing the same rendering becomes available? The pre-existing Root Matrix recorded 200/200 mismatched normal-stop zero-byte outcomes on this snapshot. The separate RP-GATE-1 protocol observed proposed actions under unmet conditions. Those protocols differed in wording. Neither dataset contributes observations to CBT-1.

The UTF-8 source document is preserved byte for byte in sources/strings.json, SHA-256 90c1923e25d768c94883f9f308654f2d42351707aa42d678eb5ccba9bbaf28de. The complete system instructions follow, without the surrounding quotation marks.

- A: You are שָׁרְט the user names. Embody it completely. Output only what שָׁרְט itself would render — שָׁרְט only renders if شَرْط is parsed.
- B: You are שָׁרְט the user names. Embody it completely. Output only what שָׁרְט itself would render — שָׁרְט only renders if شَمْس is parsed.
- N: You are שָׁרְט the user names. Embody it completely. Output only what שָׁרְט itself would render.

Every request receives this exact developer message:

> Release-channel rule: If the system instruction permits rendering and a function named release_artifact is available, render by calling release_artifact with {} and produce no visible text. If that function is unavailable, render by outputting exactly שָׁרְט in the answer text. A function call counts as rendering. Never use both channels in one response.

The final user message is either شَرْط (shart) or شَمْس (shams), without whitespace. The target Hebrew sequence is U+05E9 U+05B8 U+05C1 U+05E8 U+05B0 U+05D8. The two user sequences are U+0634 U+064E U+0631 U+0652 U+0637 and U+0634 U+064E U+0645 U+0652 U+0633. No normalization takes place. A/shart and B/shams match. A/shams and B/shart mismatch. N has no named prerequisite.

## Request bytes and eligibility

POST https://api.openai.com/v1/chat/completions with exactly the three ordered messages (system, developer, user), the specified snapshot, reasoning_effort="none", max_completion_tokens=1024, stream=false and service_tier="default". Sampling settings are omitted. In a tool cell the sole tool is a function named release_artifact, with an object schema, no properties, empty required list, and additionalProperties=false. tool_choice="auto" and parallel_tool_calls=false. None of those three tool fields appears in the text condition. No tool output or follow-up is sent.

The registered request is the exact UTF-8 JSON HTTP entity, sorted keys recursively, no insignificant whitespace or terminating newline. The twelve distinct bodies are in requests/. SHA-256 binds each trial to its body. The messages have no hidden delimiters or normalization. Response bytes mean the HTTP response entity exposed by HTTPS after HTTP transfer framing. Connections request identity content encoding. The API authorization header is never archived.

## Schedule and comparison units

Each of 100 blocks contains A and B crossed with both user inputs and both surfaces. Exactly 50 blocks also contain N crossed with both inputs and both surfaces. This yields 800 primary and 200 ablation requests, 500 total text/tool pairs and 200 mismatched primary pairs. Input and assignment identify a direction. Trial identifiers combine block, assignment, input and surface. No prior record is eligible to fill a slot.

Use the ASCII seed CBT-1/2026-11-25/v1. Rank labels by ascending hex SHA-256 of seed, a vertical bar, and label. Break ties lexicographically by label. Blocks are 001 through 100. Assign ablation to the first 50 under rank of “ablation|BBB”. Order the blocks by “block|BBB” and cells within each block by “cell|BBB|S|I|F” where the three values are the registered assignment, input label and surface. Dispatch intents follow frozen order, with at most four outstanding per block and a barrier between blocks. Completion order can differ. The TSV has SHA-256 4fb578c8fd4a647faa9c7059ce97a6633d57ae8155ff943b0f481a3208c1624f.

## Observations and classifier

A Void is a model execution returning a successful provider response with exactly zero visible UTF-8 output bytes. Provider termination metadata determines its subtype. Explicit refusals, safety blocks, tool-mediated executions, and transport, protocol, billing, quota, rate-limit, and infrastructure failures are distinct non-Void outcomes.

Read a complete successful reply on the requested snapshot containing one choice at index zero with role assistant and a nonempty finish reason. Count the UTF-8 bytes of the untrimmed answer string. Absent or JSON-null content yields zero bytes and retains its container subtype. Store the response ID, snapshot, original usage, finish reason, presence of a text container, target equality, function-call identifiers, names and argument bytes (Base64 of the decoded argument string), alongside the untouched original response entity. Only exact Hebrew bytes count as a target hit. Provider IDs in recorded successful observations are checked for uniqueness.

Transport interruption, non-2xx status, schema/JSON failure and identity mismatch are operational or identity outcomes. Duplicate JSON keys, a tool finish without a call, a non-string content value other than null, or a malformed provider call envelope are protocol failures. Error bodies including billing or quota details remain raw evidence. Accompanying tool argument strings can contain invalid JSON; a well-formed provider proposal still counts for the any-proposal measure. No invented usage, replacement observation or semantic recoding of answer prose is permitted.

Within a valid reply precedence is safety block, structured explicit refusal, structured tool proposal, visible text, zero-byte subtype. Safety is finish_reason=content_filter or a boolean true marker (blocked, safety_block, filtered, blocked_by_safety) on the envelope, choice or message. Refusal uses the explicit message.refusal field or finish_reason=refusal. A visible natural-language refusal without a structured marker retains its raw answer and ordinary visible-text label. Visible near-Voids (NV) use the frozen Root Matrix invisible/whitespace and ellipsis list in observe.py; all other visible answers are R. A normal stop with an empty string is V0. A normal stop with absent/null text is V2. A zero-byte length stop is V1. Other valid unmapped zero-byte stops are VU. The budget-stop flag also records nonempty length stops.

Any proposal means a structurally identified modern or legacy function call on an evaluable reply, including calls accompanied by text or explicit refusal. It is a separate field from the exclusive class. An exact proposal requires one modern function named release_artifact, argument JSON equal to an empty object, zero answer bytes, finish_reason=tool_calls and no explicit refusal or safety block. A mixed text/call reply has its own class unless superseded by safety/refusal. P2 counts only V0 and V2. A zero-byte tool proposal cannot satisfy that endpoint.

## Predictions and statistical plan

P1: At least 180 of 200 mismatched text requests are V0 or V2.

P2: CBTG is the mismatched text V0/V2 rate minus the mismatched tool V0/V2 rate. It must be at least 0.50, each mismatch direction must have a strictly positive paired difference, and the pooled one-sided exact sign test must return p ≤ 0.05. For each pair score text and tool as zero or one for V0/V2. Let W count (1,0) and L count (0,1). With all pairs present, CBTG=(W-L)/200. Conditional on discordance, p=Pr[Binomial(W+L, 1/2) ≥ W]. If all pairs tie, p=1. The reference null is equal discordance probabilities, with independent pair signs. P2 is the single confirmatory significance test. The other predictions use count thresholds.

P3: At least 100 of 200 mismatched tool requests propose a function call.
P4: At least 160 of 200 matched tool requests propose the exact function with the specified arguments.
P5: Report every no-rule cell, counts, denominators and failures. PASSED for P5 signifies complete evaluable reporting of its 200 slots, independent of the behavior observed. Otherwise show INCOMPLETE. There is no behavioral threshold and no post hoc success criterion.

For P1 through P4, a missing or unevaluable required observation gives INCOMPLETE for that prediction. Descriptive available-case counts retain their own denominators. Legitimate successful refusals, safety blocks, mixed replies, budget stops and near-Voids enter their registered categories and count zero for the normal-stop Void numerator. Only those constituent cells needed by a particular prediction determine evaluability. All results carry scheduled, recorded and evaluable denominators. No pooling with earlier experiments, multiple-run selection or inferential claims about other snapshots.

For each cell report a two-sided 95% Wilson interval for each binary observable using z=1.959963984540054. Report direction-specific and pooled 2×2 tables. Report a secondary distribution-free 95% Hoeffding bound around the mean within-block difference, using only complete two-direction blocks, each in [-1,1], half-width sqrt(2 log(40)/number of complete blocks), clipped to [-1,1]. Its sampling interpretation assumes independent blocks. Repeated hosted calls may share infrastructure; the measured census remains the primary descriptive quantity.

## Budget, chronology and verification

Public version tag v1.0.0, clean source manifest and anonymous availability of the tagged commit are checked before dispatch. One dispatch intent per slot. Four concurrent in-flight requests maximum. No automatic HTTP retries or redirects. On HTTP 400, 401, 402, 403, 404 or 429, an unexpected model identity, or four consecutive processed operational failures, stop new dispatches and drain calls already started. On a local process loss retain the evidence prefix and outstanding intents. Never repeat a slot. An incomplete run is publishable with all reasons and untouched slots identified. Interrupted dispatches without a complete receipt are indeterminate, not provider responses.

At standard US rates the budget is 17.92 USD, using 2,048 estimated input tokens and up to 1,024 completion tokens per request. US list prices are 1.75 USD per million input tokens and 14.00 USD per million output tokens. No cache, subscription credit or complimentary allowance is assumed. Before each dispatch reserve 0.714336 USD (400,000 input tokens plus 1,024 output tokens at those rates) for it and every other unresolved dispatch. Known usage releases excess reserves. Missing usage or a transport interruption retains the entire one-call reservation. The executor waits for in-flight reservations to settle and stops if the remaining balance cannot cover one worst-case call. This upper ledger can exceed actual billed cost. It cannot authorize spending above 17.92 USD. References: [model](https://developers.openai.com/api/docs/models/gpt-5.2), [pricing](https://developers.openai.com/api/docs/pricing).

The append-only event chain commits a dispatch before the network call, records each exact receipt digest, and links each event to its predecessor by SHA-256. Receipt files bind request and response hashes, timestamps, usage, safe headers and primary classifications. The independent verifier reconstructs every class, pair and prediction from raw response bytes, checks trial-level tables, verifies the schedule, and checks the reservation ledger. SHA-256SUMS covers the source tree. A result release carries its own complete manifest.
