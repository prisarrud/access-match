from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
from langchain_core.documents import Document
from api.app.documents import retrieval

class DocumentRetrievalTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.embeddings = SimpleNamespace(model="nomic-embed-text")
        self.engine = AsyncMock()
        self.store = AsyncMock()
        self.enterContext(patch.object(
            retrieval, "load_index_config",
            return_value=("postgresql://localhost/test", self.embeddings),
        ))
        self.enterContext(patch.object(
            retrieval.PGEngine, "from_connection_string", return_value=self.engine,
        ))
        self.enterContext(patch.object(
            retrieval, "create_vector_store", return_value=self.store,
        ))

    async def test_filters_by_property_and_model_and_keeps_complementary_sources(self):
        documents = [
            Document(page_content=text, metadata={
                "property_id": "residencial-oliveira",
                "document_id": f"residencial-oliveira-{kind}",
                "document_type": kind,
                "source_path": f"property-b/{kind}.pdf",
                "page": 2,
            })
            for kind, text in (("memorial", "Vão livre previsto de 85 cm."),
                               ("vistoria", "Vão livre medido de 78 cm."))
        ]
        self.store.asimilarity_search.return_value = documents

        result = await retrieval.retrieve_evidence("residencial-oliveira", "largura")

        self.assertEqual(result, documents)
        self.store.asimilarity_search.assert_awaited_once_with(
            retrieval.CRITERION_QUERIES["largura"],
            k=4,
            filter={"property_id": "residencial-oliveira", "embedding_model": self.embeddings.model},
        )
        self.engine.close.assert_awaited_once()

    async def test_no_results_returns_an_empty_list(self):
        self.store.asimilarity_search.return_value = []
        self.assertEqual(await retrieval.retrieve_evidence("edificio-ipe", "largura"), [])

    async def test_infrastructure_failure_raises_and_closes_the_engine(self):
        error = ConnectionError("Ollama unavailable")
        self.store.asimilarity_search.side_effect = error

        with self.assertRaises(retrieval.RetrievalError) as raised:
            await retrieval.retrieve_evidence("residencial-oliveira", "largura")

        self.assertIs(raised.exception.__cause__, error)
        self.engine.close.assert_awaited_once()
