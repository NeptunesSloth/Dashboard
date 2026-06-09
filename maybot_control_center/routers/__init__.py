"""Domain API routers, split out of the app.py monolith.

Each module exposes ``router`` (a FastAPI ``APIRouter``) that ``app.py`` mounts
via ``include_router``. Handlers depend only on ``..deps`` and feature modules,
never on the FastAPI app object, so there is no import cycle.
"""
