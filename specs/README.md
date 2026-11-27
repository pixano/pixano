# Pixano specifications

**Status:** Accepted
**Owner:** @jrabary
**Last agreed change:** 2026-11-22
**Covers:** `specs/`

This file says how the specs work. It follows the template it defines, and its own rules are numbered `SPEC-1`, `SPEC-2`, and so on.

## Purpose and concepts

The specs in this directory are the only source of truth on what Pixano is and how it is built. They bind everyone who changes the code, developers and AI agents alike.

AI agents write most of Pixano's code, and an agent follows what it reads. A design decision that is written nowhere, or in a place the agent does not read, gets broken sooner or later. The specs are the place where decisions are written, and the first thing to read.

Specs are for the people and the agents who build Pixano. They are read here, in the repository, and they are never published. The docs for the users of Pixano live in `docs-astro/`. They are a separate thing.

The words used in every spec:

- A **spec** is one file of this directory. It describes one part of Pixano: what it is, and the rules its code follows.
- A **rule** is one design decision, written so that it can be checked. It says what the code MUST or MUST NOT do, and why.
- A **rule ID** names a rule: the prefix of its spec, then a number, as in `JOB-12`.
- A **target rule** is a rule that the code does not follow yet. It says where Pixano goes. It carries the mark `(target)` after its ID, and a line `_Today:_` that says what the code does instead.
- An **open question** is something that is not decided yet.
- The **decision log** of a spec lists the changes that were agreed, one line each.
- A **spec PR** is a pull request that changes files in `specs/` and nothing else. A **code PR** is any other pull request.
- The **tech lead** is the code owner of `specs/`, named in [`.github/CODEOWNERS`](../.github/CODEOWNERS).

A spec has one of three statuses:

| Status       | Meaning                                                                                                                                                                                               |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Draft`      | The spec lists rules that are already true in the code, and target rules. It may be incomplete. Its rules bind like any other, a target rule as SPEC-14 says, and a missing rule is not a permission. |
| `Accepted`   | The tech lead and the developers agreed that the spec covers its part of Pixano.                                                                                                                      |
| `Superseded` | Another spec replaced this one, and the header names it. A superseded spec binds nobody. It stays for history.                                                                                        |

## Rules

**SPEC-1.** A design decision MUST be recorded in a spec.

_Why:_ a decision written in an issue, a chat, a PR description or a code comment is not found by the next person or the next agent. It binds nobody.

**SPEC-2.** When two sources disagree, the spec MUST be followed before `AGENTS.md`, and `AGENTS.md` before the existing code. Existing code that contradicts a spec is a bug. It MUST NOT be taken as an example.

_Why:_ an agent copies the code it finds. Without an order of precedence, one mistake becomes the pattern.

**SPEC-3.** Every spec MUST follow the [template](#template), with its five parts in the same order.

_Why:_ with one format, a reader finds the rules of any spec in the same place.

**SPEC-4.** Every rule MUST have an ID, MUST say MUST or MUST NOT, and MUST be followed by its reason.

_Why:_ an ID can be cited and checked. A reason lets a developer challenge the rule, and lets an agent apply it to a case the rule did not foresee.

**SPEC-5.** A rule ID MUST NOT be reused or renumbered. A rule that is removed keeps its line, marked as removed, with the date.

_Why:_ code, PRs and reviews cite rules by ID. A reused ID makes an old citation point to another rule.

**SPEC-6.** What is not decided MUST be listed under "Open questions". Code MUST NOT be built on an open question as if it were decided.

_Why:_ a guess that ships becomes a decision that nobody took.

**SPEC-7.** Before planning a change, its author MUST read the specs that cover the code paths the change touches. The [index](#index) says which. The plan and the PR description MUST cite, by ID, the rules that apply.

_Why:_ a rule that is not read is not followed. The cited IDs tell the reviewer which rules to check the change against.

**SPEC-8.** A spec MUST change only through a spec PR. A spec PR changes files in `specs/` and nothing else, carries the `spec-change` label, and is approved by the tech lead after discussion with the developers.

_Why:_ a change to a spec is a design decision. Next to code, it is reviewed as a detail of that code, or not reviewed at all.

**SPEC-9.** A spec PR MUST be merged before the code that relies on it. A code PR MUST NOT change `specs/`.

_Why:_ a spec edited to match code that already broke it is no longer a decision. It is a description of the code.

**SPEC-10.** When a task cannot be done without breaking a rule, its author MUST stop and report the conflict to the person who asked for the task. The author MUST NOT work around the rule, and MUST NOT edit the spec to fit the code.

_Why:_ the conflict is the information. Either the task is wrong or the rule is, and only the tech lead and the developers can say which.

**SPEC-11.** When a change needs a design decision that no spec states, its author MUST ask the tech lead. The author MUST NOT invent the rule. This holds when the spec is unclear, when it is silent, and when it is not written yet.

_Why:_ an invented rule looks like a decision, and it was never agreed.

**SPEC-12.** A change to a rule MUST be made in place, and MUST add one dated line to the decision log of its spec, with a link to the spec PR. An amendment MUST NOT be added to the header, or stacked next to the rule it changes.

_Why:_ a reader must find the current rule in one place, without replaying its history.

**SPEC-13.** Specs MUST be written in English, in plain words. They MUST NOT be published.

_Why:_ every developer and every agent reads English. A published design doc is read as a promise to users, and the specs are not one.

**SPEC-14.** A rule that the code does not follow yet MUST carry the mark `(target)` after its ID, and a line `_Today:_` that says what the code does instead. Until a spec PR removes the mark, the code that exists follows `_Today:_`: it is not a bug, and SPEC-10 does not stop a task on it. A change MUST NOT take the code further from a target rule.

_Why:_ a decision about where Pixano goes must be written where agents read it, before the code exists. Without the mark, it would make most of the code a bug on the day it is merged.

## Index

Find the code paths you are about to change in the last column, and read the spec of that row.

| Part of Pixano          | Prefix | Spec                                                                                                                                                                                          | Code paths                                                                                                                                                                                                                      |
| ----------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| How the specs work      | `SPEC` | This file. Accepted.                                                                                                                                                                          | `specs/`                                                                                                                                                                                                                        |
| Overall architecture    | `ARCH` | [`architecture.md`](./architecture.md). Draft.                                                                                                                                                | The components, how they reach each other and what they may import: `docker-compose*.yml`, `.env.example`, `dockerfiles/`, `hatch_build.py`, `src/pixano/cli/`, `src/pixano/utils/`, and the list of packages under `packages/` |
| Data model and database | `DATA` | [`data-model.md`](./data-model.md). Draft.                                                                                                                                                    | `src/pixano/schemas/`, `src/pixano/features/`, `src/pixano/datasets/` except `io/`                                                                                                                                              |
| REST API                | `API`  | [`rest-api.md`](./rest-api.md). Draft.                                                                                                                                                        | `src/pixano/api/`, except `src/pixano/api/jobs/`, `src/pixano/api/routers/jobs.py` (`JOB`), `src/pixano/api/routers/data_io.py` (`IO`) and `src/pixano/api/routers/inference.py` (`INF`)                                        |
| Worker and jobs         | `JOB`  | `jobs.md`, not moved yet. Until then: [`docs/specs/backend-processing.md`](../docs/specs/backend-processing.md) and [`docs/specs/writing-a-job-kind.md`](../docs/specs/writing-a-job-kind.md) | `packages/pixano-worker/`, `src/pixano/api/jobs/`, `src/pixano/api/routers/jobs.py`, `src/pixano/statistics/`                                                                                                                   |
| Import and export       | `IO`   | `import-export.md`, not moved yet. Until then: [`docs/specs/data-import-export.md`](../docs/specs/data-import-export.md)                                                                      | `src/pixano/datasets/io/`, `src/pixano/cli/data.py`, `src/pixano/api/routers/data_io.py`                                                                                                                                        |
| Legacy app              | `UI`   | `legacy-app.md`, not written yet                                                                                                                                                              | `ui/apps/pixano/`                                                                                                                                                                                                               |
| Inference               | `INF`  | `inference.md`, not written yet                                                                                                                                                               | `src/pixano/inference/`, `src/pixano/api/routers/inference.py`, `docker/inference/`                                                                                                                                             |

A path that no row lists has no spec yet. Neither has a row whose spec is not written yet. SPEC-11 applies to both.

The new UI, `ui/apps/web`, gets no spec here. It is leaving the repository, and its docs go with it.

### During the move

Three specs were written before this directory existed. They are still in `docs/specs/`, and the index names them. Until each one moves here:

- it keeps the weight it has today;
- it is still edited the way it was, in code PRs. SPEC-8 and SPEC-9 bind a spec from the day it is in `specs/`.

No new spec is added under `docs/`. This section goes away when `docs/` does.

## Template

Copy this block to start a spec. Add its row to the [index](#index) in the same spec PR.

```markdown
# <The part of Pixano this spec covers>

**Status:** Draft
**Owner:** @<GitHub handle>
**Last agreed change:** YYYY-MM-DD
**Covers:** `<code path>`, `<code path>`

## Purpose and concepts

What this part of Pixano is and what it is for, in plain words.
Then the words a reader needs, each one defined once.

## Rules

**<PREFIX>-1.** <This part> MUST <do this>.

_Why:_ <the reason, in one or two sentences>.

**<PREFIX>-2.** <This part> MUST NOT <do that>.

_Why:_ <the reason>.

**<PREFIX>-3.** Removed on YYYY-MM-DD ([#<number>](https://github.com/pixano/pixano/pull/<number>)).

**<PREFIX>-4 (target).** <This part> MUST <do this, once the code is there>.

_Why:_ <the reason>.

_Today:_ <what the code does instead, and the file or the spec that says so>.

## Open questions

- <What is not decided yet, and what waits for it.>

## Decision log

- YYYY-MM-DD: <what was agreed> ([#<number>](https://github.com/pixano/pixano/pull/<number>)).
```

How to fill it:

- **Status** is `Draft`, `Accepted` or `Superseded by [<spec>](./<spec>.md)`.
- **Owner** is the person to ask about this spec. The tech lead approves every change, whoever the owner is.
- **Last agreed change** is the date of the last line of the decision log.
- **Covers** lists the same code paths as the row of the spec in the index.
- **One rule, one decision.** Keep a rule short. A rule states the decision, not how it was reached.
- **History and measurements** stay out, unless they are the reason for a rule.
- **A new rule** takes the next number that was never used.
- **A target rule** (SPEC-14) carries the mark `(target)` and a `_Today:_` line. When the code follows the rule, a spec PR removes the mark and the line. The ID stays.
- **Other sections** (a diagram, a reference table, an example) can follow the rules. The five parts above are never dropped.
- **A Draft** lists what is already true in the code, and target rules. What is not decided is an open question.

## How a spec changes

1. **Open a spec PR.** It changes files in `specs/` and nothing else. Give it the `spec-change` label. In its description, say what changes, why, and which code will rely on it.
2. **Discuss it with the developers**, in the PR.
3. **The tech lead approves it.**
4. **Merge it.**
5. **Then write the code**, in a code PR that cites the rules it follows.

A new spec follows the same steps.

Two things enforce them:

- The `Specs` check fails a pull request that changes `specs/` together with anything else, or without the `spec-change` label.
- [`.github/CODEOWNERS`](../.github/CODEOWNERS) asks for the tech lead's review on every change under `specs/`.

## Open questions

- Does the repository need a spec for the conventions that span every part (coding style, naming, tests)? Today they are in `AGENTS.md`.
- When the job kind contract moves here, does it stay a spec of its own, or does it become a part of `jobs.md`?
- Where does history go (reviews, audits, plans that were carried out)? Either the git history is enough, or the repository keeps an archive directory.

## Decision log

- 2026-11-18: first version, with the rules about specs, the template and the index ([#862](https://github.com/pixano/pixano/pull/862)).
- 2026-11-22: a rule that the code does not follow yet is a target rule, marked `(target)`, with a `_Today:_` line (SPEC-14) ([#866](https://github.com/pixano/pixano/pull/866)).
