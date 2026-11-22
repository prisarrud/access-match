from collections.abc import Awaitable, Callable

from langchain_core.documents import Document

from ..properties.schemas import Property
from .schemas import Criterion

# Each Document carries catalog metadata: property_id, document_id, document_type,
# source_path, one-based page and one-based chunk_index.
DocumentContextProvider = Callable[[Property, Criterion], Awaitable[list[Document]]]
