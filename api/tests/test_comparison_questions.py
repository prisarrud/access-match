import json
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda

from api.app.comparison.questions import ModelQuestions
from api.app.comparison.schemas import ComparisonEvidence, PropertyEvidence
from api.app.comparison.store import ComparisonStore
from api.app.documents.extraction import EvidenceSource
from api.app.main import app
from api.app.photos.analysis import PhotoAnalysis, PhotoObservation, VisibleParts, summarize_photo


class ComparisonQuestionsTests(TestCase):
    def setUp(self):
        self.client = self.enterContext(TestClient(app))
        self.ids = ["edificio-ipe", "residencial-oliveira"]
        partial_photo = summarize_photo(
            "partial", "property-b/porta-entrada.jpg",
            VisibleParts(
                calcada="out_of_frame", portao="out_of_frame", trajeto="out_of_frame",
                patamar="visible", porta_entrada="visible",
            ), [],
        )
        self.properties = [
            PropertyEvidence(propertyId=self.ids[0], title="Ipê", evidence=ComparisonEvidence(
                textSources=[EvidenceSource(
                    source_id="listing:ipe", property_id=self.ids[0], nature="declaracao_anuncio",
                    text="A entrada do prédio é sem degraus. Texto do anúncio que não precisa ir ao modelo.",
                )],
                visual=[PhotoAnalysis(
                    photo_id="front", source_path="property-a/entrada-frontal.jpg", status="analyzed",
                    observations=[PhotoObservation(photo_id="front", element="degrau", location="patamar")],
                )],
            ), issues=[]),
            PropertyEvidence(propertyId=self.ids[1], title="Oliveira", evidence=ComparisonEvidence(
                visual=[partial_photo],
            ), issues=[]),
        ]
        self.comparison_id = app.state.comparisons.save(self.properties)

    def post(self, criteria, *, selected=0, comparison_id=None):
        return self.client.post(f"/comparisons/{comparison_id or self.comparison_id}/questions", json={
            "propertyIds": self.ids, "propertyId": self.ids[selected], "criteria": criteria,
        })

    def model(self, questions):
        prompts = []

        def respond(prompt):
            prompts.append(json.loads(prompt.messages[-1].content.split("\n", 1)[1]))
            return ModelQuestions(questions=[{"pending": pending, "question": text} for pending, text in questions])

        model = Mock()
        model.with_structured_output.return_value = RunnableLambda(respond)
        self.enterContext(patch("api.app.comparison.questions.load_extraction_model", return_value=model))
        return prompts

    def test_missing_width_uses_only_its_pending_without_reanalyzing(self):
        question = "Qual é a largura livre da porta de entrada, em centímetros, com a porta totalmente aberta?"
        prompts = self.model([
            ("alternate_access", "Há outra entrada sem degraus?"),
            ("current_entrance_width", question),
            ("current_entrance_width", question.upper()),
        ])
        with (
            patch("api.app.comparison.routes.collect_comparison_evidence") as collect,
            patch("api.app.comparison.service.retrieve_evidence") as retrieve,
            patch("api.app.comparison.service.analyze_property_photos") as visual,
        ):
            response = self.post({"minimumClearWidthCm": 80})
            for operation in (collect, retrieve, visual):
                operation.assert_not_called()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "propertyId": self.ids[0], "questions": [{"pending": "current_entrance_width", "question": question}],
        })
        self.assertEqual([item["pending"] for item in prompts[0]["pendencias"]], ["current_entrance_width"])
        self.assertNotIn("Texto do anúncio", json.dumps(prompts[0], ensure_ascii=False))

    def test_divergence_and_partial_photo_keep_the_selected_property_and_pending_ids(self):
        alternate = "Existe outro acesso sem degraus?"
        route = "O trajeto inteiro da calçada até a porta de entrada é sem degraus?"
        prompts = self.model([("alternate_access", alternate), ("route_continuity", alternate), ("route_continuity", route)])

        for index in (0, 1):
            with self.subTest(property_id=self.ids[index]):
                response = self.post({"stepFree": True}, selected=index)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["propertyId"], self.ids[index])
                self.assertEqual({item["pending"]: item["question"] for item in response.json()["questions"]}, {
                    "alternate_access": alternate, "route_continuity": route,
                })
        self.assertIn("da calçada até a porta", prompts[1]["trecho_nao_verificado"])

    def test_generation_error_leaves_the_active_comparison_available(self):
        self.model([("current_entrance_width", "A porta tem 80 cm.")])
        with self.assertLogs("api.app.comparison.routes", level="WARNING"):
            response = self.post({"minimumClearWidthCm": 80})
        self.assertEqual(response.status_code, 503)
        recalculated = self.client.post(f"/comparisons/{self.comparison_id}/recalculate", json={
            "propertyIds": self.ids, "criteria": {"stepFree": True},
        })
        self.assertEqual(recalculated.status_code, 200)
        self.assertTrue(recalculated.json()["properties"][0]["results"][0]["divergence"])

    def test_expired_or_unrelated_comparison_does_not_generate(self):
        with patch("api.app.comparison.questions.load_extraction_model") as model:
            clock = Mock(return_value=0)
            store = ComparisonStore(ttl_seconds=1, clock=clock)
            expired_id = store.save(self.properties)
            clock.return_value = 2
            app.state.comparisons = store
            self.assertEqual(self.post({"stepFree": True}, comparison_id=expired_id).status_code, 410)
            response = self.client.post(f"/comparisons/{self.comparison_id}/questions", json={
                "propertyIds": self.ids, "propertyId": "outro-imovel", "criteria": {"stepFree": True},
            })
            self.assertEqual(response.status_code, 422)
            model.assert_not_called()
