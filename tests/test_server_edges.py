"""Real local HTTP boundary checks; no external service or substitute guardian."""

import asyncio
import json

from hub import scenario
from hub.server import Session, serve


def test_http_validation_and_recovery():
    async def go():
        server, dash = await serve("127.0.0.1", 0, lambda: Session(scenario.ensure_night()))
        port = server.sockets[0].getsockname()[1]
        errors = []
        asyncio.get_running_loop().set_exception_handler(lambda loop, ctx: errors.append(ctx))

        async def raw(request):
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(request)
            await writer.drain()
            writer.write_eof()
            result = await asyncio.wait_for(reader.read(), 2)
            writer.close()
            await writer.wait_closed()
            return result

        async def request(method, path):
            response = await raw(f"{method} {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
            head, _, body = response.partition(b"\r\n\r\n")
            return int(head.split()[1]), body

        try:
            for value in ("banana", "NaN", "Infinity", "-Infinity"):
                old = dash.session.replay.speed
                code, body = await request("POST", f"/api/replay/speed?x={value}")
                assert code == 400 and "finite" in json.loads(body)["error"]
                assert dash.session.replay.speed == old
            for value, expected in (("0", .25), ("-2", .25), (".1", .25), ("10", 4), (".25", .25), ("4", 4), ("", 1)):
                assert (await request("POST", f"/api/replay/speed?x={value}"))[0] == 200
                assert dash.session.replay.speed == expected
            for method in ("PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
                assert await request(method, "/api/state") == (405, b"")
            for payload in (b"broken\r\n\r\n", b"GET / HTTP/1.1\r\n", b"POST /api/state HTTP/1.1\r\nContent-Length: banana\r\n\r\n", b"POST /api/state HTTP/1.1\r\nContent-Length: 5\r\n\r\nx"):
                assert await raw(payload) == b""
            assert (await request("GET", "/api/state"))[0] == 200
            assert not errors
        finally:
            dash.session.stop()
            server.close()
            await server.wait_closed()
    asyncio.run(go())
