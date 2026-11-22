from unittest import TestCase
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from api.app.comparison.rules import compare_ramp, compare_steps, compare_width
from api.app.comparison.schemas import ComparisonEvidence, PropertyEvidence, TextSearch
from api.app.comparison.store import ComparisonStore
from api.app.documents.extraction import EvidenceSource, ExtractionError, ExtractionResult, GroundedObservation
from api.app.main import app
from api.app.photos.analysis import PhotoAnalysis, PhotoObservation, PropertyPhotoAnalysis

PROPERTY_B = "residencial-oliveira"
PROPERTY_IDS = ["edificio-ipe", PROPERTY_B]


def measurement(source_id, document_type, value, unit="cm", scope="entrada"):
    nature = "observacao_vistoria" if document_type == "vistoria" else "especificacao_projeto"
    quote = f"Vão livre de {value} {unit}."
    source = EvidenceSource(
        source_id=source_id, property_id=PROPERTY_B, nature=nature,
        document_id=source_id, document_type=document_type, page=2, text=quote,
    )
    return GroundedObservation(
        criterion="largura", location="Porta de entrada", scope=scope, value=value,
        unit=unit, nature=nature, source_id=source_id, quote=quote, source=source,
    )


class ComparisonRulesTests(TestCase):
    def test_prefers_inspection_and_keeps_project_measurement(self):
        evidence = ComparisonEvidence(textual=[
            measurement("vistoria", "vistoria", 78),
            measurement("memorial", "memorial", 85),
            measurement("depósito", "vistoria", 90, scope="outra_porta"),
            measurement("serviço", "vistoria", 98).model_copy(update={"location": "Porta de serviço"}),
        ])
        result = compare_width(80, evidence)
        self.assertEqual(result.status, "nao_atende")
        self.assertIn("78 cm", result.justification)
        self.assertIn("85 cm", result.justification)
        self.assertEqual(result.referenceIds, ["vistoria", "memorial"])

    def test_exact_minimum_meets_after_converting_units(self):
        for value, unit in [(0.8, "m"), (800, "mm")]:
            with self.subTest(unit=unit):
                evidence = ComparisonEvidence(textual=[measurement("vistoria", "vistoria", value, unit)])
                self.assertEqual(compare_width(80, evidence).status, "atende")

    def test_project_only_and_other_door_only_require_confirmation(self):
        result = compare_width(80, ComparisonEvidence(textual=[measurement("memorial", "memorial", 85)]))
        self.assertEqual(result.status, "a_confirmar")
        self.assertIn("85 cm", result.justification)
        self.assertEqual(result.toConfirm, ["current_entrance_width"])
        result = compare_width(80, ComparisonEvidence(textual=[
            measurement("depósito", "vistoria", 90, scope="outra_porta"),
        ]))
        self.assertEqual(result.status, "a_confirmar")
        self.assertEqual(result.referenceIds, [])

    def test_distinguishes_missing_measurements_from_missing_pdf_passages(self):
        for retrieval, expected in (
            ("no_documents", "é preciso medir o vão livre"),
            ("no_results", "A busca nos PDFs não retornou trechos"),
        ):
            with self.subTest(retrieval=retrieval):
                evidence = ComparisonEvidence(textSearches=[
                    TextSearch(criterion="largura", retrieval=retrieval, extraction="no_results"),
                ])
                result = compare_width(50, evidence)
                self.assertEqual(result.status, "a_confirmar")
                self.assertIn(expected, result.justification)
                self.assertIn("50 cm", result.justification)

    def test_listed_step_free_access_and_photographed_step_conflict(self):
        evidence = ComparisonEvidence(
            textSources=[EvidenceSource(
                source_id="listing:a", property_id="a", nature="declaracao_anuncio",
                text="A entrada do prédio é sem degraus.",
            )],
            visual=[PhotoAnalysis(photo_id="front", source_path="front.jpg", status="analyzed", observations=[
                PhotoObservation(photo_id="front", element="degrau", location="patamar"),
            ])],
        )
        result = compare_steps(evidence)
        self.assertEqual(result.status, "nao_atende")
        self.assertTrue(result.divergence)
        self.assertIn("alternate_access", result.toConfirm)
        self.assertEqual(set(result.referenceIds), {"listing:a", "front"})

    def test_local_ramp_presence_and_local_absence_do_not_confirm_the_whole_route(self):
        evidence = ComparisonEvidence(visual=[
            PhotoAnalysis(photo_id="door", source_path="door.jpg", status="analyzed", assessments=[
                {"element": "degrau", "state": "not_observed"},
                {"element": "rampa", "state": "not_observed"},
            ]),
        ])
        for result in (compare_steps(evidence), compare_ramp(evidence)):
            self.assertEqual(result.status, "a_confirmar")
            self.assertIn("route_continuity", result.toConfirm)
            self.assertEqual(result.referenceIds, ["door"])

        evidence.visual[0].observations = [PhotoObservation(
            photo_id="door", element="rampa", location="trajeto",
        )]
        result = compare_ramp(evidence)
        self.assertEqual(result.status, "atende")
        self.assertIn("route_continuity", result.toConfirm)
        self.assertIn("ramp_continuity", result.toConfirm)


class ComparisonEndpointTests(TestCase):
    def setUp(self):
        self.client = self.enterContext(TestClient(app))

    def test_rejects_invalid_requests_before_analysis(self):
        valid_criteria = {"stepFree": True}
        cases = [
            ([PROPERTY_B], valid_criteria, 422),
            ([PROPERTY_B, PROPERTY_B], valid_criteria, 422),
            ([PROPERTY_B, "unknown"], valid_criteria, 404),
            (PROPERTY_IDS, {}, 422),
            (PROPERTY_IDS, {"minimumClearWidthCm": 0}, 422),
            (PROPERTY_IDS, {"minimumClearWidthCm": -80}, 422),
            (PROPERTY_IDS, {"minimumClearWidthCm": "80"}, 422),
        ]
        with patch("api.app.comparison.routes.collect_comparison_evidence") as compare:
            for ids, criteria, status in cases:
                with self.subTest(ids=ids, criteria=criteria):
                    result = self.client.post("/comparisons", json={"propertyIds": ids, "criteria": criteria})
                    self.assertEqual(result.status_code, status)
            compare.assert_not_called()

    def test_preserves_available_sources_when_retrieval_and_model_calls_fail(self):
        async def visual(property_id):
            return PropertyPhotoAnalysis(property_id=property_id, status="partial", photos=[
                PhotoAnalysis(photo_id=f"{property_id}-front", source_path="front.jpg", status="analyzed",
                              observations=[PhotoObservation(
                                  photo_id=f"{property_id}-front", element="degrau", location="patamar",
                              )]),
                PhotoAnalysis(photo_id=f"{property_id}-side", source_path="side.jpg", status="pending",
                              error="model_error"),
            ])

        with (
            patch("api.app.comparison.service.retrieve_evidence", new_callable=AsyncMock,
                  side_effect=ConnectionError("Database offline")),
            patch("api.app.comparison.service.extract_evidence", new_callable=AsyncMock,
                  side_effect=ExtractionError("Invalid model output")),
            patch("api.app.comparison.service.analyze_property_photos", side_effect=visual),
            self.assertLogs("api.app.comparison.service", level="WARNING"),
        ):
            response = self.client.post("/comparisons", json={
                "propertyIds": PROPERTY_IDS, "criteria": {"stepFree": True, "minimumClearWidthCm": 80},
            })

        self.assertEqual(response.status_code, 200)
        first, second = response.json()["properties"]
        self.assertTrue(first["results"][0]["divergence"])
        self.assertEqual(second["results"][1]["status"], "a_confirmar")
        self.assertIn("Execute uma nova análise", second["results"][1]["justification"])
        self.assertIn("residencial-oliveira-front", second["results"][0]["referenceIds"])
        self.assertEqual(second["evidence"]["textSources"][0]["source_id"], f"listing:{PROPERTY_B}")
        self.assertEqual({(issue["stage"], issue["kind"]) for issue in second["issues"]}, {
            ("retrieval", "infrastructure"), ("extraction", "analysis"), ("visual", "analysis"),
        })

    def test_nonfinite_width_returns_a_validation_error(self):
        for value in ("1e999", "NaN", "-Infinity"):
            with self.subTest(value=value):
                response = self.client.post(
                    "/comparisons", headers={"content-type": "application/json"},
                    content='{"propertyIds":["edificio-ipe","residencial-oliveira"],'
                            '"criteria":{"minimumClearWidthCm":' + value + "}}",
                )
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["detail"][0]["loc"][-1], "minimumClearWidthCm")

    def test_preserves_a_document_measurement_when_all_visual_analysis_fails(self):
        async def extract(property_item, criterion, chunks):
            observations = (
                [measurement("vistoria", "vistoria", 78)]
                if property_item.id == PROPERTY_B and criterion == "largura" else []
            )
            return ExtractionResult(
                property_id=property_item.id, criterion=criterion,
                status="evidence_found" if observations else "insufficient_evidence",
                sources=[item.source for item in observations], observations=observations,
            )

        with (
            patch("api.app.comparison.service.retrieve_evidence", new_callable=AsyncMock, return_value=[]),
            patch("api.app.comparison.service.extract_evidence", side_effect=extract),
            patch("api.app.comparison.service.analyze_property_photos", side_effect=ConnectionError("Offline")),
            self.assertLogs("api.app.comparison.service", level="WARNING"),
        ):
            response = self.client.post("/comparisons", json={
                "propertyIds": PROPERTY_IDS, "criteria": {"ramp": True, "minimumClearWidthCm": 80},
            })

        self.assertEqual(response.status_code, 200)
        second = response.json()["properties"][1]
        self.assertEqual(second["results"][1]["status"], "nao_atende")
        self.assertEqual(second["results"][1]["referenceIds"], ["vistoria"])
        self.assertEqual(second["evidence"]["textual"][0]["source"]["page"], 2)
        self.assertEqual(second["issues"][0]["kind"], "infrastructure")

    def test_recalculation_uses_all_collected_evidence_without_model_calls(self):
        async def retrieve(property_id, criterion):
            return [Document(page_content="Vão livre medido de 78 cm.")] if criterion == "largura" else []

        async def extract(property_item, criterion, chunks):
            observations = (
                [measurement("vistoria", "vistoria", 78)]
                if property_item.id == PROPERTY_B and criterion == "largura" else []
            )
            return ExtractionResult(
                property_id=property_item.id, criterion=criterion,
                status="evidence_found" if observations else "insufficient_evidence",
                sources=[item.source for item in observations], observations=observations,
            )

        async def visual(property_id):
            photo_id = f"{property_id}-photo"
            return PropertyPhotoAnalysis(property_id=property_id, status="complete", photos=[
                PhotoAnalysis(photo_id=photo_id, source_path="front.jpg", status="analyzed", observations=[
                    PhotoObservation(photo_id=photo_id, element="rampa", location="patamar"),
                ]),
            ])

        with (
            patch("api.app.comparison.service.retrieve_evidence", side_effect=retrieve) as retrieval,
            patch("api.app.comparison.service.extract_evidence", side_effect=extract) as extraction,
            patch("api.app.comparison.service.analyze_property_photos", side_effect=visual) as photos,
        ):
            original = self.client.post("/comparisons", json={
                "propertyIds": PROPERTY_IDS, "criteria": {"minimumClearWidthCm": 50},
            })
            self.assertEqual(original.status_code, 200)
            comparison = original.json()
            first, second = comparison["properties"]
            self.assertEqual(first["results"][0]["status"], "a_confirmar")
            self.assertEqual(second["results"][0]["status"], "atende")
            self.assertEqual(retrieval.await_count, 3)
            self.assertEqual(extraction.await_count, 6)
            self.assertEqual(photos.await_count, 2)
            self.assertEqual({item["retrieval"] for item in first["evidence"]["textSearches"]}, {"no_documents"})
            self.assertEqual(
                {item["criterion"]: (item["retrieval"], item["extraction"])
                 for item in second["evidence"]["textSearches"]},
                {"largura": ("found", "found"), "degraus": ("no_results", "no_results"),
                 "rampas": ("no_results", "no_results")},
            )

            for integration in (retrieval, extraction, photos):
                integration.reset_mock()
                integration.side_effect = AssertionError("Recalculation must not call analysis integrations")

            path = f'/comparisons/{comparison["comparisonId"]}/recalculate'
            updated = self.client.post(path, json={
                "propertyIds": PROPERTY_IDS, "criteria": {"minimumClearWidthCm": 80, "ramp": True},
            })
            self.assertEqual(updated.status_code, 200)
            self.assertEqual(updated.json()["comparisonId"], comparison["comparisonId"])
            after = updated.json()["properties"][1]
            self.assertEqual({item["criterion"]: item["status"] for item in after["results"]}, {
                "largura": "nao_atende", "rampas": "atende",
            })
            self.assertEqual(after["results"][1]["referenceIds"], second["results"][0]["referenceIds"])
            self.assertEqual(after["evidence"], second["evidence"])

            invalid = self.client.post(path, json={"propertyIds": PROPERTY_IDS, "criteria": {}})
            self.assertEqual(invalid.status_code, 422)
            wrong_pair = self.client.post(path, json={
                "propertyIds": [PROPERTY_IDS[0], "unknown"], "criteria": {"ramp": True},
            })
            self.assertEqual(wrong_pair.status_code, 410)
            for integration in (retrieval, extraction, photos):
                integration.assert_not_awaited()

    def test_expired_or_unavailable_reference_does_not_start_new_analysis(self):
        now = [0.0]
        app.state.comparisons = ComparisonStore(ttl_seconds=5, clock=lambda: now[0])
        reference = app.state.comparisons.save([
            PropertyEvidence(propertyId=property_id, title=property_id, evidence=ComparisonEvidence(), issues=[])
            for property_id in PROPERTY_IDS
        ])
        request = {"propertyIds": PROPERTY_IDS, "criteria": {"ramp": True}}
        with patch("api.app.comparison.routes.collect_comparison_evidence") as collect:
            self.assertEqual(self.client.post(f"/comparisons/{reference}/recalculate", json=request).status_code, 200)
            now[0] = 5.0
            for comparison_id in (reference, "unavailable"):
                response = self.client.post(f"/comparisons/{comparison_id}/recalculate", json=request)
                self.assertEqual(response.status_code, 410)
                self.assertIn("expirou", response.json()["detail"])
            collect.assert_not_called()
