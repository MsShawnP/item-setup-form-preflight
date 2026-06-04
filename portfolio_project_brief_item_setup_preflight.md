# Portfolio Project Brief: Item Setup Form Pre-flight

**Status:** Brainstorm / Brief stage
**Tier:** 2 (fixed-fee onboarding diagnostic + reusable schema/validation engine)
**Priority:** Build after the two in-progress pieces (Dimension & Weight Integrity, Remittance Stub Parsing). Sits at the *opposite end* of the lifecycle from remittance parsing — that piece is the last step (getting paid); this is the first step (getting on shelf). Together with EDI Pre-flight they form a "validate before you transmit" cluster across three different document types.
**Backlog ref:** #32 (Item setup form parsing PDF→structured, 32) + #34 (Retailer item setup form parsing, 32), absorbing #30 (Retailer-specific item setup schema mapping, 33).

---

### 1. The Pain

To get a new product onto a retailer's shelf, Cinderhaven has to fill out that retailer's **item setup form** — Walmart's Item 360 setup, Costco's item setup workbook, UNFI's and KeHE's new item forms. Each one is a sprawling form demanding dozens to hundreds of attributes per SKU: GTIN hierarchy, case pack, dimensions and weights, ti/hi, nutritional panel, ingredients, allergens, pricing, MAP, and a long tail of retailer-specific fields. **Every retailer's form is different** — different required fields, different formats, different GTIN hierarchy expectations.

The data to fill them is scattered — some in the ERP, some in a nutritional spreadsheet, some in artwork files, some in someone's head. So the form gets filled by hand, pulling from multiple sources, slightly differently each time. Then it gets submitted and **bounces**: a missing field, a GTIN at the wrong level of the hierarchy, dimensions in the wrong format. The item doesn't go live. The launch slips.

- **Who feels it most:** Whoever owns retailer onboarding — often a sales/ops hybrid or the COO at this size; the CEO feels it when a launch they're counting on for the year's growth number doesn't happen on time.
- **When it gets acute:** Every new retailer multiplies the form count; every new SKU multiplies the rows. A brand going from 2 retailers to 5 while pushing new items is filling and re-filling forms constantly, each in a different dialect.
- **How it compounds:** The growth plan *is* new retailer wins and new item launches. Form friction throttles exactly the thing the brand is betting on. At $25M it delays launches; on the way to $50M it means missing category-review windows entirely.

#### The Status Quo

A folder of blank retailer templates, a master product spreadsheet that's almost-but-not-quite complete, and a person copy-pasting fields from the ERP, the nutritional doc, and last year's submission into each new form. Rejections come back days or weeks later with terse error notes. The fixes are guesswork. Nobody has a single view of "is this product actually ready to submit to Costco specifically?"

### 2. Why This Piece

The published portfolio proves data analysis and (with the in-progress remittance piece) document extraction. **It does not yet show the discipline that prevents the most expensive failure in specialty food: a blown product launch.** Item setup is where clean product data either pays off or fails publicly, in front of the retailer, on a deadline.

- **Compounds with EDI Pre-flight (shipped).** Same philosophy — catch the error before you transmit it — applied to a different document (item setup forms vs EDI transactions). Cross-link them as the onboarding-stage and transaction-stage halves of the same "pre-flight" idea.
- **Reuses the GTIN Validator (shipped).** GTIN validation is one field-check inside this engine. The piece calls that logic rather than reinventing it — visible reuse that shows the portfolio is a connected system, not scattered demos.
- **Consumes Dimension & Weight Integrity's fields (in progress).** The physical attributes (weight, cube, L/W/H, ti/hi) that piece governs are exactly the fields a setup form demands. This piece validates that those fields are *present and format-valid for each retailer's form* — it does **not** re-litigate which weight is correct; that's Dimension & Weight's job. Clean handoff.
- **Distinct from PDH (shipped).** PDH measures structural completeness of the master in the abstract ("you're 87% complete"). This measures completeness against a *specific retailer's specific requirements* ("you're missing the 7 fields Costco requires, so this submission bounces"). Internal-general vs external-specific. Different question, different output.
- **Reinforces the primary buyer**, opens a slightly different angle: this is a *growth-enablement* story (get launches live faster) as much as a cost story, which lands with a CEO focused on the revenue plan.

### 3. The Portfolio Piece

**Working title:** *Why Your Item Didn't Make the Reset* (alts: *One Master, Every Retailer's Form*; *The New Item Form That Bounced*)

The reader meets the same new product as it heads into three different retailers — and watches it need three different field sets, three different GTIN hierarchies, three different "required" lists. Then they watch a pre-flight catch, before submission, every reason each form would have bounced. The arc: *the same product is "ready" or "not ready" depending entirely on which retailer you ask → here's exactly what each one will reject → fix it now, not after the window closes.*

#### Structure

- **Part 1 — The hook:** One Cinderhaven SKU against all four forms — but arranged as **two like-to-like comparisons, not a flat row**: retailer-vs-retailer (Walmart Item 360 vs Costco workbook) and distributor-vs-distributor (UNFI vs KeHE new item forms). The flat "here are four different forms" version just says *everything is different*. The paired version surfaces **structure**: what's shared inside a channel type and what diverges across them. The expected pattern — and the actual insight of the piece — is counterintuitive: the two *distributors* are structurally close to each other (both broadline new-item worksheets built around case logistics, cost tiers, and promo codes), while the two *retailers* diverge hard from each other on the single most consequential axis — the **GTIN hierarchy / primary sellable unit** (Walmart is consumer-unit-first; Costco is club-pack/case-first, because club retail and big-box grocery disagree about what "the product" even is). So your two retailers are *more different from each other* than your two distributors are. The takeaway reframes the whole problem: this isn't four idiosyncratic forms, it's **two structural families plus a known set of divergence axes** — which means a new form can be filled by analogy to its channel sibling instead of from scratch.
- **Part 2 — The proof:** Cinderhaven case study — a new-product launch run through the pre-flight against all four trading partners. Findings: N fields missing for Costco specifically, a GTIN assigned at the wrong hierarchy level for the club pack, dimension fields failing Walmart's format mask, a nutritional field present internally but in the wrong unit, and — surfaced by the paired view — that the same master is *nearly* submission-ready for both distributors once one shared gap is fixed, but needs genuinely different work for each retailer. Quantify the cost of submitting the errors uncaught (see Margin Math). Then show the *after*: a clean readiness verdict per partner.
- **Part 3 — The evidence:** The engine — a **retailer/distributor schema library** (each partner's item-setup spec codified as structured config: required fields, formats, GTIN-hierarchy rules, allowed values, conditional triggers), and a **validation engine** that scores the master against each schema and emits *typed, explainable* rejection risks. The engine runs a four-tier topology in order: (1) **Presence** — mandatory fields for the category; (2) **Format** — regex/mask checks (e.g., Walmart's dimension string masks); (3) **Conditional** — cross-field logic trees (e.g., `storage_type == "Refrigerated"` → temperature-zone fields required; `package_type == "Aerosol"` → Prop 65 fields required); (4) **GTIN hierarchy** — asserting the identifier resolves to the right unit class per partner (Costco's primary resolves to a Case/Pallet GTIN-14, not an Each UPC-12). Each failure returns a structured record, not a vague flag:

```json
{ "field": "storage_temp_min",
  "error_type": "CONDITIONAL_REQUIREMENT_MISSING",
  "trigger": "storage_type == 'Refrigerated'",
  "rejection_risk": "CRITICAL_BOUNCE" }
```

A separate **audit CLI** (in the repo, not the hosted demo) parses the standardized master export / a single generic draft sheet → structured, so the data can be pre-flighted from a file. It deliberately does **not** attempt to reverse-parse each partner's completed proprietary spreadsheet — hardcoding cell coordinates across Walmart's multi-tab workbook, Costco's, and two distributor sheets is a maintenance tar pit, and the PDF→structured extraction capability is already carried elsewhere in the portfolio (the remittance parser).

#### The Margin Math

Anchor to Cinderhaven's growth trajectory ($25M → $40–55M), which depends on new retailer wins and new item launches. Frame the cost of a bounced/late setup:

- **Lost launch velocity:** An item that goes live 6 weeks late loses ~6 weeks of sell-through on a shelf you're already committed to. On a SKU expected to do meaningful weekly velocity, quantify the lost units × contribution.
- **The window (the sharp number):** Retailers set items during **category review / shelf reset** cycles. Miss the window because the form bounced and you don't slip 6 weeks — you wait for the *next reset*, often 6–12 months out, and the slot may go to a competitor. This is the item-setup analog of the remittance dispute-window forfeit: not a delay, a forfeit of the whole cycle.
- **Slotting paid for empty shelf:** Slotting fees / launch commitments incurred for space the item isn't generating revenue on yet because setup stalled.
- **Rework labor:** Hours re-filling and re-submitting rejected forms, costed at a loaded rate.

#### Before / After

- **Before:** Fill each retailer's form by hand from scattered sources, submit, wait, get a rejection with a cryptic note, guess at the fix, resubmit, hope you make the window.
- **After:** One readiness view per retailer — "ready to submit to Walmart; NOT ready for Costco (missing 7 fields, GTIN at wrong hierarchy level, 2 format errors)." Fix the named gaps once, submit clean, make the reset.

#### Who Else Sees This?

- **Primary audience:** CEO/founder (it's a growth-plan story) and whoever owns retailer onboarding (COO / sales-ops).
- **Secondary audience:** The broker (who shepherds new-item submissions and lives the rejections), and the ops/data person who fills the forms.
- **How it gets shared:** Broker forwards to the brand with "this is why the Costco item didn't set." CEO forwards to ops with "we cannot miss the next reset — get us to a clean submission."

### 4. Technical Specification

#### Repo

- **Repo name:** `item-setup-preflight`
- **Repo description:** Retailer/distributor item-setup pre-flight — codified partner schemas + a typed validation engine that flags new-item form rejection risk before submission; runs client-side in the browser; audit CLI for local master exports.

#### Tech Stack

| Tool | Role in This Project |
|------|---------------------|
| Python | The single validation engine — authored once, run two ways (browser + CLI) |
| YAML schema library | Codified per-partner item-setup specs — required fields, formats, GTIN-hierarchy rules, allowed values, conditional triggers. The core reusable asset; the config itself is a portfolio artifact. |
| Pydantic (model/root validators) | Typed validation + the four-tier topology; conditional cross-field rules return structured error dicts (`field / error_type / trigger / rejection_risk`), not nested unreadable JSON-Schema `if/then/else` |
| GTIN Validator (reused) | Check-digit + format + hierarchy-level validation for GTIN fields — called, not reinvented |
| Pyodide / WASM | Runs the *same* Python engine entirely in the browser — no second copy of the rules in JS/TS (which would violate the single-source-of-truth thesis this practice preaches), and an airtight privacy story (the product master never leaves browser memory) |
| HTML5 / Tailwind / vanilla JS | The shareable schema-diff + readiness dashboard surface |
| openpyxl + click (audit CLI) | Repo-only utility to parse the standardized master export / generic draft sheet → structured, for local pre-flighting |
| SQLite | Case-study data store; reconcile against the Cinderhaven dataset |

#### Deliverables

| Deliverable | Format | Purpose |
|------------|--------|---------|
| Partner schema library | YAML in repo | The reusable asset — codified specs other practitioners can read and extend |
| Validation engine | Python package (browser + CLI) | Technical credibility — the four-tier rules engine + GTIN-hierarchy logic + typed error contract |
| Paired schema-diff view | Interactive, client-side (retailer-vs-retailer **and** distributor-vs-distributor, with the channel-type pattern called out) | The shareable lead-gen artifact — surfaces structure, not just difference |
| Readiness tool | Client-side web app via Pyodide (drop the master, get a per-partner readiness verdict + typed gap list, nothing uploaded) | Lead gen + the privacy narrative |
| Audit CLI | `click` utility in repo | Honors the parse-to-structured capability for local master exports without building per-retailer reverse-parsers |
| Case study write-up | HTML + PDF | The narrative proof, Cinderhaven launch scenario + the channel-pattern finding |

#### Deployment

- **Where:** Repo for engine + schema library + audit CLI; case study on the portfolio site (HTML/PDF); the readiness tool + schema-diff hosted as **static files** (GitHub Pages / Netlify) since Pyodide runs everything client-side — no server.
- **URL structure:** `item-setup-preflight` on the portfolio's static host.
- **How a prospect finds it:** Linked from EDI Pre-flight and GTIN Validator as the onboarding-stage companion; LinkedIn; ops people Googling "Walmart Item 360 required fields," "Costco item setup GTIN," "new item form rejected."

#### Simulated Data Sources

The product master "pulled from" the ERP + nutritional spreadsheet + artwork specs (deliberately scattered, so completeness gaps are realistic). Partner requirements codified from the real shape of **Walmart Item 360**, **Costco item setup workbook**, and the **UNFI** and **KeHE** new item forms — all four, since the paired comparison is the whole point. Audit-CLI input: a standardized master export / generic draft sheet, not per-retailer completed workbooks. The launch SKU's physical fields must match whatever Dimension & Weight Integrity establishes — no drift.

### 5. Skills Demonstrated

- Schema/spec engineering — translating messy, undocumented partner requirements into structured, machine-checkable config
- Rules-engine design with a typed, explainable error contract and an ordered four-tier validation topology (presence → format → conditional → GTIN hierarchy) — not pass/fail
- GTIN hierarchy fluency — knowing each/inner/case/pallet GTIN-14 levels and that retailers expect different ones
- Client-side Python via Pyodide/WASM — running one engine in the browser with zero data egress (rare in a portfolio; separates from the "everything is a Python backend" default)
- Analytical framing — the like-to-like channel comparison that turns "four idiosyncratic forms" into "two structural families plus divergence axes"
- System reuse — calling the existing GTIN Validator, consuming Dimension & Weight's fields, staying off PDH's turf
- Domain fluency: retailer/distributor item-setup mechanics, category-review windows, GS1/GDSN data expectations

### 6. Foot-in-the-Door Offering

- **Offering name:** New Item Setup Readiness (or "Retailer Onboarding Pre-flight")
- **Format:** Fixed-fee build — codify the client's target retailers' specs, validate their master against each, deliver a readiness verdict + populated/corrected forms ready to submit.
- **Price range:** $10K–$20K depending on number of retailers codified.
- **What the client gets:** A schema config for their target retailers, a per-retailer readiness report on their current master, a prioritized gap list, and submission-ready forms for the items they're launching now.
- **Why this piece is the sales collateral:** A CEO staring at a growth plan built on new retailer wins sees, concretely, the thing that silently kills those wins — and a way to stop missing windows.

#### Client Lift

- **What the client has to do:** One kickoff call, a list of target retailers + the items they're launching, and read access to / an export of the product master.
- **What we need from them:** Product master export, any blank retailer templates they've been handed, and a sample of any returned/rejected forms.

#### The DIY Defense

- Retailer requirements aren't published cleanly anywhere — they live in portal help text, broker tribal knowledge, and the scar tissue of past rejections. The value is the *codified schema*, which takes real reps to build correctly.
- The GTIN-hierarchy rules are a classic landmine: Costco expects the club/case pack at a different hierarchy level than Walmart expects the consumer unit. A generic "is the field filled?" check passes a wrong-level GTIN and the item still bounces. You have to encode the hierarchy logic, not just presence.
- "Required" is conditional: a field can be required only when another field has a certain value (e.g., refrigerated → temperature-zone fields required). Naive checklists miss conditional requirements; this is where in-house attempts fail quietly.

### 7. Marketing / Distribution

- **Portfolio integration:** Anchors an "onboarding / get-on-shelf" cluster with GTIN Validator and EDI Pre-flight; cross-link as the pre-flight family.
- **LinkedIn:** "Your item didn't miss the shelf because the product was wrong. It missed because the *form* was wrong — and the reset doesn't wait." Lead with the missed-window forfeit.
- **SEO / organic:** "Walmart Item 360 required fields," "Costco item setup workbook GTIN," "UNFI new item form," "why was my item setup rejected."
- **Shareability:** The schema-diff view (Walmart vs Costco vs UNFI required fields) is the forward-worthy artifact — ops people will send "look how different these are" to each other.
- **Lead capture:** Keep the readiness tool and schema-diff open. Lean open on the case study too, consistent with the buyer's skepticism of gates.

### 8. Competitor / Existing Content Scan

- **What exists:** Enterprise PIM/syndication platforms (Salsify, Syndigo, 1WorldSync's own tooling) that handle item setup at scale and at enterprise price/complexity; plus retailer portal help docs that describe fields but don't validate your data.
- **What's missing:** Nothing sized for a $25M–$50M food brand that wants to *know if it's ready before it submits*, without buying a full PIM. The enterprise tools assume you've already got clean governed data flowing in; this meets the brand at the messy-spreadsheet stage they're actually in.
- **Your angle:** A pre-flight, not a platform — codified retailer specs + a readiness verdict on the master you have today, framed around the missed-reset cost a PIM vendor never mentions.

### 9. Cinderhaven Integration

- **New asset:** partner item-setup schemas for all four — Walmart, Costco, UNFI, KeHE — codified as config, plus a new-product-launch scenario run against all four with the paired (retailer/retailer, distributor/distributor) comparison.
- **Reuses** the existing 90-SKU product master and the existing GTIN Validator logic. The launch SKU's **physical fields must match the Dimension & Weight Integrity piece** exactly — this piece consumes those fields, it does not redefine them.
- **Same retailers** as the rest of the portfolio (Walmart, Costco, Whole Foods, UNFI, KeHE) — no new trading partners.
- **Consistency requirement:** Any product attributes shown must match prior Cinderhaven pieces (GTINs, dimensions, case packs). This piece is downstream of PDH (completeness) and Dimension & Weight (physical fields) and must not contradict either.

### 10. Tactical Notes

- Get the partner specs *directionally real*. Exact field-for-field portal replication isn't the point (and changes constantly) — but the *shape* (Item 360 vs Costco workbook vs distributor new-item form) and the known gotchas (GTIN hierarchy differences, conditional requirements) must ring true to someone who's filled these.
- **The paired comparison is load-bearing — design the schemas so the channel pattern actually emerges.** The insight ("two distributors are more alike than the two retailers") only lands if the codified specs honestly reflect it: distributor schemas heavy on case logistics / cost tiers / promo codes and structurally similar to each other; retailer schemas diverging on the GTIN-hierarchy / primary-unit axis. Don't manufacture the pattern — but do make sure the synthetic schemas are faithful enough that it shows. If, when you codify them honestly, the pattern *doesn't* hold, report what actually emerges; a real finding beats a tidy one.
- Encode the **GTIN hierarchy** explicitly — the single most credible detail in the piece and the one a naive tool gets wrong.
- Write conditional rules as clean Pydantic validators returning the typed error contract, not nested JSON-Schema `if/then/else` (unreadable, and it can't produce operator-friendly error messages).
- Build the schema library as clean, readable YAML, because the *config itself* is a portfolio artifact — a practitioner reading it should think "this person actually knows what each partner wants."
- Keep the boundary with PDH and Dimension & Weight crisp in the write-up so the cluster reads as a designed system, not overlapping one-offs.

#### The Credibility Marker

Costco item setup requires a **different GTIN hierarchy** than Walmart — the club/case pack sits at a different level than Walmart's consumer unit, and an item submitted with the GTIN at the wrong level bounces even though "the field is filled." Pair that with knowing item setup is gated by **category-review windows**, so a rejected form doesn't just delay — it can forfeit the whole cycle. Generic data people check that fields are populated; a practitioner checks them against each retailer's hierarchy and the reset calendar.

#### Data Paranoia / Security

- **What's sensitive:** The product master and any pricing/MAP fields on setup forms; some brands treat their full attribute set and retailer relationships as confidential.
- **How the narrative reassures:** Runs against an export, can operate on obfuscated SKUs; the schema library is generic (retailer requirements, not the client's data); case study uses synthetic Cinderhaven data so no real product master is exposed.

### 11. Open Questions

*Resolved (June 4, 2026 — incorporating external review + the channel-comparison direction):*

- [x] **Interactive surface → client-side via Pyodide/WASM.** Runs the *same* Python validation engine in the browser (no second JS/TS copy of the rules — that would break the single-source-of-truth thesis), with an airtight privacy line: the product master is validated in browser memory and never uploaded. Hosted as static files. *Known cost, accepted:* Pyodide is a multi-MB payload with a few seconds of cold-start; fine for a drop-a-file demo. The audit parser moves out of the hosted demo into a repo CLI.
- [x] **Schema count → all four, arranged as two like-to-like comparisons** (Walmart vs Costco; UNFI vs KeHE). Not a flat row and not three-plus-one-in-repo: the paired structure is what produces the channel-type insight, which is the analytical payload of the piece.
- [x] **Audit scope → narrowed.** Parse the standardized master export / a generic draft sheet via CLI; do **not** build reverse-parsers for each partner's completed proprietary workbook (cell-coordinate tar pit, and PDF→structured is already carried by the remittance parser).
- [x] **Naming → keep "Pre-flight."** Cluster cohesion with EDI Pre-flight is an asset — it brands the practice's "intercept errors before they cost money" philosophy.

*Still open:*
- [ ] Whether the channel-pattern finding is strong enough to headline the piece (title/LinkedIn angle) or sits as a mid-piece reveal. Depends on how cleanly the pattern emerges once the four schemas are honestly codified — decide during build, not before.

### 12. Build Estimate

- **Effort level:** Medium. The schema library is the real work — getting retailer specs directionally right and encoding hierarchy/conditional logic. Validation engine is straightforward once schemas exist.
- **Dependencies:** Existing 90-SKU master and GTIN Validator (both shipped). **Dimension & Weight Integrity's physical fields** (in progress) — this piece consumes them, so the launch SKU's dims/weights should be locked there first to avoid rework.
- **New skills required:** Schema/spec engineering + a rules engine with explainable conditional validation (adjacent to EDI Pre-flight but more configuration-driven), plus running the Python engine client-side via **Pyodide/WASM** — the genuinely new build technique here.

#### Out of Scope

- Becoming a PIM — this is a pre-flight check, not a system of record or a syndication platform.
- Auto-submitting to retailer portals — the piece produces submission-ready output and a readiness verdict; it does not push to Item 360 / portals.
- Re-deciding physical field values — weight/cube/dims SSOT belongs to Dimension & Weight Integrity; this piece only validates presence + format for each retailer.
- General product-data completeness scoring — that's PDH; this is retailer-specific submission readiness only.

---

*Brief drafted June 4, 2026; revised same day with external review + the channel-comparison direction folded in. Build decisions resolved; one open item (whether the channel pattern headlines) deferred to build. Status left for you to set.*
