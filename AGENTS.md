# Commerce Data Platform — engineering charter

This file is the durable project charter. Code wins when memory disagrees.
Update it when the architecture actually changes.

The product is a link between last night's SEC filings and a GLEIF
company record, or a written refusal. The resale workspace still in this
tree is the previous domain. Do not extend it.

## What stays

Reuse the ingest machinery. Do not write a second loader.

| Keep | Where | Job in the rebuild |
|------|--------|--------------------|
| Hash skip, one transaction, quarantine, failed-run audit, orphan recovery | `src/cdp_cli/ingest/` | SEC and GLEIF producers land here |
| `read = loaded + rejected` | `src/cdp_cli/observability.py` | `/health` goes red when this fails, or when the company-file hash does not match disk |
| Audit tables | `core.ingest_runs`, `core.rejected_records`, `core.record_lineage` | Same contract. New sources, not a new audit schema |
| Fail-closed rule | `src/cdp_cli/llm/grounding.py` | A model may not fill a hole or add a fact. The librarian loop does not stay |

Postgres is the only database. Nothing is paid. A laptop is the production
environment.

## What does not stay

Resale entities, the context bundle as the thesis, the Business Librarian,
MCP, sandbox actions, synthetic demo worlds, and a model on the path that
decides a link.

Do not add a second business, a fuzzy matcher, sanctions, filing PDFs, or
a hosted demo to get there.

## Invariants

1. Producers do not write canonical rows. Raw is immutable. Canonical is
   replaceable from raw.
2. A rerun with the same hash does nothing.
3. Rejects are quarantined with a reason. They are never silent.
4. One transaction per ingest run. A mid-run exception rolls back upserts
   and still leaves a durable `failed` audit row.
5. The link is deterministic. One row per CIK, replaced on rerun, not
   stacked. Status is `linked` or `refused`. Every row has an evidence
   type and a short reason.
6. Rules fire in order and stop: `printed_on_record`,
   `registration_authority`, `exact_name`, `former_name`, else `refused`.
   Ticker never creates a link by itself. No similarity score.
7. Confirm GLEIF registration-authority column names from the file header
   before depending on them.
8. Apple (CIK `0000320193`) is the honesty check. The submissions record
   has former names and `lei` null. Do not invent a link.
9. The answer cites the accession and the company record, or it abstains.
   A template is enough. A model may not add facts or pick a parent.
10. Public docs explain the software. They do not describe careers,
    interviews, or portfolios.

## Target shape

```
SEC daily index + submissions JSON     GLEIF lei2 / rr / repex
        |                                      |
        v                                      v
   raw, hashed                            raw file, hashed
        |                                      |
        v                                      v
   sec.filers / names / filings           lei.entities / names /
                                          relationships / exceptions
        |                                      |
        +---------------- link ----------------+
                         |
              link.decisions: linked or refused
                         |
           /health  /filers/{cik}  /refusals
                         |
              cited answer, or abstain
```

SEC pull: daily index, forms 10-K, 10-Q, and 8-K only, submissions JSON
for those CIKs, no filing document. Declare a user agent. Stay under 10
requests a second.

GLEIF pull: `lei2`, `rr`, `repex` from the golden-copy latest CSV URLs,
only if the hash changed. Do not put the zip in git or inside a row.

## Build order

1. Postgres up. One filer, Apple, raw JSON visible, `lei` null visible.
2. Daily index in. Filings table filled. Rerun is a no-op.
3. Company file in. Entities load. Hash recorded.
4. Five rules, with tests. One forced LEI link. One exact-name link.
   One two-candidate refusal. Apple must not get a sloppy link.
5. Health page and filer page.
6. Ownership files, and the cited answer. Only then.

Do not start with the UI, and do not start with a model.

## Verification

Local tests passing is not remote CI passing.

After changing workflows, connection strings, or developer commands:
push, locate the GitHub Actions run for that HEAD, and require GREEN.
Do not report CI success from local execution alone.

GitHub Actions log redaction prints the disposable Postgres password
as `***`. Never copy that masked form into YAML, Makefile, compose
files, or executable Python defaults. The local/CI password is the
literal `cdp`.

## Licensing

The public GitHub copy carries an MIT license (copyright 2026 Seb).
Do not silently replace it.
