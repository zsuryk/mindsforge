import json
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.base import get_engine

# A local OpenAI-compatible server (Ollama shape): no API key required.
LOCAL_LLM_BASE_URL = "http://localhost:11434/v1"


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> Iterator[None]:
    """Keep the cached Settings object from leaking between tests.

    ``get_settings`` is an ``lru_cache`` singleton, so any test that mutates
    the environment must be bracketed by a cache clear or the next test reads
    the previous test's configuration.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _mock_fetch_video_title() -> Iterator[None]:
    with patch("app.api.jobs.fetch_video_title", return_value=None):
        yield


@pytest.fixture()
def configure_llm(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Point the LLM client at an OpenAI-compatible endpoint for one test."""

    def configure(
        base_url: str = LOCAL_LLM_BASE_URL,
        api_key: str = "",
        *,
        model: str | None = None,
    ) -> None:
        monkeypatch.setenv("OPENAI_BASE_URL", base_url)
        monkeypatch.setenv("OPENAI_API_KEY", api_key)
        if model is not None:
            monkeypatch.setenv("OPENAI_MODEL", model)
        get_settings.cache_clear()

    return configure


class OpenAIStub:
    """The single HTTP-layer seam for LLM calls, backed by ``MockTransport``.

    ``app.services.llm`` calls the module-level ``httpx.get``/``httpx.post``
    helpers, so the fixture routes those through a client whose transport is a
    ``MockTransport``. Requests are therefore real ``httpx.Request`` objects
    (headers, serialised body and all) and the client under test runs
    unmodified — nothing inside ``llm`` is patched.

    All state lives on the instance, and the ``llm_http`` fixture builds a
    fresh one per test, so nothing is shared between tests.
    """

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.replies: list[str] = []
        self.error: httpx.RequestError | None = None
        self.models_status = 200
        self.completions_status = 200
        self.raw_handler: Callable[[httpx.Request], httpx.Response] | None = None
        self.routes: dict[str, Callable[[httpx.Request], httpx.Response]] = {}
        self._client = httpx.Client(transport=httpx.MockTransport(self._handle))

    # --- test-side scripting ---

    def reply_with(self, *contents: str) -> "OpenAIStub":
        """Queue chat-completion reply bodies, consumed in order.

        With a single queued body every call returns it, which covers both
        steps of the read-then-fill flow. With none queued, replies are empty
        strings (so the client's own "empty reply" guard is what fails).
        """
        self.replies.extend(contents)
        return self

    def fail_with(self, error: httpx.RequestError) -> "OpenAIStub":
        """Make every request raise a transport error."""
        self.error = error
        return self

    def models_status_is(self, status_code: int) -> "OpenAIStub":
        """Answer ``GET /models`` (the health probe) with a given status."""
        self.models_status = status_code
        return self

    def completions_status_is(self, status_code: int) -> "OpenAIStub":
        """Answer ``POST /chat/completions`` with a non-200 status."""
        self.completions_status = status_code
        return self

    def respond_with(
        self, handler: Callable[[httpx.Request], httpx.Response]
    ) -> "OpenAIStub":
        """Answer every request with a bespoke response, bypassing the defaults."""
        self.raw_handler = handler
        return self

    def route(
        self,
        url_contains: str,
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> "OpenAIStub":
        """Answer requests whose URL contains ``url_contains`` with ``handler``.

        Lets a test that exercises two outbound HTTP services (the LLM and
        Tavily, say) share one transport instead of stacking httpx patches.
        """
        self.routes[url_contains] = handler
        return self

    # --- assertion helpers ---

    @property
    def urls(self) -> list[str]:
        return [str(request.url) for request in self.requests]

    @property
    def completion_requests(self) -> list[httpx.Request]:
        return [
            request
            for request in self.requests
            if request.url.path.endswith("/chat/completions")
        ]

    def messages(self, call: int = 0) -> list[dict[str, str]]:
        return json.loads(self.completion_requests[call].content)["messages"]

    def prompt(self, call: int = 0, message: int = -1) -> str:
        """Content of one message of the n-th ``/chat/completions`` call."""
        return self.messages(call)[message]["content"]

    def roles(self, call: int = 0) -> list[str]:
        return [message["role"] for message in self.messages(call)]

    def close(self) -> None:
        self._client.close()

    # --- transport ---

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if self.raw_handler is not None:
            return self.raw_handler(request)
        for url_contains, handler in self.routes.items():
            if url_contains in str(request.url):
                return handler(request)
        if request.url.path.endswith("/models"):
            return httpx.Response(self.models_status, json={"data": []})
        content = self.replies.pop(0) if len(self.replies) > 1 else (
            self.replies[0] if self.replies else ""
        )
        return httpx.Response(
            self.completions_status,
            json={"choices": [{"message": {"role": "assistant", "content": content}}]},
        )


@pytest.fixture()
def llm_http(monkeypatch: pytest.MonkeyPatch) -> Iterator[OpenAIStub]:
    """Intercept every httpx call the LLM client makes.

    Returns the :class:`OpenAIStub` driving the responses: script it before
    exercising the client, assert on it afterwards.
    """
    stub = OpenAIStub()
    monkeypatch.setattr(httpx, "get", stub._client.get)
    monkeypatch.setattr(httpx, "post", stub._client.post)
    yield stub
    stub.close()


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, Path]]:
    db_path = tmp_path / "test.db"
    media_dir = tmp_path / "media"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("MEDIA_DIR", str(media_dir))
    monkeypatch.setenv("PROCESS_JOBS_ON_SUBMIT", "false")
    get_settings.cache_clear()
    get_engine.cache_clear()

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client, tmp_path

    get_settings.cache_clear()
    get_engine.cache_clear()
