import asyncio
import sys

import uvicorn


def test_server_loop_uses_windows_selector_without_suppressing_errors():
    config = uvicorn.Config(lambda: None, loop="backend.services.event_loop:create_server_loop")
    loop = config.get_loop_factory()()
    try:
        if sys.platform == "win32":
            assert isinstance(loop, asyncio.SelectorEventLoop)
        assert loop.get_exception_handler() is None
    finally:
        loop.close()
        asyncio.set_event_loop(None)
