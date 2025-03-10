import typing
from datetime import timedelta

import httpcore
import pytest

import httpx
from tests.utils import MockTransport


def test_get(server):
    url = server.url
    with httpx.Client(http2=True) as http:
        response = http.get(url)
    assert response.status_code == 200
    assert response.url == url
    assert response.content == b"Hello, world!"
    assert response.text == "Hello, world!"
    assert response.http_version == "HTTP/1.1"
    assert response.encoding is None
    assert response.request.url == url
    assert response.headers
    assert response.is_redirect is False
    assert repr(response) == "<Response [200 OK]>"
    assert response.elapsed > timedelta(0)


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("invalid://example.org", id="scheme-not-http(s)"),
        pytest.param("://example.org", id="no-scheme"),
        pytest.param("http://", id="no-host"),
    ],
)
def test_get_invalid_url(server, url):
    with httpx.Client() as client:
        with pytest.raises((httpx.UnsupportedProtocol, httpx.LocalProtocolError)):
            client.get(url)


def test_build_request(server):
    url = server.url.copy_with(path="/echo_headers")
    headers = {"Custom-header": "value"}

    with httpx.Client() as client:
        request = client.build_request("GET", url)
        request.headers.update(headers)
        response = client.send(request)

    assert response.status_code == 200
    assert response.url == url

    assert response.json()["Custom-header"] == "value"


def test_build_post_request(server):
    url = server.url.copy_with(path="/echo_headers")
    headers = {"Custom-header": "value"}

    with httpx.Client() as client:
        request = client.build_request("POST", url)
        request.headers.update(headers)
        response = client.send(request)

    assert response.status_code == 200
    assert response.url == url

    assert response.json()["Content-length"] == "0"
    assert response.json()["Custom-header"] == "value"


def test_post(server):
    with httpx.Client() as client:
        response = client.post(server.url, content=b"Hello, world!")
    assert response.status_code == 200
    assert response.reason_phrase == "OK"


def test_post_json(server):
    with httpx.Client() as client:
        response = client.post(server.url, json={"text": "Hello, world!"})
    assert response.status_code == 200
    assert response.reason_phrase == "OK"


def test_stream_response(server):
    with httpx.Client() as client:
        with client.stream("GET", server.url) as response:
            content = response.read()
    assert response.status_code == 200
    assert content == b"Hello, world!"


def test_stream_iterator(server):
    body = b""

    with httpx.Client() as client:
        with client.stream("GET", server.url) as response:
            for chunk in response.iter_bytes():
                body += chunk

    assert response.status_code == 200
    assert body == b"Hello, world!"


def test_raw_iterator(server):
    body = b""

    with httpx.Client() as client:
        with client.stream("GET", server.url) as response:
            for chunk in response.iter_raw():
                body += chunk

    assert response.status_code == 200
    assert body == b"Hello, world!"


def test_raise_for_status(server):
    with httpx.Client() as client:
        for status_code in (200, 400, 404, 500, 505):
            response = client.request(
                "GET", server.url.copy_with(path=f"/status/{status_code}")
            )
            if 400 <= status_code < 600:
                with pytest.raises(httpx.HTTPStatusError) as exc_info:
                    response.raise_for_status()
                assert exc_info.value.response == response
                assert exc_info.value.request.url.path == f"/status/{status_code}"
            else:
                assert response.raise_for_status() is None  # type: ignore


def test_options(server):
    with httpx.Client() as client:
        response = client.options(server.url)
    assert response.status_code == 200
    assert response.reason_phrase == "OK"


def test_head(server):
    with httpx.Client() as client:
        response = client.head(server.url)
    assert response.status_code == 200
    assert response.reason_phrase == "OK"


def test_put(server):
    with httpx.Client() as client:
        response = client.put(server.url, content=b"Hello, world!")
    assert response.status_code == 200
    assert response.reason_phrase == "OK"


def test_patch(server):
    with httpx.Client() as client:
        response = client.patch(server.url, content=b"Hello, world!")
    assert response.status_code == 200
    assert response.reason_phrase == "OK"


def test_delete(server):
    with httpx.Client() as client:
        response = client.delete(server.url)
    assert response.status_code == 200
    assert response.reason_phrase == "OK"


def test_base_url(server):
    base_url = server.url
    with httpx.Client(base_url=base_url) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert response.url == base_url


def test_merge_absolute_url():
    client = httpx.Client(base_url="https://www.example.com/")
    request = client.build_request("GET", "http://www.example.com/")
    assert request.url == "http://www.example.com/"


def test_merge_relative_url():
    client = httpx.Client(base_url="https://www.example.com/")
    request = client.build_request("GET", "/testing/123")
    assert request.url == "https://www.example.com/testing/123"


def test_merge_relative_url_with_path():
    client = httpx.Client(base_url="https://www.example.com/some/path")
    request = client.build_request("GET", "/testing/123")
    assert request.url == "https://www.example.com/some/path/testing/123"


def test_merge_relative_url_with_dotted_path():
    client = httpx.Client(base_url="https://www.example.com/some/path")
    request = client.build_request("GET", "../testing/123")
    assert request.url == "https://www.example.com/some/testing/123"


def test_pool_limits_deprecated():
    limits = httpx.Limits()

    with pytest.warns(DeprecationWarning):
        httpx.Client(pool_limits=limits)

    with pytest.warns(DeprecationWarning):
        httpx.AsyncClient(pool_limits=limits)


def test_context_managed_transport():
    class Transport(httpcore.SyncHTTPTransport):
        def __init__(self):
            self.events = []

        def close(self):
            # The base implementation of httpcore.SyncHTTPTransport just
            # calls into `.close`, so simple transport cases can just override
            # this method for any cleanup, where more complex cases
            # might want to additionally override `__enter__`/`__exit__`.
            self.events.append("transport.close")

        def __enter__(self):
            super().__enter__()
            self.events.append("transport.__enter__")

        def __exit__(self, *args):
            super().__exit__(*args)
            self.events.append("transport.__exit__")

    transport = Transport()
    with httpx.Client(transport=transport):
        pass

    assert transport.events == [
        "transport.__enter__",
        "transport.close",
        "transport.__exit__",
    ]


def test_context_managed_transport_and_mount():
    class Transport(httpcore.SyncHTTPTransport):
        def __init__(self, name: str):
            self.name: str = name
            self.events: typing.List[str] = []

        def close(self):
            # The base implementation of httpcore.SyncHTTPTransport just
            # calls into `.close`, so simple transport cases can just override
            # this method for any cleanup, where more complex cases
            # might want to additionally override `__enter__`/`__exit__`.
            self.events.append(f"{self.name}.close")

        def __enter__(self):
            super().__enter__()
            self.events.append(f"{self.name}.__enter__")

        def __exit__(self, *args):
            super().__exit__(*args)
            self.events.append(f"{self.name}.__exit__")

    transport = Transport(name="transport")
    mounted = Transport(name="mounted")
    with httpx.Client(transport=transport, mounts={"http://www.example.org": mounted}):
        pass

    assert transport.events == [
        "transport.__enter__",
        "transport.close",
        "transport.__exit__",
    ]
    assert mounted.events == [
        "mounted.__enter__",
        "mounted.close",
        "mounted.__exit__",
    ]


def hello_world(request):
    return httpx.Response(200, text="Hello, world!")


def test_client_closed_state_using_implicit_open():
    client = httpx.Client(transport=MockTransport(hello_world))

    assert not client.is_closed
    client.get("http://example.com")

    assert not client.is_closed
    client.close()

    assert client.is_closed
    with pytest.raises(RuntimeError):
        client.get("http://example.com")


def test_client_closed_state_using_with_block():
    with httpx.Client(transport=MockTransport(hello_world)) as client:
        assert not client.is_closed
        client.get("http://example.com")

    assert client.is_closed
    with pytest.raises(RuntimeError):
        client.get("http://example.com")


def echo_raw_headers(request: httpx.Request) -> httpx.Response:
    data = [
        (name.decode("ascii"), value.decode("ascii"))
        for name, value in request.headers.raw
    ]
    return httpx.Response(200, json=data)


def test_raw_client_header():
    """
    Set a header in the Client.
    """
    url = "http://example.org/echo_headers"
    headers = {"Example-Header": "example-value"}

    client = httpx.Client(transport=MockTransport(echo_raw_headers), headers=headers)
    response = client.get(url)

    assert response.status_code == 200
    assert response.json() == [
        ["Host", "example.org"],
        ["Accept", "*/*"],
        ["Accept-Encoding", "gzip, deflate, br"],
        ["Connection", "keep-alive"],
        ["User-Agent", f"python-httpx/{httpx.__version__}"],
        ["Example-Header", "example-value"],
    ]


def unmounted(request: httpx.Request) -> httpx.Response:
    data = {"app": "unmounted"}
    return httpx.Response(200, json=data)


def mounted(request: httpx.Request) -> httpx.Response:
    data = {"app": "mounted"}
    return httpx.Response(200, json=data)


def test_mounted_transport():
    transport = MockTransport(unmounted)
    mounts = {"custom://": MockTransport(mounted)}

    client = httpx.Client(transport=transport, mounts=mounts)

    response = client.get("https://www.example.com")
    assert response.status_code == 200
    assert response.json() == {"app": "unmounted"}

    response = client.get("custom://www.example.com")
    assert response.status_code == 200
    assert response.json() == {"app": "mounted"}


def test_all_mounted_transport():
    mounts = {"all://": MockTransport(mounted)}

    client = httpx.Client(mounts=mounts)

    response = client.get("https://www.example.com")
    assert response.status_code == 200
    assert response.json() == {"app": "mounted"}
