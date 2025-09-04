"""Socket.IO server definition.

This module instantiates the Socket.IO server used for real‑time
communication. The server is configured with permissive CORS for
local development. In production you should restrict origins. The
server emits chat messages to rooms keyed by claim ID. Clients join
these rooms via the ``join_claim`` event.
"""

from __future__ import annotations

import socketio

# Create the Socket.IO server. We choose async_mode="asgi" because the
# application will run in an ASGI environment via Uvicorn. The
# ``cors_allowed_origins`` list should be restricted to your frontend
# domain in production.
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_timeout=25,
    ping_interval=20,
)


@sio.event
async def connect(sid, environ, auth):
    """Called when a client connects to the socket server."""
    # We could authenticate here using the auth payload if desired.
    print(f"Socket connected: {sid}")


@sio.event
async def disconnect(sid):
    """Called when a client disconnects from the socket server."""
    print(f"Socket disconnected: {sid}")


@sio.event
async def join_claim(sid, claim_id: str):
    """Join a room corresponding to a claim.

    Rooms are named using the claim ID. This allows messages to be
    targeted to only those clients viewing the same claim.
    """
    room = str(claim_id)
    await sio.enter_room(sid, room)
    await sio.emit("joined", {"room": room}, room=room)