# Architecture

```mermaid
flowchart LR
    Browser[Browser UI] -->|HTTP-only session cookie| API[FastAPI API]
    API -->|validated rows| DB[(PostgreSQL / SQLite)]
    API -->|large upload| Worker[Background analysis worker]
    API -->|small upload| Pipeline[Detection pipeline]
    Worker --> Pipeline
    Pipeline --> Normalize[Alias normalization + blocked fuzzy grouping]
    Normalize --> Cycle[Interval coverage + cycle detection]
    Cycle --> Score[Amount drift + confidence threshold]
    Score --> DB
    DB --> API
```

Large uploads leave the request lifecycle through FastAPI background dispatch. For horizontal multi-instance production, replace that adapter with a durable queue such as Celery/Redis without changing `run_analysis`.
