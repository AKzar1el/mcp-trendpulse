from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from mcp_trendpulse.news import BrowserManager


def reset_browser_manager_state():
    BrowserManager._browser = None
    BrowserManager._playwright = None
    BrowserManager._class_contexts = 0


@pytest.fixture(autouse=True)
def reset_browser_manager():
    reset_browser_manager_state()
    yield
    reset_browser_manager_state()


async def test_browser_launch_failure_raises_runtime_error_and_cleans_up():
    launch_error = Exception("browser executable is missing")
    playwright = SimpleNamespace(
        chromium=SimpleNamespace(launch=AsyncMock(side_effect=launch_error)),
        stop=AsyncMock(),
    )
    runner = SimpleNamespace(start=AsyncMock(return_value=playwright))

    with patch("mcp_trendpulse.news.async_playwright", return_value=runner):
        with pytest.raises(RuntimeError, match="playwright install chromium") as error:
            await BrowserManager._get_browser()

    assert not isinstance(error.value, SystemExit)
    assert error.value.__cause__ is launch_error
    playwright.stop.assert_awaited_once()
    assert BrowserManager._playwright is None
    assert BrowserManager._browser is None


async def test_browser_manager_can_start_after_a_previous_launch_failure():
    failed_playwright = SimpleNamespace(
        chromium=SimpleNamespace(launch=AsyncMock(side_effect=Exception("launch failed"))),
        stop=AsyncMock(),
    )
    browser = SimpleNamespace(close=AsyncMock())
    successful_playwright = SimpleNamespace(
        chromium=SimpleNamespace(launch=AsyncMock(return_value=browser)),
        stop=AsyncMock(),
    )
    runner = SimpleNamespace(start=AsyncMock(side_effect=[failed_playwright, successful_playwright]))

    with patch("mcp_trendpulse.news.async_playwright", return_value=runner):
        with pytest.raises(RuntimeError):
            await BrowserManager._get_browser()

        assert await BrowserManager._get_browser() is browser

    assert BrowserManager._playwright is successful_playwright
    assert BrowserManager._browser is browser
    failed_playwright.stop.assert_awaited_once()
    successful_playwright.chromium.launch.assert_awaited_once_with(headless=True)


async def test_browser_manager_successful_start_is_reused():
    browser = SimpleNamespace(close=AsyncMock())
    playwright = SimpleNamespace(
        chromium=SimpleNamespace(launch=AsyncMock(return_value=browser)),
        stop=AsyncMock(),
    )
    runner = SimpleNamespace(start=AsyncMock(return_value=playwright))

    with patch("mcp_trendpulse.news.async_playwright", return_value=runner):
        assert await BrowserManager._get_browser() is browser
        assert await BrowserManager._get_browser() is browser

    runner.start.assert_awaited_once()
    playwright.chromium.launch.assert_awaited_once_with(headless=True)
