from types import SimpleNamespace
from unittest.mock import MagicMock

import requests
from trendspy import Trends

from mcp_trendpulse import news


def _trends_client_with_session(session):
    client = Trends(request_delay=0, max_retries=1)
    client.session = session
    return news.configure_trends_request_timeout(client, timeout=7)


def test_trendspy_get_requests_receive_the_project_timeout():
    session = MagicMock()
    session.proxies = {}
    session.get.return_value = SimpleNamespace(status_code=200)
    client = _trends_client_with_session(session)

    response = client._get(
        "https://trends.example.test/get",
        params={"query": "python"},
        headers={"accept": "application/json"},
    )

    assert response.status_code == 200
    session.get.assert_called_once_with(
        "https://trends.example.test/get",
        params={"query": "python"},
        headers={"accept": "application/json"},
        timeout=7,
    )


def test_trendspy_post_requests_receive_the_project_timeout():
    session = MagicMock()
    session.proxies = {}
    client = _trends_client_with_session(session)

    client._get_batch("request-id", {"keyword": "python"})

    session.post.assert_called_once()
    _, post_data = session.post.call_args.args
    assert post_data.startswith("f.req=")
    assert session.post.call_args.kwargs == {
        "headers": {"content-type": "application/x-www-form-urlencoded;charset=UTF-8"},
        "timeout": 7,
    }


def test_trendspy_retries_continue_to_use_the_project_timeout():
    session = MagicMock()
    session.proxies = {}
    response = SimpleNamespace(status_code=200)
    session.get.side_effect = [requests.Timeout("request timed out"), response]
    client = Trends(request_delay=0, max_retries=2)
    client.session = session
    client = news.configure_trends_request_timeout(client, timeout=7)

    assert client._get("https://trends.example.test/get") is response
    assert session.get.call_count == 2
    assert all(call.kwargs["timeout"] == 7 for call in session.get.call_args_list)


def test_timeout_session_preserves_explicit_timeout_and_request_options():
    session = MagicMock()
    session.proxies = {}
    client = _trends_client_with_session(session)

    client.session.get("https://trends.example.test/get", timeout=3, stream=True)
    client.session.post("https://trends.example.test/post", "payload", timeout=None, verify=False)

    session.get.assert_called_once_with(
        "https://trends.example.test/get",
        timeout=3,
        stream=True,
    )
    session.post.assert_called_once_with(
        "https://trends.example.test/post",
        "payload",
        timeout=None,
        verify=False,
    )


def test_project_trends_client_uses_a_timeout_session():
    assert isinstance(news.tr.session, news.TimeoutSession)
    assert news.tr.session.timeout == news.TRENDS_HTTP_TIMEOUT_SECONDS
