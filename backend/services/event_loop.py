"""Socket-only HTTP server loop without Windows Proactor close callbacks."""

import asyncio
import sys


def create_server_loop() -> asyncio.AbstractEventLoop:
    # The server does not use asyncio subprocesses or pipes. Its 64-connection
    # limit stays below Windows SelectSelector's 512-socket capacity.
    loop = asyncio.SelectorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop
