import asyncio
import base64
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from PIL import Image

from api.app.main import app
from api.app.photos import analysis

class PhotoAnalysisTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(TemporaryDirectory()))
        self.catalog = self.folder / "properties.json"
        self.valid_photo = self.folder / "front.jpg"
        image = Image.new("RGB", (16, 16))
        image.paste("white", (0, 0, 8, 16))
        image.save(self.valid_photo)
        self.photo = {"id": "front", "path": self.valid_photo.name, "alt": "unused alt text"}
        self.coverage = AsyncMock(return_value={
            "calcada": "partial", "portao": "out_of_frame", "trajeto": "partial",
            "patamar": "visible", "porta_entrada": "visible",
        })
        self.invoke = AsyncMock(return_value={
            "observations": [{"element": "degrau", "location": "entre_calcada_e_patamar"}],
        })
        model = SimpleNamespace(with_structured_output=lambda schema, **kwargs: SimpleNamespace(
            ainvoke=self.coverage if schema is analysis.VisibleParts else self.invoke,
        ))
        self.load_model = self.enterContext(patch.object(
            analysis, "load_vision_model", return_value=model,
        ))

    def write_catalog(self, photos):
        self.catalog.write_text(json.dumps({"properties": [
            {"id": "a", "title": "A", "description": "unused listing", "photos": photos},
            {"id": "b", "title": "B", "description": "unused listing", "photos": [
                {**self.photo, "id": "other-property"},
            ]},
        ]}), encoding="utf-8")

    async def test_sends_only_image_and_prompt_and_assigns_catalog_reference(self):
        self.write_catalog([self.photo])
        result = await analysis.analyze_property_photos("a", self.catalog)

        self.assertEqual(result.status, "complete")
        [photo] = result.photos
        self.assertEqual(photo.photo_id, "front")
        self.assertEqual(photo.observations[0].photo_id, "front")
        self.assertEqual(photo.observations[0].element, "degrau")
        self.assertEqual(photo.observations[0].location, "entre_calcada_e_patamar")
        self.assertEqual(photo.coverage.framing, "partial")
        self.assertIn("alternate_access", photo.to_confirm)
        [[message]] = self.invoke.await_args.args
        text, image = message.content
        self.assertNotIn(self.photo["alt"], text["text"])
        self.assertNotIn("unused listing", text["text"])
        self.assertEqual(text["text"], analysis.PROMPT)
        self.assertEqual(base64.b64decode(image["image_url"].split(",", 1)[1]), self.valid_photo.read_bytes())

    async def test_empty_catalog_photo_list_needs_no_model(self):
        self.write_catalog([])
        result = await analysis.analyze_property_photos("a", self.catalog)
        self.assertEqual(result.status, "no_photos")
        self.assertEqual(result.photos, [])
        self.load_model.assert_not_called()

    async def test_preserves_success_and_marks_failed_photos_as_pending(self):
        (self.folder / "broken.jpg").write_bytes(b"invalid image")
        self.write_catalog([
            {**self.photo, "id": "missing", "path": "missing.jpg"},
            {**self.photo, "id": "broken", "path": "broken.jpg"},
            {**self.photo, "id": "model-failure"},
            self.photo,
        ])
        self.invoke.side_effect = [ConnectionError("Ollama unavailable"), self.invoke.return_value]

        result = await analysis.analyze_property_photos("a", self.catalog)

        self.assertEqual(result.status, "partial")
        self.assertEqual([photo.error for photo in result.photos], [
            "missing_file", "unreadable_image", "model_error", None,
        ])
        self.assertEqual([photo.status for photo in result.photos], ["pending"] * 3 + ["analyzed"])
        self.assertTrue(result.photos[2].infrastructure_failure)
        self.assertEqual(result.photos[-1].observations[0].photo_id, "front")
        self.assertEqual(self.invoke.await_count, 2)

        self.invoke.side_effect = None
        self.invoke.reset_mock()
        retried = await analysis.analyze_property_photos("a", self.catalog)
        self.assertEqual(retried.status, "partial")
        self.assertEqual([photo.status for photo in retried.photos], ["pending", "pending", "analyzed", "analyzed"])
        self.assertEqual(retried.photos[-1], result.photos[-1])
        self.invoke.assert_awaited_once()

    async def test_reuses_validated_observations_and_only_reprocesses_changed_photo(self):
        second = self.folder / "second.jpg"
        second.write_bytes(self.valid_photo.read_bytes())
        self.write_catalog([self.photo, {**self.photo, "id": "second", "path": second.name}])
        first = await analysis.analyze_property_photos("a", self.catalog)
        folder = self.folder / ".photo-analysis"
        entries = [analysis.PhotoCacheEntry.model_validate_json(path.read_bytes()) for path in folder.glob("*.json")]
        self.assertEqual({item.key.photo_id for item in entries}, {"front", "second"})
        self.assertTrue(all(item.key.property_id == "a" for item in entries))
        self.assertTrue(all(item.key.file_sha256 == sha256(second.read_bytes()).hexdigest() for item in entries))
        self.assertTrue(all(item.key.configuration.prompt_version for item in entries))

        self.load_model.reset_mock()
        self.coverage.reset_mock()
        self.invoke.reset_mock()
        again = await analysis.analyze_property_photos("a", self.catalog)
        self.assertEqual(again, first)
        self.load_model.assert_not_called()

        image = Image.new("RGB", (16, 16), "white")
        image.paste("black", (0, 0, 4, 16))
        image.save(second)
        self.invoke.side_effect = ConnectionError("Ollama unavailable")
        failed = await analysis.analyze_property_photos("a", self.catalog)
        self.assertEqual(failed.status, "partial")
        self.assertEqual(failed.photos[0], first.photos[0])
        self.assertEqual(failed.photos[1].status, "pending")
        self.assertEqual(failed.photos[1].observations, [])
        self.invoke.assert_awaited_once()

        self.invoke.side_effect = None
        self.coverage.reset_mock()
        self.invoke.reset_mock()
        self.invoke.return_value = {"observations": []}
        changed = await analysis.analyze_property_photos("a", self.catalog)
        self.assertEqual(changed.photos[0], first.photos[0])
        self.assertEqual(changed.photos[1].observations, [])
        self.coverage.assert_awaited_once()
        self.invoke.assert_awaited_once()

    async def test_prompt_or_model_change_requires_fresh_analysis(self):
        self.write_catalog([self.photo])
        await analysis.analyze_property_photos("a", self.catalog)
        self.invoke.reset_mock()
        with patch.object(analysis, "PROMPT", analysis.PROMPT + " Test prompt revision."):
            await analysis.analyze_property_photos("a", self.catalog)
            self.invoke.assert_awaited_once()

        self.invoke.reset_mock()
        with patch.dict(analysis.os.environ, {"OLLAMA_VISION_MODEL": "different-model"}):
            await analysis.analyze_property_photos("a", self.catalog)
            self.invoke.assert_awaited_once()

    async def test_concurrent_requests_share_the_preparation(self):
        self.write_catalog([self.photo])
        coverage = self.coverage.return_value

        async def yield_during_analysis(_messages):
            await asyncio.sleep(0)
            return coverage

        self.coverage.side_effect = yield_during_analysis
        first, second = await asyncio.gather(
            analysis.analyze_property_photos("a", self.catalog),
            analysis.analyze_property_photos("a", self.catalog),
        )
        self.assertEqual(first, second)
        self.coverage.assert_awaited_once()
        self.invoke.assert_awaited_once()

    def test_background_prepares_catalog_updates_without_a_comparison(self):
        self.write_catalog([self.photo])
        independent = self.folder / "second.jpg"
        independent.write_bytes(self.valid_photo.read_bytes())
        catalog = json.loads(self.catalog.read_text())
        catalog["properties"][1]["photos"][0]["path"] = independent.name
        self.catalog.write_text(json.dumps(catalog), encoding="utf-8")
        cache_dir = self.folder / ".photo-analysis"

        def wait_for_entries(expected):
            deadline = monotonic() + 3
            while monotonic() < deadline:
                entries = list(cache_dir.glob("*.json"))
                if len(entries) == expected:
                    return
                sleep(0.01)
            self.fail(f"Expected {expected} prepared entries, found {len(entries)}")

        with (
            patch("api.app.main.DEFAULT_CATALOG_PATH", self.catalog),
            patch("api.app.main.PHOTO_REFRESH_INTERVAL_SECONDS", 0.01),
            TestClient(app) as client,
        ):
            wait_for_entries(2)
            image = Image.new("RGB", (16, 16), "black")
            image.paste("white", (0, 0, 4, 16))
            changed = self.folder / "changed.jpg"
            image.save(changed)
            changed.replace(self.valid_photo)
            wait_for_entries(3)

            catalog["properties"][0]["photos"].append({**self.photo, "id": "new-photo", "path": independent.name})
            updated_catalog = self.folder / "properties-next.json"
            updated_catalog.write_text(json.dumps(catalog), encoding="utf-8")
            updated_catalog.replace(self.catalog)
            wait_for_entries(4)
            response = client.get("/properties")
            self.assertEqual(response.status_code, 200)
            self.assertEqual([photo["id"] for photo in response.json()[0]["photos"]], ["front", "new-photo"])

        self.assertEqual(self.invoke.await_count, 4)

    async def test_corrupt_cache_is_replaced_with_valid_observations(self):
        self.write_catalog([self.photo])
        first = await analysis.analyze_property_photos("a", self.catalog)
        [path] = (self.folder / ".photo-analysis").glob("*.json")
        path.write_text("{", encoding="utf-8")
        self.invoke.reset_mock()

        with self.assertLogs(analysis.__name__, level="WARNING"):
            retried = await analysis.analyze_property_photos("a", self.catalog)
        self.invoke.assert_awaited_once()
        self.assertEqual(retried, first)
        self.assertEqual(analysis.PhotoCacheEntry.model_validate_json(path.read_bytes()).analysis, first.photos[0])

    async def test_rejects_a_photo_reference_in_model_output(self):
        self.write_catalog([self.photo])
        self.invoke.return_value["observations"] = [
            {"element": "degrau", "location": None, "photo_id": "other-property"},
        ]

        result = await analysis.analyze_property_photos("a", self.catalog)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.photos[0].error, "model_error")
        self.assertEqual(result.photos[0].observations, [])

    async def test_not_observed_is_scoped_to_the_visible_landing(self):
        self.write_catalog([self.photo])
        self.coverage.return_value = {
            "calcada": "out_of_frame", "portao": "out_of_frame", "trajeto": "out_of_frame",
            "patamar": "partial", "porta_entrada": "visible",
        }
        self.invoke.return_value = {"observations": []}

        [photo] = (await analysis.analyze_property_photos("a", self.catalog)).photos

        self.assertEqual(photo.photo_id, "front")
        self.assertEqual(photo.observations, [])
        self.assertEqual(photo.coverage.framing, "partial")
        self.assertIn("calcada", photo.coverage.unverified_parts)
        self.assertIn("trajeto", photo.coverage.unverified_parts)
        self.assertIn("route_continuity", photo.to_confirm)
        self.assertEqual([item.state for item in photo.assessments], ["not_observed", "not_observed"])

    async def test_indeterminate_image_cannot_assert_absence(self):
        self.write_catalog([self.photo])
        self.coverage.return_value = dict.fromkeys(self.coverage.return_value, "indeterminate")
        self.invoke.return_value = {"observations": []}

        [photo] = (await analysis.analyze_property_photos("a", self.catalog)).photos

        self.assertEqual(photo.status, "analyzed")
        self.assertEqual(photo.coverage.framing, "indeterminate")
        self.assertEqual([item.state for item in photo.assessments], ["not_assessable", "not_assessable"])

    async def test_featureless_image_has_no_visual_evidence_without_calling_the_model(self):
        Image.new("RGB", (16, 16), "black").save(self.valid_photo)
        self.write_catalog([self.photo])

        [photo] = (await analysis.analyze_property_photos("a", self.catalog)).photos

        self.assertEqual(photo.photo_id, "front")
        self.assertEqual(photo.coverage.framing, "indeterminate")
        self.assertEqual([item.state for item in photo.assessments], ["not_assessable", "not_assessable"])
        self.assertEqual(photo.observations, [])
        self.load_model.assert_not_called()

    async def test_does_not_assign_an_observation_to_a_location_outside_the_frame(self):
        self.write_catalog([self.photo])
        self.coverage.return_value["calcada"] = "out_of_frame"

        [photo] = (await analysis.analyze_property_photos("a", self.catalog)).photos

        self.assertEqual(photo.observations[0].photo_id, "front")
        self.assertIsNone(photo.observations[0].location)

    async def test_ramp_leaves_measurements_and_continuity_to_confirm(self):
        self.write_catalog([self.photo])
        self.invoke.return_value["observations"] = [{"element": "rampa", "location": "trajeto"}]

        [photo] = (await analysis.analyze_property_photos("a", self.catalog)).photos

        self.assertEqual(photo.observations[0].element, "rampa")
        self.assertEqual(photo.observations[0].model_dump(), {
            "element": "rampa", "location": "trajeto", "photo_id": "front",
        })
        self.assertTrue({"ramp_width", "ramp_slope", "ramp_continuity"} <= set(photo.to_confirm))

    async def test_rejects_model_generated_measurements(self):
        self.write_catalog([self.photo])
        self.invoke.return_value["observations"][0]["inclination"] = 8

        [photo] = (await analysis.analyze_property_photos("a", self.catalog)).photos

        self.assertEqual(photo.error, "model_error")
        self.assertEqual(photo.observations, [])
        self.assertNotIn("inclination", photo.detail)
