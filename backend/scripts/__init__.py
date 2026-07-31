"""Backend utilities run by hand, not by the application.

A module here does composition-root work under the existing rule in
docs/architecture/dependency-rules.md: it may read configuration and construct
concrete adapters, which application and domain code must never do. It holds
wiring, not business rules -- those stay in the use case it calls. See
docs/development/folder-structure.md.
"""
