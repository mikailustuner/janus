# 0001. No language model as a product reader

Status: accepted (owner decision), 2026-11.

## Context

Janus reads drug labels, trial records and articles, and explains findings to people. Language models can extract
values and write explanations, but their errors are hard to bound, they change between versions, and an
explanation that sounds certain can mislead a patient.

## Decision

Inside the product, documents are read by deterministic, tested rules, and every sentence a person sees comes
from a fixed, reviewed template filled with checked values. Automated review passes may be used to _evaluate_
those readers (for example the two independent passes of a precision measurement); they never decide what the
product shows.

## Consequences

- Readers abstain more often (lower coverage, measured and published), but each kept value is traceable to a rule
  and a source quote.
- Wording says "automated" for anything automated; nothing implies a person checked it until an expert has.
