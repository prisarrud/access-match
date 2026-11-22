from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app.main import app


class PropertyMediaTests(TestCase):
    def setUp(self):
        self.client = self.enterContext(TestClient(app))

    def properties(self):
        response = self.client.get("/properties")
        self.assertEqual(response.status_code, 200)
        return {item["id"]: item for item in response.json()}

    def test_serves_catalog_photo_with_its_alternative_text(self):
        photo, = self.properties()["edificio-ipe"]["photos"]
        self.assertIn("degrau", photo["alt"])
        response = self.client.get(photo["url"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertTrue(response.content.startswith(b"\xff\xd8"))

    def test_serves_pdfs_inline_and_supports_partial_requests(self):
        documents = self.properties()["residencial-oliveira"]["documents"]
        self.assertEqual(len(documents), 2)
        for document in documents:
            with self.subTest(document=document["id"]):
                response = self.client.get(document["url"], headers={"Range": "bytes=0-4"})
                self.assertEqual(response.status_code, 206)
                self.assertEqual(response.headers["content-type"], "application/pdf")
                self.assertTrue(response.headers["content-disposition"].startswith("inline"))
                self.assertEqual(response.content, b"%PDF-")

    def test_rejects_foreign_unknown_and_unavailable_catalog_sources(self):
        for source_id in ("residencial-oliveira-vistoria", "../property-a/entrada-frontal.jpg"):
            response = self.client.get("/properties/source", params={"property_id": "edificio-ipe", "source_id": source_id})
            self.assertEqual(response.status_code, 404)

        directory = Path(self.enterContext(TemporaryDirectory()))
        (directory / "media").mkdir()
        (directory / "entrada-frontal.jpg").touch()
        (directory / "media" / "property-a").symlink_to(directory, target_is_directory=True)

        with patch("api.app.properties.routes.DEFAULT_CATALOG_PATH", directory / "media" / "properties.json"):
            properties = self.properties()
            photo, = properties["edificio-ipe"]["photos"]
            self.assertIsNone(photo["url"])
            self.assertIn("degrau", photo["alt"])
            self.assertTrue(all(item["url"] is None and item["title"] for item in properties["residencial-oliveira"]["documents"]))
            response = self.client.get("/properties/source", params={"property_id": "edificio-ipe", "source_id": photo["id"]})
            self.assertEqual(response.status_code, 404)
