from unittest import TestCase

from langchain_core.documents import Document

from api.app.documents.extraction import (
    ExtractionError,
    ModelExtraction,
    Observation,
    prepare_sources,
    validate_observations,
)
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

    def test_rejects_a_width_invented_for_a_qualitative_listing(self):
        invented = self.observation.model_copy(update={
            "source_id": self.sources[0].source_id, "nature": "declaracao_anuncio",
            "quote": "A entrada tem uma porta ampla.", "value": 80,
        })
        with self.assertRaisesRegex(ExtractionError, "measurement was not found"):
            self.validate(invented)
