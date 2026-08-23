import mcp_trendpulse.cli as cli_module
from mcp_trendpulse import server


async def test_server_lifespan_loads_environment_before_browser(monkeypatch):
    events: list[str] = []

    def fake_load_environment() -> None:
        events.append("environment")

    class FakeBrowserManager:
        async def __aenter__(self):
            events.append("browser-enter")
            return self

        async def __aexit__(self, exc_type, exc, tb):
            events.append("browser-exit")
            return False

    monkeypatch.setattr(server, "load_environment", fake_load_environment)
    monkeypatch.setattr(server, "BrowserManager", FakeBrowserManager)

    async with server.lifespan(server.mcp):
        assert events == ["environment", "browser-enter"]

    assert events == ["environment", "browser-enter", "browser-exit"]


def test_cli_loads_environment_when_invoked(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(cli_module, "load_environment", lambda: calls.append("environment"))

    cli_module.cli.callback()

    assert calls == ["environment"]
