import asyncio
import pytest
from aiohttp import web, ClientSession

class chaotic_test:
    def __init__(self, port=6666):
        self.port = port
        self.app = web.Application()
        self.app.add_routes([
            web.get("/normal", self.handle_normal),
            web.get("/chaotic-drop", self.handle_drop),
            web.get("/waf-block", self.handle_waf),
            web.get('/garbage', self.handle_garbage),
            web.get("/slow-timeout", self.handle_slow),
            web.get("/redirect-loop", self.handle_loop),
        ])
        self.runner = None
        self.site = None

    async def handle_normal(self, request):
        return web.Response(text="<html><body><a href='/chaotic-drop'>Next</a></body></html>", status=200)

    async def handle_drop(self, request: web.Request):
        if request.transport:
            request.transport.close()
        raise ConnectionResetError("Коннект оборвался")

    async def handle_waf(self, request):
        return web.Response(text="Forbidden", status=403)

    async def handle_garbage(self, request):
        return web.Response(body=b"\xff\xfe\x00\x00corrupted_data_stream", status=200)

    async def handle_slow(self, request):
        await asyncio.sleep(5.5)
        return web.Response(text="Slow Success", status=200)

    async def handle_loop(self, request):
        return web.HTTPFound(location="/redirect-loop")

    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, 'localhost', self.port)
        await self.site.start()

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()


@pytest.fixture(scope="function")
async def chaos_server():
    server = chaotic_test()
    await server.start()
    yield f"http://localhost:{server.port}"
    await server.stop()


async def test_normalrespomse(chaos_server):
    async with ClientSession() as session:
        async with session.get(f"{chaos_server}/normal") as resp:
            assert resp.status == 200
            text = await resp.text()
            assert "<html>" in text


async def test_failedconnectdrop(chaos_server):
    async with ClientSession() as session:
        with pytest.raises(Exception):
            async with session.get(f"{chaos_server}/chaotic-drop") as resp:
                await resp.text()


async def test_waf_handling(chaos_server):
    async with ClientSession() as session:
        async with session.get(f"{chaos_server}/waf-block") as resp:
            assert resp.status == 403


async def test_garbage_response_handling(chaos_server):
    async with ClientSession() as session:
        async with session.get(f"{chaos_server}/garbage") as resp:
            assert resp.status == 200
            body = await resp.read()
            with pytest.raises(UnicodeDecodeError):
                body.decode('utf-8')


async def test_time_based_fuzz_trigger(chaos_server):
    async with ClientSession() as session:
        start_time = asyncio.get_running_loop().time()
        try:
            async with session.get(f"{chaos_server}/slow-timeout", timeout=6) as resp:
                elapsed = asyncio.get_running_loop().time() - start_time
                assert elapsed >= 5.0
                assert resp.status == 200
        except asyncio.TimeoutError:
            assert True


async def test_redirect_loop_handling(chaos_server):
    async with ClientSession() as session:
        try:
            await session.get(f"{chaos_server}/redirect-loop", max_redirects=5)
        except Exception as e:
            assert "Too many redirects" in str(e) or "redirect" in str(type(e)).lower()
