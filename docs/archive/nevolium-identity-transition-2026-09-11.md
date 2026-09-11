# Nevolium identity transition — 11 September 2026

## Scope and decision

The project adopted Nevolium as its only public and technical identity before the first user or
server deployment. This was a hard cut, not a compatibility period: a first installation must use
fresh configuration, databases, volumes, streams, workflows, identity realm and secret namespace.
The durable decision is [ADR-030](../decisions/ADR-030-nevolium-canonical-identity.md).

The transition changed 257 tracked files in one coherent commit and covered:

- product copy and Web/FastAPI titles;
- Python distributions, modules, imports and container entrypoints;
- npm workspace names, source symbols and Vite variables;
- Compose project, services, network references and operational paths;
- PostgreSQL database, roles and owned function names;
- Keycloak realm, client, audience, roles and development fixtures;
- OpenBao policy/path, NATS stream/subjects, Temporal queue/workflow IDs and object prefixes;
- telemetry keys, deterministic identity seeds and owned HTTP/event headers;
- smoke tests, qualification, CI, documentation, links and filenames.

Archived product labels and repository links were normalized in the current tree while immutable
SHA/run/job IDs, measurements, outcomes and limitations were retained. The exact pre-transition
tree and evidence remain at commit `8cc34c964d34c360fe9b42e50e2ac9daca678a75`; history was not
rewritten.

## Exact technical evidence

- Rename commit: `18dff4d7507fad285fae871e35e56c0567e42c3a`.
- Rename tree: `e39f8ebfe2a55a0869cafb6531a6fbabbf3a70f4`.
- Main synchronization and tested head: `d9478deada2c2c1781958abd87779b9a5e7c11f2`.
- Tested tree: `898306b233b7f16de6b28b19f78304498e0d7b2e`.
- Pull request: [#88](https://github.com/fredbuhr/nevolium/pull/88), still draft because D04/H5
  requires the private target campaign.

Local checks succeeded for the identity contract, zero tracked path/content residues, package
imports and metadata, both Python wheels, Python compilation, frozen pnpm installation, all
TypeScript checks, Web/Realtime builds, 12 Core contracts, 11 Worker contracts, memory wait,
reproducibility, JSON parsing and Bash syntax. Local Docker tests were intentionally delegated to
GitHub Actions because Docker is absent from the workspace; the local uv binary is 0.12.11 while
the repository correctly requires 0.12.13.

## GitHub Actions result

All ten pull-request workflows completed successfully on the tested head:

| Workflow | Run |
|---|---:|
| Autonomous research validation | `34646941667` |
| Baseline reproducibility validation | `34646941660` |
| Code quality validation | `34646941634` |
| D04 real engine qualification | `34646941592` |
| Document ingestion validation | `34646941768` |
| Foundation validation | `34646941578` |
| MCP tool registry validation | `34646941616` |
| Multi-user isolation validation | `34646941593` |
| News ownership validation | `34646941623` |
| UI workspace validation | `34646941618` |

The D04 workflow passed all five jobs: qualification runner contract, real local services, real
document/memory, recovery source and recovery target. This proves the renamed test and integration
topologies on the exact head; it does not complete the still-missing netcup private-target tests.

## Remaining external step

The source tree and active GitHub issue/PR metadata use Nevolium. The repository slug must still be
renamed in GitHub Settings, after which `origin` and the final active links must be verified. Closed
pull requests, old commits, Actions logs and the legacy experimental branch remain historical data;
they must not be rewritten merely for branding.
