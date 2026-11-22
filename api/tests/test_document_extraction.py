import asyncio
import json
from unittest import TestCase
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from api.app.comparison.rules import compare_width
from api.app.comparison.schemas import ComparisonEvidence
from api.app.documents.extraction import (
    CANDIDATE_PROMPT_VERSION,
    ExtractionError,
    ModelExtraction,
    Observation,
    extract_evidence_batch,
    prepare_sources,
    validate_observations,
)
from api.app.documents.schemas import CandidateExtraction, CandidateObservation, EvidenceQuoteNotFound, UnknownEvidenceSource
from api.app.properties.catalog import load_catalog

class ExtractionValidationTests(TestCase):
    def setUp(self):
        self.property = next(
            item for item in load_catalog().properties if item.id == "residencial-oliveira"
        )
        self.entrance = "3.1 Porta de entrada do hall — PE-01\nVão livre medido de 78 cm."
        self.other_door = "3.2 Porta do depósito técnico — PS-03\nVão livre medido de 90 cm."
        document = self.property.documents[1]
        self.chunk = Document(page_content=f"{self.entrance}\n{self.other_door}", metadata={
            "property_id": self.property.id,
            "document_id": document.id,
            "document_type": document.type,
            "document_date": document.date,
            "source_path": document.path,
            "page": 2,
            "chunk_index": 1,
        })
        self.sources = prepare_sources(self.property, [self.chunk])
        self.observation = Observation(
            criterion="largura", location="Porta de entrada do hall", scope="entrada",
            value=78, unit="cm", nature="observacao_vistoria",
            source_id=self.sources[1].source_id, quote="Vão livre medido de 78 cm.",
        )

    def validate(self, item):
        return validate_observations(ModelExtraction(observations=[item]), "largura", self.sources)

    def test_resolves_document_and_page_from_the_retrieved_metadata(self):
        [result] = self.validate(self.observation)
        self.assertEqual(result.value, 78)
        self.assertEqual(result.source.document_id, self.chunk.metadata["document_id"])
        self.assertEqual(result.source.page, 2)
        self.assertEqual(result.source.source_path, self.chunk.metadata["source_path"])

    def test_candidate_anchors_page_and_measurement_to_the_selected_source(self):
        document = self.property.documents[0]
        memorial_id = f"pdf:{document.id}:2:1"
        wrong_page_id = f"pdf:{document.id}:1:1"
        project = Document(
            page_content="Porta de entrada do hall. Vão livre previsto de 85 cm.",
            metadata=self.chunk.metadata | {"document_id": document.id, "document_type": document.type,
                                            "document_date": document.date, "source_path": document.path},
        )
        page_one = project.model_copy(update={"page_content": "Memorial descritivo",
                                              "metadata": project.metadata | {"page": 1}})
        measured = CandidateObservation(
            **self.observation.model_dump(exclude={"source_id", "nature"}),
            candidate_id=self.observation.source_id,
        )
        planned = measured.model_copy(update={
            "candidate_id": memorial_id, "value": 0.85, "unit": "m", "quote": "Vão livre previsto de 85 cm.",
        })
        sources = prepare_sources(self.property, [self.chunk, page_one, project])
        for candidate_id, error_type in (
            (wrong_page_id, EvidenceQuoteNotFound),
            ("pdf:unknown:2:1", UnknownEvidenceSource),
            ("listing:edificio-ipe", UnknownEvidenceSource),
        ):
            with self.subTest(candidate_id=candidate_id), self.assertRaises(error_type):
                validate_observations(
                    CandidateExtraction(observations=[planned.model_copy(update={"candidate_id": candidate_id})]),
                    "largura", sources,
                )
        other_door = measured.model_copy(update={"value": 90, "quote": "Vão livre medido de 90 cm."})
        other_door_without_value = other_door.model_copy(update={"value": None, "unit": None})

        async def respond(payload):
            candidates = json.loads(payload["sources"])
            ids = [candidate["candidate_id"] for candidate in candidates]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertNotIn("source_id", candidates[0])
            return CandidateExtraction(observations=[planned, measured, other_door, other_door_without_value])

        results = asyncio.run(extract_evidence_batch(
            self.property, {"largura": [self.chunk, page_one, project, project]},
            invoke=respond, prompt_version=CANDIDATE_PROMPT_VERSION,
        ))
        observations = results["largura"].observations
        self.assertEqual([(o.source_id, o.source.page, o.nature) for o in observations], [
            (memorial_id, 2, "especificacao_projeto"),
            (measured.candidate_id, 2, "observacao_vistoria"),
        ])
        result = compare_width(80, ComparisonEvidence(textual=observations))
        self.assertEqual(result.status, "nao_atende")
        self.assertEqual(result.referenceIds, [memorial_id, measured.candidate_id])
        self.assertIn("78 cm", result.justification)
        self.assertIn("85 cm", result.justification)

    def test_uses_catalog_nature_for_a_grounded_observation(self):
        [result] = self.validate(self.observation.model_copy(update={"nature": "declaracao_anuncio"}))
        self.assertEqual(result.nature, "observacao_vistoria")
        self.assertEqual(result.nature, result.source.nature)

    def test_ignores_other_criteria_without_losing_a_valid_observation(self):
        unrelated = self.observation.model_copy(update={"criterion": "rampas"})
        result = validate_observations(
            ModelExtraction(observations=[unrelated, self.observation]), "largura", self.sources,
        )
        self.assertEqual([item.value for item in result], [78])

    def test_door_width_cannot_be_reused_as_step_or_ramp_evidence(self):
        for criterion in ("degraus", "rampas"):
            with self.subTest(criterion=criterion):
                incorrectly_labeled = self.observation.model_copy(update={"criterion": criterion})
                result = validate_observations(
                    ModelExtraction(observations=[incorrectly_labeled]), criterion, self.sources,
                )
                self.assertEqual(result, [])

    def test_valid_step_claim_survives_irrelevant_width_quote(self):
        self.chunk.page_content += "\nO acesso da calçada à entrada não tem degraus."
        sources = prepare_sources(self.property, [self.chunk])
        irrelevant = self.observation.model_copy(update={"criterion": "degraus"})
        valid = irrelevant.model_copy(update={
            "quote": "O acesso da calçada à entrada não tem degraus.", "value": None, "unit": None,
        })
        result = validate_observations(ModelExtraction(observations=[irrelevant, valid]), "degraus", sources)
        self.assertEqual([item.quote for item in result], [valid.quote])

    def test_rejects_a_reference_the_model_was_not_sent(self):
        with self.assertRaisesRegex(ExtractionError, "Unknown evidence source"):
            self.validate(self.observation.model_copy(update={"source_id": "pdf:unknown:2:1"}))

    def test_rejects_retrieved_chunks_from_another_property(self):
        self.chunk.metadata["property_id"] = "edificio-ipe"
        with self.assertRaisesRegex(ExtractionError, "does not match a document"):
            prepare_sources(self.property, [self.chunk])

    def test_cannot_relabel_the_other_door_as_the_entrance(self):
        alternate = self.observation.model_copy(update={
            "value": 90, "quote": self.chunk.page_content,
        })
        self.assertEqual(self.validate(alternate), [])
        paraphrased = alternate.model_copy(update={"quote": "A entrada mede 90 cm."})
        self.assertEqual(self.validate(paraphrased), [])

    def test_accepts_equivalent_lengths_in_both_directions(self):
        model_value = self.observation.model_copy(update={"value": 0.78, "unit": "m"})
        [result] = self.validate(model_value)
        self.assertEqual((result.value, result.unit, result.quote, result.source.page),
                         (0.78, "m", self.observation.quote, 2))
        for separator in (",", "."):
            with self.subTest(separator=separator):
                quote = f"Vão livre medido de 0{separator}78 m."
                source = self.sources[1].model_copy(update={"text": self.entrance.replace(self.observation.quote, quote)})
                item = self.observation.model_copy(update={"quote": quote})
                [result] = validate_observations(ModelExtraction(observations=[item]), "largura", [source])
                self.assertEqual((result.value, result.unit, result.quote), (78, "cm", quote))

    def test_rejects_width_with_a_different_value_or_missing_unit(self):
        with self.assertRaisesRegex(ExtractionError, "measurement was not found"):
            self.validate(self.observation.model_copy(update={"value": 0.85, "unit": "m"}))
        quote = "Vão livre medido de 78."
        source = self.sources[1].model_copy(update={"text": self.entrance.replace(self.observation.quote, quote)})
        item = self.observation.model_copy(update={"quote": quote})
        with self.assertRaisesRegex(ExtractionError, "measurement was not found"):
            validate_observations(ModelExtraction(observations=[item]), "largura", [source])

    def test_rejects_an_equivalent_width_on_the_wrong_page_or_door(self):
        wrong_page = self.chunk.model_copy(update={"metadata": self.chunk.metadata | {"page": 1},
                                                 "page_content": self.other_door})
        [_, first_page] = prepare_sources(self.property, [wrong_page])
        wrong = self.observation.model_copy(update={"source_id": first_page.source_id, "value": 0.78, "unit": "m"})
        with self.assertRaisesRegex(ExtractionError, "quote was not found"):
            validate_observations(ModelExtraction(observations=[wrong]), "largura", [first_page])
        other_door = wrong.model_copy(update={"source_id": self.observation.source_id, "value": 0.9,
                                               "quote": "Vão livre medido de 90 cm."})
        self.assertEqual(self.validate(other_door), [])
        quote = "O valor de 78 cm corresponde à porta do depósito."
        source = self.sources[1].model_copy(update={"text": self.entrance.replace(self.observation.quote, quote)})
        item = self.observation.model_copy(update={"quote": quote})
        self.assertEqual(validate_observations(ModelExtraction(observations=[item]), "largura", [source]), [])

    def test_rejects_ambiguous_widths_in_a_single_quote(self):
        for text, quote in (("Vão livre de 78 cm ou 85 cm.", "78 cm"),
                            ("Vão livre de 75 a 78 cm.", "78 cm"),
                            ("Vão livre de 75 ou 78 cm.", "78 cm"),
                            ("Vão livre de 78 cm ou talvez 85 cm.", "Vão livre de 78 cm ou talvez 85 cm.")):
            with self.subTest(text=text):
                source = self.sources[1].model_copy(update={"text": self.entrance.replace(self.observation.quote, text)})
                item = self.observation.model_copy(update={"quote": quote})
                self.assertEqual(validate_observations(ModelExtraction(observations=[item]), "largura", [source]), [])

    def test_rejects_a_width_invented_for_a_qualitative_listing(self):
        invented = self.observation.model_copy(update={
            "source_id": self.sources[0].source_id, "nature": "declaracao_anuncio",
            "quote": "A entrada tem uma porta ampla.", "value": 80,
        })
        with self.assertRaisesRegex(ExtractionError, "measurement was not found"):
            self.validate(invented)

    def test_batches_shared_sources_and_validates_references_against_each_criterion(self):
        document = self.property.documents[0]
        project = Document(page_content="3.1 Porta de entrada do hall — PE-01\nVão livre previsto de 85 cm, medido no projeto.", metadata={
            **self.chunk.metadata, "document_id": document.id, "document_type": document.type,
            "document_date": document.date, "source_path": document.path,
        })
        project_id = f"pdf:{document.id}:2:1"
        project_observation = self.observation.model_copy(update={
            "value": 0.85, "unit": "m", "source_id": project_id, "quote": "Vão livre previsto de 85 cm.",
        })
        invalid_step = self.observation.model_copy(update={
            "criterion": "degraus", "source_id": project_id, "quote": "O acesso é sem degraus.",
            "value": None, "unit": None,
        })
        invalid_width = self.observation.model_copy(update={"source_id": "pdf:unknown:2:1"})
        prompts = []

        def respond(prompt):
            prompts.append(json.loads(prompt.messages[-1].content.split("Fontes (JSON):\n", 1)[1]))
            return ModelExtraction(observations=[self.observation, project_observation, invalid_width, invalid_step])

        with patch("api.app.documents.extraction.load_extraction_model") as load:
            load.return_value.with_structured_output.return_value = RunnableLambda(respond)
            result = asyncio.run(extract_evidence_batch(self.property, {
                "largura": [self.chunk, project, self.chunk], "degraus": [self.chunk], "rampas": [],
            }))

        load.assert_called_once()
        [sources] = prompts
        self.assertEqual(len(sources), 3)
        self.assertEqual({item["source_id"]: item["criteria"] for item in sources}, {
            self.sources[0].source_id: ["largura", "degraus", "rampas"],
            self.sources[1].source_id: ["largura", "degraus"],
            project_id: ["largura"],
        })
        self.assertEqual([(item.value, item.nature, item.source.page) for item in result["largura"].observations], [
            (78, "observacao_vistoria", 2), (0.85, "especificacao_projeto", 2),
        ])
        self.assertEqual(result["largura"].observations[1].quote, "Vão livre previsto de 85 cm")
        self.assertIsInstance(result["degraus"], ExtractionError)
        self.assertEqual(result["rampas"].status, "insufficient_evidence")

    def test_a_step_free_claim_is_not_qualitative_width_evidence(self):
        source = self.sources[0].model_copy(update={"text": "A entrada do prédio é sem degraus."})
        width = self.observation.model_copy(update={
            "source_id": source.source_id, "quote": source.text, "value": None, "unit": None,
        })
        self.assertEqual(validate_observations(ModelExtraction(observations=[width]), "largura", [source]), [])
