import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from api.app.properties.catalog import CatalogLoadError, load_catalog

PHOTO = {"id": "entrada", "path": "imovel/entrada.jpg", "alt": "Entrance door"}
DOCUMENT = {
    "id": "memorial",
    "path": "imovel/memorial.md",
    "title": "Design specification",
    "type": "memorial",
}

class CatalogTests(TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.path = Path(directory) / "properties.json"
        self.listing = {"id": "imovel", "title": "Apartment", "description": "Original text.\n"}

    def write_catalog(self, *properties):
        self.path.write_text(json.dumps({"properties": properties}), encoding="utf-8")

    def test_accepts_all_attachment_combinations_and_preserves_description(self):
        self.write_catalog(
            {**self.listing, "photos": [PHOTO], "documents": [DOCUMENT]},
            {**self.listing, "id": "so-foto", "photos": [PHOTO], "documents": []},
            {**self.listing, "id": "so-documento", "documents": [DOCUMENT]},
            {**self.listing, "id": "sem-anexos"},
        )

        items = load_catalog(self.path).properties
        self.assertEqual(
            [(len(item.photos), len(item.documents)) for item in items],
            [(1, 1), (1, 0), (0, 1), (0, 0)],
        )
        self.assertEqual(items[0].description, self.listing["description"])
        self.assertIsNone(items[0].documents[0].date)

    def test_missing_catalog_is_empty_but_invalid_json_raises(self):
        self.assertEqual(load_catalog(self.path).properties, [])
        self.path.write_text("{", encoding="utf-8")

        with self.assertRaisesRegex(CatalogLoadError, r"Invalid catalog.*properties\.json"):
            load_catalog(self.path)

    def test_rejects_duplicate_property_ids(self):
        self.write_catalog(self.listing, self.listing)

        with self.assertRaisesRegex(CatalogLoadError, "Duplicate property ID.*imovel"):
            load_catalog(self.path)

    def test_rejects_duplicate_source_ids_across_attachment_types(self):
        self.write_catalog({
            **self.listing,
            "photos": [PHOTO],
            "documents": [{**DOCUMENT, "id": PHOTO["id"]}],
        })

        with self.assertRaisesRegex(CatalogLoadError, "Duplicate source ID.*imovel.*entrada"):
            load_catalog(self.path)

    def test_rejects_invalid_source_fields(self):
        self.write_catalog({
            **self.listing,
            "photos": [{**PHOTO, "path": "../entrada.jpg"}],
            "documents": [{**DOCUMENT, "date": "01/02/2026", "type": "anuncio"}],
        })

        with self.assertRaises(CatalogLoadError) as error:
            load_catalog(self.path)
        for field in ("photos.0.path", "documents.0.date", "documents.0.type"):
            self.assertIn(field, str(error.exception))
