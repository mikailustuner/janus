# Janus

> Janus provides information, not medical advice. Research prototype — not a medical
> device (not FDA-cleared, not CE-marked).

Janus reads the medicines in a person's home, from the code on the box, the pharmacy
label or the medicine's name, in Türkiye, the European Union and the United States. It
looks for **prescribing-cascade patterns**: cases where a side effect of one medicine may
have been mistaken for a new condition and treated with another medicine. Each pattern
is linked to its published source and turned into a short note the person can take to
their doctor, in the doctor's language (English, Turkish, German, French or Spanish).

Janus never tells anyone to start, stop or change a medicine. Its findings are patterns
from the literature that may be worth discussing with a doctor.

Built for the Kiroween 2026 hackathon. The project is at an early stage: this
repository currently contains the project skeleton only.

## Repository layout

| Path         | Contents                                                                  |
| ------------ | ------------------------------------------------------------------------- |
| `apps/web/`  | Next.js web app (PWA), five languages                                     |
| `apps/api/`  | FastAPI service (Python 3.12)                                             |
| `pipelines/` | Data ETL jobs, one per source                                             |
| `data/`      | Small, redistributable data files                                         |
| `docs/`      | Documentation; `docs/kiro-usage.md` is the development log                |
| `.kiro/`     | Kiro steering, specs and hooks used to build the project                  |

## Local development

Requirements: Docker with Compose, or Node 24 + pnpm 12 and
[uv](https://docs.astral.sh/uv/).

With Docker:

```sh
cp .env.example .env    # set POSTGRES_PASSWORD
docker compose up --build
```

- Web: http://localhost:3100
- API health check: http://localhost:8000/health

Without Docker:

```sh
pnpm install
pnpm dev                          # web on http://localhost:3000

cd apps/api
uv sync
uv run uvicorn janus.main:app --reload
```

Checks (the same ones CI runs):

```sh
pnpm lint && pnpm typecheck && pnpm test
cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```

## Privacy

Images never leave the device; barcode decoding and OCR run in the browser. Medication
lists stay in the browser by default, and the API does not store them.

## License

Code: [Apache License 2.0](LICENSE). Copyright 2026 Mikail Üstüner.

Third-party data sources keep their own licenses and terms; see [NOTICE](NOTICE).
