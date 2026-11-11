import sys
import asyncio
from numpy import select
from numpy._core.umath import fabs
import pytest
from unittest.mock import patch ,  AsyncMock , MagicMock
from curl_cffi.requests import AsyncSession
from stabilitytests import chaos_server
import os


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from core.crawler import WebantulaCrawler, breaker
from core.graphmanager import GraphManager
from core.analyzer import Analyzer



class AsyncRedisMock:
    def __init__(self, *args, **kwargs):
        self.storage = {}

    def delete(self, *keys):
        for k in keys:
            if k in self.storage:
                del self.storage[k]
        return len(keys)

    async def sadd(self, key, value):
        if key not in self.storage:
            self.storage[key] = set()
        if value in self.storage[key]:
            return 0
        self.storage[key].add(value)
        return 1

    async def sismember(self, key, value):
        if key not in self.storage:
            return 0
        return 1 if value in self.storage[key] else 0

    async def scard(self, key):
        if key not in self.storage:
            return 0
        return len(self.storage[key])

    async def rpush(self, key, value):
        if key not in self.storage:
            self.storage[key] = []
        self.storage[key].append(value)
        return len(self.storage[key])

    async def blpop(self, key, timeout=5):
        if key not in self.storage or not self.storage[key]:
            return None
        return [key, self.storage[key].pop(0)]


class DummySignals:
    def __init__(self):
        self.node_added = self
        self.scan_finished = self
        self.emits = []
    def emit(self, *args, **kwargs):
        self.emits.append((args,kwargs))
        pass


@pytest.mark.asyncio
async def test_crawler_vs_chaos_server(chaos_server):
    manager = GraphManager()
    signals = DummySignals()
    analyzer = Analyzer()

    with patch('redis.asyncio.Redis', new=AsyncRedisMock):
        crawler = WebantulaCrawler(base_url=chaos_server, manager=manager, signals=signals, analyzer=analyzer)
        crawler.ratelimiter.check_delay = lambda domain: 0
        await crawler.r.rpush("task_queue", f"{chaos_server}/normal")
        await crawler.r.rpush("task_queue", f"{chaos_server}/garbage")
        async with AsyncSession(impersonate="chrome120") as session:
            try:
                await asyncio.wait_for(crawler.run_worker(session), timeout=4)
            except asyncio.TimeoutError:
                pass
        assert len(manager.graph.nodes) > 0
        visited_count = await crawler.r.scard("visited")
        assert visited_count > 0
        assert await crawler.r.sismember("visited", f"{chaos_server}/garbage") == 1


@pytest.mark.asyncio
async def test_circuit_breaker_trigger(chaos_server):
    manager = GraphManager()
    signals = DummySignals()
    analyzer = Analyzer()
    with patch('redis.asyncio.Redis', new=AsyncRedisMock):
        crawler = WebantulaCrawler(base_url=chaos_server, manager=manager, signals=signals, analyzer=analyzer)
    domain = "localhost"
    breaker.report_error(domain, status_code=429)
    is_blocked = breaker.blocked_checker(domain)
    assert is_blocked is True

@pytest.mark.asyncio
async def test_render_graph(chaos_server):
    graph = GraphManager()
    signals = DummySignals()
    start_url = f"{chaos_server}/start"
    inter_url = f"{chaos_server}/api/v1"
    vuln_url = f"{chaos_server}/api/v1/.env"
    await graph.add_node(start_url, score=0, status="safe")
    signals.emit("node_added", node=start_url)
    await graph.add_node(inter_url, score=10, status="safe")
    signals.emit("node_added", node=inter_url)
    await graph.add_node(vuln_url, score=95, status="vulnerable")
    signals.emit("node_added", node=vuln_url)
    await graph.add_edge(start_url, inter_url)
    await graph.add_edge(inter_url, vuln_url)
    await graph.add_node(f"{chaos_server}/false_positive", score=0, status="safe")
    await graph.add_edge(start_url, f"{chaos_server}/false_positive")
    test_filename = "shademap.html"
    await graph.save(start_node=start_url, filename=test_filename)
    assert os.path.exists(test_filename)
    assert graph.graph.nodes[vuln_url]['color'] == "#ff0033"
    assert graph.graph.nodes[vuln_url]['shape'] == 'diamond'
    assert graph.graph.nodes[inter_url]['color'] == "#ff0033"
    assert graph.graph.nodes[f"{chaos_server}/false_positive"]['color'] == "rgba(168, 85, 247, 0.4)"
    assert graph.graph.edges[start_url, inter_url]['width'] == 3.5
    assert graph.graph.edges[start_url, f"{chaos_server}/false_positive"]['width'] == 1
    signals.emit("scan_finished", total_nodes=len(graph.graph.nodes))



@pytest.mark.asyncio
async def test_correct_fuzz_discoverleaks(chaos_server):
    with patch('redis.asyncio.Redis', new=AsyncRedisMock):
        signals = DummySignals()
        crawler = WebantulaCrawler(base_url=chaos_server, manager=None, signals=signals, analyzer=None)
        crawler.ratelimiter.check_delay = lambda domain: 0
        matchers = {"status":[200,500], "negative_regex": []}
        session_honeypot = MagicMock()
        resp_honeypot = AsyncMock()
        resp_honeypot.status = 200
        resp_honeypot.headers = {"Content-Type": "text/html; charset=utf-8"}
        resp_honeypot.read = AsyncMock(return_value=b"<html><head><title>Access Denied</title></head><body>WAF Blocked. Enter security token or password to bypass template error.</body></html>")
        context_honeypot = AsyncMock()
        context_honeypot.__aenter__.return_value = resp_honeypot
        context_honeypot.__aexit__ = AsyncMock()
        session_honeypot.get.return_value = context_honeypot
        result_honeypot = await crawler.probe_path(
            session=session_honeypot, url=chaos_server, path="/.env", path_matchers=matchers
        )
        assert result_honeypot is None
        session_log = MagicMock()
        resp_log = AsyncMock()
        resp_log.status = 200
        resp_log.headers = {"Content-Type": "text/plain"}
        resp_log.read = AsyncMock(return_value=b"[CRITICAL] 2026-09-20 404 page not found exception triggered. Connection failed due to wrong secret token. Dump: app_password=admin123")
        context_log = AsyncMock()
        context_log.__aenter__.return_value = resp_log
        context_log.__aexit__ = AsyncMock()
        session_log.get.return_value = context_log
        result_log = await crawler.probe_path(
            session=session_log, url=chaos_server, path="/production.log", path_matchers=matchers
        )
        assert result_log is not None
        assert result_log["status"] == "vulnerable"
        session_binary = MagicMock()
        resp_binary = AsyncMock()
        resp_binary.status = 200
        resp_binary.headers = {"Content-Type": "application/x-gzip"}
        resp_binary.read = AsyncMock(return_value=b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff\x50\x4b\x03\x04\x00\x00\xff\x00\xae\x32")
        context_binary = AsyncMock()
        context_binary.__aenter__.return_value = resp_binary
        context_binary.__aexit__ = AsyncMock()
        session_binary.get.return_value = context_binary

        result_binary = await crawler.probe_path(
            session=session_binary, url=chaos_server, path="/dump.tar.gz", path_matchers=matchers
        )
        assert result_binary is not None
        assert result_binary["status"] == "vulnerable"
        assert "dump.tar.gz" in result_binary["url"]

        session_env = MagicMock()
        resp_env = AsyncMock()
        resp_env.status = 200
        resp_env.headers = {"Content-Type": "application/octet-stream"}
        resp_env.read = AsyncMock(return_value=b"STRIPE_API_KEY=sk_live_51M\n# Production config\nAWS_SECRET_ACCESS_KEY=ABC123XYZ")
        context_env = AsyncMock()
        context_env.__aenter__.return_value = resp_env
        context_env.__aexit__ = AsyncMock()
        session_env.get.return_value = context_env

        result_env = await crawler.probe_path(
            session=session_env, url=chaos_server, path="/.env", path_matchers=matchers
        )
        assert result_env is not None
        assert result_env["status"] == "vulnerable"


@pytest.mark.asyncio
async def test_cottectpathfind(chaos_server):
    graph = GraphManager()
    await graph.add_edge("root", "node_A")
    await graph.add_edge("node_A", "node_B")
    await graph.add_edge("node_B", "target_vuln")
    await graph.add_edge("root", "node_C")
    await graph.add_edge("node_C", "node_D")
    await graph.add_edge("node_D", "node_E")
    await graph.add_edge("node_E", "target_vuln")
    shortest = graph.find_shorttestpath("root", "target_vuln")
    assert shortest == ["root", "node_A", "node_B", "target_vuln"]
    await graph.add_edge("node_B", "node_A")
    assert shortest == ["root", "node_A", "node_B", "target_vuln"]
    analyzer_mock = MagicMock()
    def mock_calc_score(node):
        if node == "target_vuln":
            graph.graph.nodes[node]['score'] = 95
            graph.graph.nodes[node]['status'] = 'vulnerable'
        else:
            graph.graph.nodes[node]['score'] = 0
            graph.graph.nodes[node]['status'] = 'safe'
    analyzer_mock.calc_score.side_effect = mock_calc_score
    graph.runAnlasysiss(analyzer_mock)
    await graph.save(start_node="root", filename="test_shortest_path_map.html")
    assert graph.find_shorttestpath("root", "non_existent_node") is None
    assert graph.find_shorttestpath("non_existent_node", "target_vuln") is None





@pytest.mark.asyncio
async def test_vulnfuzzer(chaos_server):
    with patch('redis.asyncio.Redis', new=AsyncRedisMock):
        crawler = WebantulaCrawler(base_url=chaos_server, manager=None, signals=None, analyzer=None)
        crawler.rsd = MagicMock()
        crawler.rsd.check_anomaly = AsyncMock(return_value=False)
        for mock_elapsed in [3,3.99]:
            crawler.doublechecl = AsyncMock(return_value=False)
            session_mock = AsyncMock()
            resp_mock = AsyncMock()
            resp_mock.status = 200
            resp_mock.text.return_value = "safe web page"
            context_mock = AsyncMock()
            context_mock.__aenter__.return_value = resp_mock
            session_mock.get.return_value = context_mock
            with patch('asyncio.get_running_loop') as mock_loop:
                loop_instance = MagicMock()
                loop_instance.time.side_effect = [0.0, mock_elapsed,4.0,10.0,11.0]
                mock_loop.return_value = loop_instance
                result =    await  crawler.probe_fuzz(
                    session=session_mock,
                    originalUrl=chaos_server,
                    test_url=f"{chaos_server}/api",
                    category="SQLi",
                    matchers={"status":[200,500], "regex": []}
                )
                if mock_elapsed >=  4:
                    assert result is None
                    assert crawler.doublechecl.called is False
                else:
                    assert result is None
                    assert crawler.doublechecl.called is True
                    assert crawler.doublechecl.return_value == False#проверяем что он вызвался и ничего не вернул
        crawler.doublechecl.return_value = True
        session_combinatorics = AsyncMock()
        resp_combinatorics = AsyncMock()
        resp_combinatorics.status = 200
        resp_combinatorics.text.return_value = "<html> echo: err ; db_state: super_error </html>"
        context_combinatorics = AsyncMock()
        context_combinatorics.__aenter__.return_value = resp_combinatorics
        session_combinatorics.get.return_value = context_combinatorics
        complex_url = f"{chaos_server}/search?p1=err&p2=super_error"
        result_combinatorics = await crawler.probe_fuzz(
            session=session_combinatorics,
            originalUrl=chaos_server,
            test_url=complex_url,
            category="SQL_Error",
            matchers={"status":[200,500], "regex": ["error"]}
        )

        assert result_combinatorics is not None
        assert "vulnerable" in str(result_combinatorics.get("status")).lower()
        crawler.doublechecl.return_value = False
        resp_mock_echo = AsyncMock()
        resp_mock_echo.status = 200
        resp_mock_echo.text.return_value = "<html>reflected_val</html>"
        context_mock_echo = AsyncMock()
        context_mock_echo.__aenter__.return_value = resp_mock_echo
        session_mock.get.return_value = context_mock_echo

        result_echo = await crawler.probe_fuzz(
            session=session_mock,
            originalUrl=chaos_server,
            test_url=f"{chaos_server}/search?query=reflected_val",
            category="XSS",
            matchers={"status":[200,500], "regex": ["reflected_val"]}
        )
        assert result_echo is None
        crawler.doublechecl.return_value = True
        resp_mock_err = AsyncMock()
        resp_mock_err.status = 500
        resp_mock_err.text.return_value = "fatal driver exception"
        context_mock_err = AsyncMock()
        context_mock_err.__aenter__.return_value = resp_mock_err
        session_mock.get.return_value = context_mock_err

        result_err = await crawler.probe_fuzz(
            session=session_mock,
            originalUrl=chaos_server,
            test_url=f"{chaos_server}/api?q=payload",
            category=" sql_ErrorBased",
            matchers={"status":[200,500], "regex": ["exception"]}
        )
        assert result_err is not None
        assert "vulnerable" in str(result_err).lower()
        resp_mock_404 = AsyncMock()
        resp_mock_404.status = 200
        resp_mock_404.text.return_value = "sorry, page not found"
        context_mock_404 = AsyncMock()
        context_mock_404.__aenter__.return_value = resp_mock_404
        session_mock.get.return_value = context_mock_404
        crawler.doublechecl = AsyncMock(return_value=False)
        result_404 = await crawler.probe_fuzz(
            session=session_mock,
            originalUrl=chaos_server,
            test_url=f"{chaos_server}/api?id=payload",
            category="SQLi",
            matchers={"status":[200,500], "regex": ["page"]}
        )
        assert result_404 is None



@pytest.mark.asyncio
async def test_doublechek(chaos_server):
    crawler = WebantulaCrawler(base_url=chaos_server, manager=None, analyzer=None, signals=None)
    if not hasattr(crawler, 'pld'):
        crawler.pld = PayloadHider()

    async with AsyncSession(impersonate="chrome120") as session:
        res_lag = await crawler.doublechecl(
            session,
            f"{chaos_server}/slow-timeout?id=1%20AND%20WAITFOR%20DELAY%20'0:0:4'",
            5.0
        )
        assert res_lag is False
        res_xss = await crawler.doublechecl(
            session,
            f"{chaos_server}/normal?name=%3Cscript%3Ealert(4)%3C/script%3E",
            0.05
        )
        assert res_xss is False
        res_ssti = await crawler.doublechecl(
            session,
            f"{chaos_server}/normal?template=%7B%7B4*4%7D%7D",
            0.08
        )
        assert res_ssti is False
        res_ssrf = await crawler.doublechecl(
            session,
            f"{chaos_server}/normal?url=http://127.0.0",
            0.1
        )
        assert res_ssrf is False
