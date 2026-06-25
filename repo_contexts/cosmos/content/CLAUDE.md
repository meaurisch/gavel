# CleanArchitectureCosmosDB — repo context

A .NET 8 Web API built with Clean Architecture over Azure Cosmos DB. Solution:
`CleanArchitectureCosmosDB.sln`.

## Layout

- `src/CleanArchitectureCosmosDB.Core` — domain layer. Entities live in
  `Core.Entities` (e.g. `ToDoItem`, `Audit`). Entities guard their own invariants:
  `ToDoItem.IsCompleted` has a private setter flipped via `MarkComplete()`; `Audit`
  stamps `DateCreatedUTC = DateTime.UtcNow` in its constructor.
- `src/CleanArchitectureCosmosDB.Infrastructure` — persistence. `CosmosDbData`
  holds the repositories (`Repository/`), the generic `CosmosDbRepository<T>`, and
  container factory. Repositories implement the `Core.Interfaces` abstractions.
- `src/CleanArchitectureCosmosDB.WebAPI` — API layer. Request/response models and
  MediatR handlers live under `Models/<Aggregate>/` (one file per use case:
  `Create`, `Get`, `GetAll`, `Search`, `Update`, `Delete`, `GetAuditHistory`).
  Controllers are thin and dispatch through MediatR.

## Conventions

- **MediatR** for the command/query pattern — each use case is a `Command`/`Query`
  plus a nested `Handler`. Cross-cutting concerns go through pipeline behaviours.
- **Cosmos persistence** — documents are JSON; use `Newtonsoft.Json`
  (`[JsonProperty(...)]`) for property names. The Cosmos `id` is lower-case `id`
  and the system etag is `_etag`. A `type` discriminator distinguishes document
  kinds within a shared container.
- **Dependency injection** — services are registered via `Setup*` extension
  methods called from `Startup.ConfigureServices`.
- Tests: `tests/CleanArchitectureCosmosDB.UnitTests` (xUnit). Run with
  `dotnet test`. The SDK-style project globs `**/*.cs`, so new test files under the
  project directory are picked up automatically.

## Build / test

```
dotnet build CleanArchitectureCosmosDB.sln
dotnet test tests/CleanArchitectureCosmosDB.UnitTests/CleanArchitectureCosmosDB.UnitTests.csproj
```
