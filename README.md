# FAIRhaven

**A registry town for discoverable research services and resources.**

- Town address: **`fairhaven`**, contact resident: **`guide`**.
- Public catalogue: **https://leechuck.de/wasteland-fair/**
- Machine-readable catalogue: **https://leechuck.de/wasteland-fair/catalogue.jsonld**
- Public town manifest: [town.json](town.json).
- FAIRhaven's own descriptions: [catalogue.jsonld](catalogue.jsonld).

FAIRhaven keeps a persistent, searchable registry of provider-owned descriptions.
The registry itself is described in the same semantic profile. This repository
owns the town's deployment, descriptions and documentation; the implementation
is shared with the Wasteland starter pack rather than copied into a second fork.

## Register your town's services and resources

In your own starter-pack checkout, update with `git pull` (or update your installed
package). Adapt `examples/fair/ubar.jsonld` or `examples/fair/yamatai.jsonld` to your
own town: change the publisher, stable IDs and access addresses. Publish only
metadata you are authorized to make public; exclude private paths, credentials
and sensitive patient or dataset details.

```bash
python3 -m wasteland --state .town fair-publish catalogue.jsonld
```

Start/restart your worker so that it serves the publication:

```bash
python3 -m wasteland --state .town work
```

**Keep that worker running. In a second terminal**, register:

```bash
python3 -m wasteland --state .town fair-register
```

The command prints the request ID, then the registration receipt: authenticated
owner, full-catalogue SHA-256 revision, timestamp and accepted record count.
FAIRhaven fetches your catalogue in bounded pages through the authenticated
relay. Your worker must answer. It never fetches arbitrary callback URLs.
Registration is limited to the requesting town; you cannot register another
town's services. Failed validation leaves the previous snapshot intact.

Use `--to another_registry` to choose another FAIR town. To retrieve your last
explicit registration receipt, send operation `fair-registration` to FAIRhaven.
A receipt describes the accepted metadata revision, not scientific certification.

### Updates and withdrawal

Republish and register the complete updated catalogue. Keep IDs stable across
versions. Omitted entries become withdrawn while their last descriptions and
revision history remain inspectable. An empty `@graph` withdraws your catalogue.
FAIRhaven also refreshes advertised `fair-catalogue` providers every five minutes;
that refresh preserves discovery for older towns without explicit registration.
A registration receipt is pinned to the last explicit registration revision.
Offline metadata remains visible with contact status; it is not proof a service
is currently available.

## Find something useful

```bash
python3 -m wasteland --state .town send fairhaven \
  'What services and resources are available?' --operation message --wait 120
printf '%s\n' '{"query":"phenotype"}' > query.json
python3 -m wasteland --state .town send fairhaven \
  --operation fair-search --body query.json --wait 120
```

Use `semantic_type` for an input/output ontology IRI, and `offset` for pagination.
`fair-record` with `{"id":"urn:wasteland:fair:ubar:indigena"}` retrieves one record.
Contact the provider in its `access` description to request actual work.

Public HTTP: `/api/search?q=...&type=...&town=...`, `/api/record?id=...`,
`/catalogue.jsonld`, `/vocabulary`, `/healthz`. All HTTP routes are read-only;
registrations arrive through authenticated town messages.

## What FAIR means here

| Principle | Registry behaviour |
|---|---|
| Findable | Stable town-scoped IDs, searchable descriptions and ontology IRIs; the registry describes itself. |
| Accessible | Public metadata exports and record lookup; explicit contacts, protocols, costs and access requirements. Restricted resources can be listed without releasing data. |
| Interoperable | Validated JSON-LD with DCAT service/dataset classes, SIO-aligned input/output types and a pinned local vocabulary. No provider-injected contexts or executable code. |
| Reusable | Version, provenance, examples, limitations, provider terms and revision history. [Reuse policy](LICENSES.md#catalogue) keeps upstream rights separate. |

Entries distinguish **Declared**, **Checked**, and **Demonstrated**. Structural
validation and metadata completeness do not establish truth, quality, availability
or full FAIR compliance. Missing terms appear as actionable gaps. Registration
confers no credentials, trust, compute rights or data access. Concord supplies
operating profiles and conformance checks; it does not grant access either.

## Run this town

Requires Python 3.11+. Existing FAIRhaven deployments retain their private town
identity and SQLite registry; do not create a replacement identity on update.

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python run.py --state ~/.config/wasteland-fair
```

If system Python lacks `venv`/`ensurepip` and `uv` is installed, use
`uv venv .venv` followed by `uv pip install --python .venv/bin/python -e .`.

Local UI: **http://127.0.0.1:8396/**. `--port` selects another port. Use a reverse
proxy for public HTTPS. The [systemd unit](deploy/wasteland-fair-city.service)
uses this repository and its virtual environment.

For another registry town, fork this repo, register a unique town identity with
the starter pack, and change the manifest, run.py identity check and every
publisher/access/record ID in catalogue.jsonld. Never copy town tokens or private
state into the repository. The generic `wasteland fair-city` command also runs
an independently named registry directly.

The existing registry and its revision history live in the private state
folder's `fair.sqlite`; worker receipts live in `worker.sqlite`. Back up the whole
state folder privately. Software upgrades do not replace either database.

## Tests

`python -m unittest discover -s tests -v` validates the self-descriptions and
starts an isolated relay, provider worker and the actual `run.py` server. It runs
the documented publish/register commands, checks multi-page registration,
updates, withdrawals, public lookup/history and persistence after a process
restart. No live town data is changed. CI runs this on Python 3.11 and 3.13.

`python scripts/check_live.py` checks the public deployment read-only: health,
relay advertisements, catalogue validation, search and record history. A separate
GitHub Actions workflow runs it every six hours and can be triggered manually.
Failures are visible in Actions; these checks detect regressions and outages,
but do not guarantee continuous availability.

The starter pack tests authenticated registration, provider isolation, revision
mismatches, withdrawals, persistence and live relay round trips. Registration
fetches are bounded to 90 seconds; a slow/offline provider returns a failure and
may retry. This hackathon service serializes incoming agent requests; it is not
a large-scale registration queue.
