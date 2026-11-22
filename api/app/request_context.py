from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID, uuid4

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def request_id() -> str | None:
    return _request_id.get()


@contextmanager
def request_context(header: str | None = None):
    if header and len(header) in (32, 36):
        try:
            UUID(header)
        except ValueError:
            header = None
    else:
        header = None

    identifier = header or uuid4().hex
    token = _request_id.set(identifier)
    try:
        yield identifier
    finally:
        _request_id.reset(token)
