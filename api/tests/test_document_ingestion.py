from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader, PdfWriter

from api.app.documents.ingestion import PdfExtractionError, prepare_chunks
from api.app.properties.catalog import DEFAULT_CATALOG_PATH, load_catalog
from api.app.properties.schemas import Document


class PdfIngestionTests(TestCase):
    def setUp(self):
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
        self.catalog_dir = DEFAULT_CATALOG_PATH.parent
        self.property = next(
            item for item in load_catalog().properties if item.id == "residencial-oliveira"
        )

    def test_demo_measurements_retain_their_pdf_page_and_source(self):
        expected = {"memorial": "85 cm", "vistoria": "78 cm"}
        self.assertEqual({document.type for document in self.property.documents}, set(expected))
        for document in self.property.documents:
            with self.subTest(document=document.id):
                chunks = prepare_chunks(self.property.id, document, self.catalog_dir, self.splitter)
                measurement = next(
                    chunk for chunk in chunks if expected[document.type] in chunk.page_content
                )
                self.assertEqual(measurement.metadata["page"], 2)
                self.assertEqual(measurement.metadata["property_id"], self.property.id)
                self.assertEqual(measurement.metadata["document_id"], document.id)
                self.assertEqual(measurement.metadata["document_type"], document.type)
                self.assertEqual(measurement.metadata["document_date"], document.date)
                self.assertEqual(measurement.metadata["source_path"], document.path)

    def test_blank_pages_preserve_numbering_and_chunks_stay_within_their_page(self):
        catalog_dir = Path(self.enterContext(TemporaryDirectory())).resolve()
        document = self.property.documents[0].model_copy(update={"path": "sample.pdf"})
        reader = PdfReader(self.catalog_dir / self.property.documents[0].path)
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.append(reader, pages=(0, 2))
        writer.write(catalog_dir / document.path)

        chunks = prepare_chunks(self.property.id, document, catalog_dir, self.splitter)
        self.assertEqual({chunk.metadata["page"] for chunk in chunks}, {2, 3})
        for chunk in chunks:
            page_text = reader.pages[chunk.metadata["page"] - 2].extract_text()
            self.assertIn(chunk.page_content, page_text)

    def test_reports_missing_invalid_and_textless_pdfs(self):
        catalog_dir = Path(self.enterContext(TemporaryDirectory())).resolve()
        document = Document(id="sample", title="Inspection", type="vistoria", path="sample.pdf")
        path = catalog_dir / document.path

        with self.assertRaisesRegex(PdfExtractionError, "PDF not found"):
            prepare_chunks(self.property.id, document, catalog_dir, self.splitter)

        path.write_bytes(b"%PDF-1.4\n")
        with self.assertRaisesRegex(PdfExtractionError, "Unreadable PDF"):
            prepare_chunks(self.property.id, document, catalog_dir, self.splitter)

        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(path)
        with self.assertRaisesRegex(PdfExtractionError, "PDF has no extractable text"):
            prepare_chunks(self.property.id, document, catalog_dir, self.splitter)
