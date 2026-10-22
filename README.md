# Commerce Data Platform

A local link between last night's SEC filings and a GLEIF company record, or a written reason there isn't one.

Postgres is the only database. Nothing is paid. The resale app is not part of this.

The new pipeline is not in the tree yet. The tree still has the previous resale workspace. The part worth keeping is the load, not the domain.

## What stays

The ingest runner already does the part that has to be trustworthy:

- a file hash, and a rerun that does nothing when the hash matches
- one transaction per run
- rejects quarantined with a reason, never dropped
- `read = loaded + rejected`, or the health check is red
- a failed run rolls back the upserts and still leaves an audit row
- a model is not allowed to fill a hole in the record

That lives in `src/cdp_cli/ingest/` and `src/cdp_cli/observability.py`, against `core.ingest_runs`, `core.rejected_records`, and `core.record_lineage`. The new producers write through that. They do not get a second loader.

## What does not stay

Items, listings, channels, the Business Librarian as the product, the context bundle as the thesis, MCP, sandbox actions, and the synthetic demo world. The link rules are new. A model is not in the path that decides a link.

## What done looks like

One command pulls the SEC daily index, fetches the new filer records, and loads the latest company file if the hash changed. A second command applies the link rules. A page then shows three things.

**Health.** Last index date, last company-file hash, rows read, rows quarantined, links by evidence type, refusals by reason. If the company-file hash does not match the file on disk, the page is red and the links are not to be trusted. The current trust check already knows `read = loaded + rejected`. It does not yet know SEC or GLEIF.

**A filer.** CIK, name, former names, ticker, the `lei` field as the SEC published it, and either a company record or a refusal. Apple is the honesty check. On 2026-10-22 the submissions record for CIK `0000320193` was Apple Inc., with former names, and `lei` null. The page must not invent a link.

**An answer, only after that.** Who is this filer, and who owns them. It cites the accession and the company record, or it abstains. A template is enough. A model may not add facts. The old grounding code already refuses to override an insufficient bundle. That rule stays. The librarian loop does not.

## Shape

```
last night's SEC index          company file (daily is enough)
        |                              |
        v                              v
   raw payloads, hashed          raw file, hashed
        |                              |
        v                              v
   filers, names, filings        entities, names, ownership
        |                              |
        +------------ link ------------+
                     |
         linked, with a reason
         or refused, with a reason
                     |
            health page + one filer page
                     |
            cited answer, or abstain
```

The link step is the product. The pulls are plumbing. The model is not in the path that decides a link.

Four layers. Each one can fail without corrupting the one below it.

**Pull.** Two producers. Neither writes canonical rows. SEC: daily index, 10-K / 10-Q / 8-K only, submissions JSON for those CIKs, no filing document. Declare a user agent. Stay under 10 requests a second. GLEIF: `lei2`, `rr`, and `repex` from the golden-copy latest CSV URLs, and only if the hash changed.

**Raw.** Immutable. A rerun with the same hash does nothing. `core.ingest_runs` already records source, status, rows read, loaded, rejected, and the file hash. Raw SEC JSON and the GLEIF file path-plus-hash are new tables. The zip does not go in git, and it does not go inside a row.

**Canonical.** Parsed, typed, replaceable from raw. `sec.filers`, `sec.filer_names`, `sec.filings`, `lei.entities`, `lei.names`, `lei.relationships`, `lei.exceptions`. Column names for registration-authority fields get locked after reading the file header, not before.

**Link.** Deterministic. One row per CIK. `linked` or `refused`. Re-running replaces the decision. It does not stack duplicates.

Rules, in order, stop at the first that fires:

1. The SEC `lei` field is present, valid, and exists in the company file. Evidence: `printed_on_record`.
2. The company record names EDGAR as the registration authority and the registered id is this CIK. Confirm that column in the file before depending on it. Evidence: `registration_authority`.
3. Normalized legal name matches exactly one issued entity. Evidence: `exact_name`.
4. A former name matches exactly one issued entity. Evidence: `former_name`.
5. Anything else is a refusal. Evidence: `refused`, with the reason.

Ticker never creates a link by itself. Normalization is case, punctuation, and a short list of suffixes, written down and tested. No similarity score.

## Pages

Three routes. Not built yet.

`/health` is the pipeline. `/filers/{cik}` is the object: SEC identity, company record, decision in the middle. Refusals are first-class. `/refusals` is the work list.

The answer sits on the filer page. If the decision is `linked` and a relationship or an exception exists, say who owns them and cite those rows. If the decision is `refused`, abstain. If the parent was not reported, say the exception. Do not let a model pick a parent.

## Out of v1

Sanctions, a chatbot, filing PDFs, a fuzzy matcher, every filer since 1994, a hosted demo, and the resale workspace.

A laptop is the production environment.

## Build order

1. Postgres up. One filer, Apple, raw JSON visible, `lei` null visible. No company file yet.
2. Daily index in, limited to those three forms, submissions fetched, filings table filled. Rerun is a no-op.
3. Company file in. Entities load. Hash recorded.
4. The five rules, with tests. One forced link from a record that actually has an LEI. One exact-name link. One refusal with two candidates. Apple must not get a sloppy link.
5. Health page and filer page.
6. Ownership files, and the cited answer. Only then.

The first thing a stranger should understand is the refusal, not the stack.

## What you can run today

The commands below still start the previous resale workspace. That is not the product.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,api,mcp]"
make doctor && make up && make seed && make demo
```

LICENSE is MIT.
