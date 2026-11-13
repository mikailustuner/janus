# 0003. Backups pulled by a separate machine

Status: accepted (owner decision on the location), 2026-11.

## Context

The public server holds the database and the built data. A backup the server can write to can also be deleted by
whoever controls the server; paid backup products are not an option.

## Decision

A separate machine pulls a daily database dump and a weekly data snapshot over the private network with its own
key. On the server that key is bound to one forced command (`deploy/backup-serve.sh`) that answers three read-only
requests and refuses everything else. Pull failures and overdue backups raise alerts.

## Consequences

- The server holds no credential for the backup machine.
- A missed run (machine off) catches up at its next start; an alert fires when the machine has not answered for
  36 hours.
- Restores are tested (`deploy/backup-restore-check.sh`).
