# 0004. Synthetic test fixtures, one contract test for recorded data

Status: accepted, 2026-11.

## Context

The web app's demo mode reads recorded API answers. Tests that asserted on those recordings broke whenever the
data was rebuilt (once 30 at a time), or silently skipped when a recording no longer held a needed case.

## Decision

Behaviour tests use small synthetic fixtures built through the production types and decoders
(`apps/web/src/test/fixtures/`), each covering the branches its tests need. Every recorded file has exactly one
contract test (it decodes and holds the minimum the demo needs). No test skips because of data content.

## Consequences

- A data rebuild changes no test outcome unless the contract itself breaks.
- Demo-mode end-to-end tests check structure only; behaviour is covered with stubbed answers.
