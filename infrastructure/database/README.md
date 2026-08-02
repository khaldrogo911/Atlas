# Database Infrastructure

## Layout

```
infrastructure/database/
├── init/     first-start SQL, mounted into the postgres container
└── README.md
```

## Initialisation

`init/*.sql` is mounted read-only at `/docker-entrypoint-initdb.d` and executed
in filename order by the PostgreSQL image — **only when the data volume is
empty**. Editing a file in `init/` has no effect on a database that already
exists.

To re-run initialisation locally:

```bash
docker compose down -v     # destroys the volume and all local data
docker compose up -d postgres
```

## Conventions

- **All timestamps are `timestamptz`, stored in UTC.** Naive timestamps in a
  trading system are a correctness bug waiting on the next DST transition.
- **One schema per bounded context** (`trading`, `risk`, `audit`, `analytics`)
  so that grants can be expressed per area.
- **Money is `numeric`, never floating point.**
- **The `audit` schema is append-only.** No `UPDATE` or `DELETE` grants are
  issued to application roles.

## Migrations

Not yet introduced — there are no tables to migrate. A migration tool is
adopted alongside the first package that owns a schema, and that adoption gets
its own ADR. Until then, `init/` is the whole story, and it is honest about
only running once.
