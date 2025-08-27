"""Backend package for the ClaimsCompanion application.

This package exposes the ASGI application via ``app.main.asgi_app``
which combines a FastAPI instance and a Socket.IO server into a
single ASGI app. Modules in this package implement the business
logic for authentication, claims management, chat messaging and a
simple AI assistant. The project is structured to mirror the Node.js
version of the application while taking advantage of Python's typing
and modern web framework features.
"""

from __future__ import annotations

# Expose the ASGI application at package level for convenience. This
# allows tools like `uvicorn app:asgi_app` to locate the app when run
# from within the ``backend_py`` directory. Importing from .main
# triggers module loading and router inclusion.
from .main import asgi_app  # noqa: F401