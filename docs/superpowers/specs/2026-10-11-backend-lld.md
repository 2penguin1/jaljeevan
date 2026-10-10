# Backend low-level design (v2, approved 2026-10-11)

Applies to all backend code. Companion to `2026-10-10-mvp-design.md`.

## Dependency rule
`api/`, `cli/` and `lambdas/` (entry points, thin) → `services/` (use cases) → `domain/` (pure rules), `repositories/` (SQL only) and `integrations/` (via `integrations/ports.py` Protocols) → `models/` (ORM).

- **`domain/` imports nothing** from FastAPI, SQLAlchemy or boto3.
- **Services never import FastAPI**, so the same classes run from the API, the CLI and Lambda.

## Folders
```
app/core/          config.py, database.py (engine, session_scope), container.py, exceptions.py, logging.py
app/domain/        entities.py (immutable dataclasses), text.py, prefilter.py, taxonomy.py, evidence.py,
                   classification.py (LLM output schemas + prompt builder), scoring.py, hazards.py,
                   lifecycle.py, events.py, states.py
app/models/        ORM tables: geo.py, intel.py, crm.py, community.py (re-exported in __init__)
app/repositories/  base.py (BaseRepository[Model]) + one class per aggregate
app/integrations/  ports.py, dates.py, sources/{base,gdelt,rss,social}.py, apify.py, bedrock.py,
                   location.py, weather.py, archive.py, sns.py
app/services/      ingestion_service.py, classification_service.py, geocoding/, zone_detection_service.py,
                   pipeline.py (IntelligencePipeline + stages), event_bus.py
app/schemas/       API DTOs
app/api/           v1/endpoints/*, dependencies.py, error_handlers.py
app/cli/           seed_geo.py, run_pipeline.py
```

## Cross-cutting rules
1. **Object lifetimes.**
   - App-scoped singletons live on `Container`: settings, engine, `Taxonomy`, LLM client, HTTP client, fetcher registry, archive, notifier, domain policies.
   - Job-scoped objects are created by container factories that take a `Session`: repositories and services. Never share a session across requests or jobs.
2. **Transactions.**
   - Repositories `flush()`; they never `commit()`.
   - The entry point owns the transaction via `session_scope()`: commit on success, roll back on error. In FastAPI, the session dependency does the same.
3. **Errors.** `core/exceptions.py` defines `AppError` and its subclasses:

   | Exception | HTTP status |
   |---|---|
   | `NotFoundError` | 404 |
   | `ConflictError` | 409 |
   | `DomainValidationError` | 422 |
   | `ExternalServiceError(retryable)` | 502 |

   They're mapped to HTTP once, in `api/error_handlers.py`. The pipeline isolates `ExternalServiceError` per source.
4. **Idempotency and concurrency.**
   - Classification is keyed by `(signal_id, classifier_version)`.
   - Zone detection takes `pg_try_advisory_xact_lock` per hazard.
   - Bids (P4) use optimistic locking on `version`.
5. **Events (Observer).** Services raise domain events such as `ZoneEscalated` and `SignalClassified`. The `EventBus` delivers them **after commit** to subscribers (SNS alert, in-app notification, live-feed NOTIFY).

## Patterns
| Pattern | Where |
|---|---|
| Ports & Adapters | whole app |
| DI + Composition Root | `core/container.py` |
| Repository | `repositories/` |
| Strategy + Registry | `SourceFetcher`s, `HazardPolicy` |
| Template Method | `BaseSourceFetcher`, `PipelineStage` |
| Adapter | Bedrock, Amazon Location, SNS, Open-Meteo |
| Chain of Responsibility | geocoding resolvers |
| State machine | `ZoneStateMachine` (later bids) |
| Observer | `EventBus` |
| Factory | archive, LLM |
| Value Object | `domain/entities.py` |

Interfaces are `typing.Protocol`. Abstract base classes are used only where they carry shared code. No interface without a second implementation or a test fake.

## Testing pyramid
1. **Domain unit tests:** no database.
2. **Repository tests:** real PostGIS.
3. **Service tests:** real repositories, fake LLM and fetchers.
4. **API tests:** `TestClient` with dependency overrides.
5. **Eval:** the gold set.
