# Configuration

Layered TOML, overlaid by environment variables, validated by Pydantic v2.

## Layers

```
config/
├── default/       base layer, applied in every environment
├── development/   local workstation
├── demo/          production topology, non-funded account
└── production/    live, funded trading
```

Within a layer, every `*.toml` file is merged in filename order. Layers are
then merged `default` first, environment layer second.

## Precedence

Highest wins:

1. Explicit keyword arguments to `AtlasSettings(...)`
2. Process environment variables — `ATLAS_` prefix, `__` nesting delimiter
3. `.env` file
4. `config/<ATLAS_ENV>/*.toml`
5. `config/default/*.toml`
6. Field defaults in `atlas.config.settings`

## Selecting a layer

`ATLAS_ENV` selects the environment layer and must be a **real process
environment variable** — it is read before the settings model is constructed,
so a value set only in `.env` will not select the layer. Every deployment path
in this repository (`docker-compose.yml`, `Dockerfile`, CI) exports it.

## Secrets

No file in this directory may contain a credential. Secrets are supplied
through the environment and typed as `SecretStr`, which keeps them out of
`repr`, logs and tracebacks. Use `PostgresSettings.safe_dsn` and
`RedisSettings.safe_url` in anything that gets logged.
