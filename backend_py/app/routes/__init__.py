"""Expose API routers for FastAPI.

This package contains individual modules implementing the
authentication, claims and chat endpoints for the ClaimsCompanion
application. Each module defines a ``router`` object which is
registered in ``app.main`` under a common path prefix.
"""

from . import auth  # noqa: F401
from . import claims  # noqa: F401
from . import chat  # noqa: F401