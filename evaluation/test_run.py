from copy import deepcopy
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from api.app.comparison.schemas import ComparisonCriteria
from api.app.documents.extraction import CANDIDATE_PROMPT_VERSION
from api.app.documents.ingestion import prepare_chunks
from api.app.documents.schemas import CandidateExtraction, CandidateObservation, ModelExtraction, Observation

from .run import MODES, catalog, check_cited_quotes, compare_mode, score, score_mode, select_property, summarize
from .validate import read_json


class TestEvaluation(IsolatedAsyncioTestCase):
    async def test_candidate_attribution_scores_both_modes(self):
        case_id = "AM-08"
        case = next(case for case in read_json("cases.json") if case["id"] == case_id)
        [entry] = case["inputs"]
        prop, directory = catalog()[entry["propertyId"]]
        item = select_property(prop, entry["sourceIds"])
        pages = [page for doc in item.documents for page in prepare_chunks(item.id, doc, directory, splitter=None)]
        answers = {row["criterion"]: row for row in read_json("expected.json")[case_id][item.id]}
        criteria = ComparisonCriteria.model_validate(case["criteria"])

        async def context(_, criterion):
            self.assertEqual(criterion, "largura")
            return pages

        class ControlledChain:
            async def ainvoke(_, payload):
                self.assertIn('"candidate_id"', payload["sources"])
                observations = [
                    CandidateObservation(
                        criterion="largura", location="Porta de entrada", scope="entrada", value=value,
                        unit="m", candidate_id=f"pdf:{item.id}-{document}:2:1", quote=quote,
                    )
                    for document, value, quote in (
                        ("memorial", 0.85, "Vão livre de passagem previsto em projeto: 85 cm"),
                        ("vistoria", 0.78, "Vão livre de passagem medido na vistoria: 78 cm"),
                    )
                ]
                observations.append(observations[0].model_copy(update={
                    "candidate_id": f"pdf:{item.id}-memorial:1:1",
                }))
                parsed = CandidateExtraction(observations=observations)
                return {
                    "raw": SimpleNamespace(content=parsed.model_dump_json(),
                                           usage_metadata={"input_tokens": 900, "output_tokens": 100,
                                                           "total_tokens": 1000},
                                           response_metadata={"done_reason": "stop"}),
                    "parsing_error": None, "parsed": parsed,
                }

        modes = {}
        for name in MODES:
            result = await compare_mode(case_id, item, criteria, context, [], [], SimpleNamespace(num_ctx=8192),
                                        ControlledChain(), prompt_version=CANDIDATE_PROMPT_VERSION)
            modes[name] = score_mode(result, answers)
            self.assertEqual([row["diagnosis"] for row in modes[name]["rows"]], ["correct"])
            trace = modes[name]["model"]["attribution"]
            self.assertEqual([a["outcome"] for a in trace], ["accepted", "accepted", "quote_not_in_candidate"])
            self.assertEqual([a["resolvedSource"]["page"] for a in trace], [2, 2, 1])
        summaries = summarize([{"properties": [{"modes": modes}]}])
        self.assertEqual(summaries["paired"]["coverage"]["overall"], [1, 1])

    def test_distractor_on_expected_page_is_not_evidence_of_missing_measurement(self):
        source = "pdf:jatoba-vistoria:1:1"
        row = {
            "criterion": "largura", "diagnosis": "correct", "checks": {},
            "actual": {"referenceIds": [source]},
            "observations": [{"source_id": source, "quote": "Vão livre medido com a folha aberta: 95 cm."}],
        }
        cases = [{"id": "AM-12", "properties": [{
            "propertyId": "edificio-jatoba", "modes": {"direct": {"rows": [row]}},
        }]}]
        check_cited_quotes(cases)
        self.assertEqual(row["diagnosis"], "extraction")
        self.assertFalse(row["checks"]["evidenceQuote"])
        row["observations"][0]["quote"] = "A largura da porta de entrada não foi medida."
        row["diagnosis"] = "correct"
        check_cited_quotes(cases)
        self.assertTrue(row["checks"]["evidenceQuote"])
        self.assertEqual(row["diagnosis"], "correct")

    async def test_visual_case_does_not_submit_an_empty_text_prompt(self):
        prop, _ = catalog()["residencial-oliveira"]
        item = select_property(prop, ["residencial-oliveira-foto-porta"])

        async def context(*_):
            self.fail("No PDFs were selected")

        class UnusedChain:
            async def ainvoke(_, payload):
                self.fail("No textual sources were selected")

        result, candidates, trace = await compare_mode(
            "AM-15", item, ComparisonCriteria(stepFree=True), context, [], [],
            SimpleNamespace(num_ctx=8192), UnusedChain(),
        )
        self.assertFalse(candidates)
        self.assertFalse(trace)
        self.assertFalse(result.issues)
        self.assertEqual(result.evidence.textSearches[0].extraction, "no_results")

    async def test_scoring_checks_measurement_provenance_and_paired_coverage(self):
        property_id = "residencial-oliveira"
        case = next(case for case in read_json("cases.json") if case["id"] == "AM-08")
        expected = read_json("expected.json")["AM-08"][property_id][0]
        prop, directory = catalog()[property_id]
        item = select_property(prop, case["inputs"][0]["sourceIds"])
        pages = [
            page for doc in item.documents
            for page in prepare_chunks(item.id, doc, directory, splitter=None)
        ]

        async def direct(_, criterion):
            self.assertEqual(criterion, "largura")
            return pages

        class ControlledChain:
            async def ainvoke(_, payload):
                self.assertEqual(payload["criteria"], "largura")
                self.assertNotIn("listing:", payload["sources"])
                self.assertNotIn("80 cm", payload["sources"])
                observations = [
                    Observation(
                        criterion="largura", location="Porta de entrada", scope="entrada",
                        value=value, unit="cm", nature=nature,
                        source_id=f"pdf:{property_id}-{document}:2:1", quote=quote,
                    )
                    for value, nature, document, quote in (
                        (85, "especificacao_projeto", "memorial",
                         "Vão livre de passagem previsto em projeto: 85 cm"),
                        (78, "observacao_vistoria", "vistoria",
                         "Vão livre de passagem medido na vistoria: 78 cm"),
                    )
                ]
                observations.append(observations[0].model_copy(update={"scope": "outra_porta"}))
                parsed = ModelExtraction(observations=observations)
                return {
                    "raw": SimpleNamespace(
                        content=parsed.model_dump_json(),
                        usage_metadata={"input_tokens": 900, "output_tokens": 100, "total_tokens": 1000},
                        response_metadata={"done_reason": "stop"},
                    ),
                    "parsing_error": None, "parsed": parsed,
                }

        result, candidates, trace = await compare_mode(
            "AM-08", item, ComparisonCriteria.model_validate(case["criteria"]), direct, [], [],
            SimpleNamespace(num_ctx=8192), ControlledChain(),
        )
        self.assertTrue(trace["jsonValid"])
        self.assertTrue(trace["schemaValid"])
        self.assertEqual([item["scope"] for item in trace["discardedObservations"]], ["outra_porta"])
        args = (result.results[0], result.evidence)
        row = score(*args, expected, candidates["largura"], result.issues, trace)
        self.assertEqual(row["diagnosis"], "correct")
        self.assertEqual(row["actual"]["status"], "nao_atende")

        wrong_values = deepcopy(expected)
        measures = wrong_values["measurements"]
        measures[0]["value"], measures[1]["value"] = measures[1]["value"], measures[0]["value"]
        wrong = score(*args, wrong_values, candidates["largura"], result.issues, trace)
        self.assertTrue(wrong["checks"]["references"])
        self.assertFalse(wrong["checks"]["measurements"])

        failed = {**row, "diagnosis": "execution"}
        summaries = summarize([{"properties": [{"modes": {
            "rag": {"rows": [failed]}, "direct": {"rows": [row]},
        }}]}])
        self.assertEqual(summaries["direct"]["direct"]["overall"]["correct"], 1)
        self.assertEqual(summaries["rag"]["rag"]["overall"]["technicalFailures"], 1)
        self.assertEqual(summaries["paired"]["coverage"]["overall"], [0, 1])
