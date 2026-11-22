"""Run the frozen Stage 6.1 cases through AccessMatch's two context providers."""
import argparse
import asyncio
import json
import logging
import re
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from api.app.comparison.schemas import AnalysisIssue, ComparisonCriteria, PropertyEvidence
from api.app.comparison.service import EVIDENCE_CRITERIA, calculate_comparison, collect_text_evidence
from api.app.config import load_ollama_base_url
from api.app.documents.config import load_extraction_model, load_index_config
from api.app.documents.extraction import (
    CANDIDATE_PROMPT_VERSION, DEFAULT_PROMPT_VERSION, PROMPTS, extraction_chain, ground_observation,
    observation_source_id, prepare_sources,
)
from api.app.documents.ingestion import prepare_chunks
from api.app.documents.measurements import WIDTH_FACTORS, width_cm
from api.app.documents.retrieval import retrieve_property_context
from api.app.documents.schemas import EvidenceQuoteNotFound, ExtractionError, UnknownEvidenceSource
from api.app.photos.analysis import (
    PhotoCacheEntry, PhotoCacheKey, load_cached_photo, read_photo_bytes, vision_configuration,
)
from api.app.properties.catalog import load_catalog

from .validate import DIRECTORY, ROOT, read_json, validate

MODES = ("rag", "direct")
NUM_PREDICT = 768
# Llama 3.2 uses byte-level BPE. Reserve additional room for the Ollama chat template.
TEMPLATE_RESERVE = 256
CASE_VERSION = "6.1 (49803cabfd9f75066602ea6ca4b231160d8d714f)"
REQUIRED_QUOTES = {
    # The expected page also contains a measurement for a different door.
    ("AM-12", "edificio-jatoba", "largura"): "largura da porta de entrada não foi medida",
}


def catalog():
    return {
        item.id: (item, path.parent)
        for path in (ROOT / "data/demo/properties.json", DIRECTORY / "fixtures/properties.json")
        for item in load_catalog(path).properties
    }


def select_property(item, source_ids):
    return item.model_copy(update={
        "description": item.description if f"listing:{item.id}" in source_ids else "",
        "documents": [document for document in item.documents if document.id in source_ids],
        "photos": [photo for photo in item.photos if photo.id in source_ids],
    })


def load_visual(item, directory, snapshot, configuration):
    photos, issues = [], []
    for photo in item.photos:
        if photo.id not in snapshot:
            key = PhotoCacheKey(
                property_id=item.id, photo_id=photo.id,
                file_sha256=sha256(read_photo_bytes(directory, photo.path)).hexdigest(),
                configuration=configuration,
            )
            cached = load_cached_photo(key.path_in(directory), key)
            snapshot[photo.id] = PhotoCacheEntry(key=key, analysis=cached) if cached else None
        entry = snapshot[photo.id]
        if entry is None:
            issues.append(AnalysisIssue(
                stage="visual", kind="source_file", photoId=photo.id,
                message="Observação visual pré-processada indisponível.",
            ))
        else:
            photos.append(entry.analysis.model_copy(update={"source_path": photo.path, "detail": None}))
    return photos, issues


def source_ref(source):
    return (source.document_id or source.source_id, source.page)


def reference(ref):
    return (ref["sourceId"], ref.get("page"))


def json_ref(ref):
    return {"sourceId": ref[0], **({"page": ref[1]} if ref[1] is not None else {})}


def measurement(ref, nature, value, unit):
    return ref, nature, width_cm(value, unit)


def score(result, evidence, expected, candidates, issues, model_trace):
    criterion = result.criterion
    sources = {source.source_id: source for source in evidence.textSources}
    refs = {source_ref(sources[key]) if key in sources else (key, None) for key in result.referenceIds}
    expected_refs = {reference(ref) for ref in expected["references"]}
    optional_refs = {reference(ref) for ref in expected.get("optionalReferences", [])}
    observations = [item for item in evidence.textual if item.criterion == criterion]
    measured = [
        item for item in observations
        if item.unit in WIDTH_FACTORS and item.value is not None and criterion == "largura"
        and item.source_id in result.referenceIds
    ]
    expected_measures = {
        measurement(reference(item["reference"]), item["nature"], item["value"], item["unit"])
        for item in expected["measurements"]
    }
    actual_measures = {
        measurement(source_ref(item.source), item.nature, item.value, item.unit) for item in measured
    }
    checks = {
        "status": result.status == expected["status"],
        "references": expected_refs <= refs <= expected_refs | optional_refs,
        "measurements": actual_measures == expected_measures if expected_measures else True,
        "toConfirm": set(result.toConfirm) == set(expected["toConfirm"]),
        "divergence": result.divergence == expected["divergence"],
    }
    relevant_issues = [
        issue for issue in issues if issue.criterion == criterion
        or (issue.stage == "visual" and criterion in {"degraus", "rampas"})
    ]
    technical = any(
        issue.stage in {"retrieval", "visual"} or model_trace.get("technical")
        for issue in relevant_issues
    )
    candidate_refs = {source_ref(source) for source in candidates}
    missing = {ref for ref in expected_refs if ref[1] is not None} - candidate_refs
    missing_measures = []
    for item in expected["measurements"]:
        value = re.escape(str(item["value"])).replace(r"\.", "[.,]")
        pattern = rf"(?<![\w.,]){value}\s*{item['unit']}\b"
        if not any(
            source_ref(source) == reference(item["reference"]) and re.search(pattern, source.text)
            for source in candidates
        ):
            missing_measures.append(item)
    grounded = {source_ref(item.source) for item in observations}
    grounded_measures = {
        measurement(source_ref(item.source), item.nature, item.value, item.unit)
        for item in observations if criterion == "largura" and item.unit in WIDTH_FACTORS and item.value is not None
    }
    visual_refs = {(photo.photo_id, None) for photo in evidence.visual}
    listing_refs = {source_ref(source) for source in candidates if source.nature == "declaracao_anuncio"}
    if technical:
        diagnosis = "execution"
    elif all(checks.values()) and not relevant_issues:
        diagnosis = "correct"
    elif missing or missing_measures:
        diagnosis = "retrieval"
    elif (
        relevant_issues or expected_refs - grounded - visual_refs - listing_refs
        or expected_measures - grounded_measures
    ):
        diagnosis = "extraction"
    else:
        diagnosis = "review"
    return {
        "criterion": criterion, "diagnosis": diagnosis, "checks": checks,
        "actual": result.model_dump(mode="json") | {
            "references": [json_ref(ref) for ref in sorted(refs)],
            "measurements": [
                {"reference": json_ref(source_ref(item.source)), "value": item.value,
                 "unit": item.unit, "nature": item.nature, "quote": item.quote}
                for item in measured
            ],
        },
        "expected": expected,
        "pdfDependent": any(ref[1] is not None for ref in expected_refs),
        "missingPdfReferences": [json_ref(ref) for ref in sorted(missing)],
        "missingPdfMeasurements": missing_measures,
        "candidates": [
            json_ref(source_ref(source)) | {
                "id": source.source_id, "chunkIndex": source.chunk_index,
                "text": source.text,
            }
            for source in candidates
        ],
        "observations": [item.model_dump(mode="json", exclude={"source"}) for item in observations],
        "issues": [issue.model_dump(mode="json") for issue in relevant_issues],
    }


def totals(rows):
    result = Counter(row["diagnosis"] for row in rows)
    return {"correct": result["correct"], "completed": len(rows) - result["execution"],
            "technicalFailures": result["execution"], "planned": len(rows), "diagnoses": dict(result)}


def check_cited_quotes(cases):
    for case in cases:
        for prop in case["properties"]:
            for mode in prop["modes"].values():
                for row in mode["rows"]:
                    quote = REQUIRED_QUOTES.get((case["id"], prop["propertyId"], row["criterion"]))
                    if quote is None:
                        continue
                    match = any(
                        quote.casefold() in " ".join(item["quote"].split()).casefold()
                        and item["source_id"] in row["actual"]["referenceIds"]
                        for item in row["observations"]
                    )
                    row["checks"]["evidenceQuote"] = match
                    if not match and row["diagnosis"] == "correct":
                        row["diagnosis"] = "extraction"


def summarize(cases):
    pairs = [
        tuple(prop["modes"][mode]["rows"][i] for mode in MODES)
        for case in cases for prop in case["properties"]
        for i in range(len(prop["modes"]["rag"]["rows"]))
    ]
    summary = {"cases": len(cases)}
    for mode in (*MODES, "paired"):
        modes = MODES if mode == "paired" else (mode,)
        index = MODES.index(mode) if mode != "paired" else None

        def completed(pair):
            rows = pair if index is None else (pair[index],)
            return all(row["diagnosis"] != "execution" for row in rows)

        paired = [pair for pair in pairs if completed(pair)]
        summary[mode] = {
            "casesCompleted": sum(
                all(prop["modes"][name]["rows"][i]["diagnosis"] != "execution"
                    for prop in case["properties"] for name in modes
                    for i in range(len(prop["modes"][name]["rows"])))
                for case in cases
            ),
            "coverage": {"overall": [len(paired), len(pairs)],
                         "pdf": [sum(pair[0]["pdfDependent"] for pair in paired),
                                 sum(pair[0]["pdfDependent"] for pair in pairs)]},
            **{
                name: {
                    "overall": totals([pair[MODES.index(name)] for pair in (paired if index is None else pairs)]),
                    "pdf": totals([pair[MODES.index(name)] for pair in (paired if index is None else pairs)
                                   if pair[0]["pdfDependent"]]),
                } for name in modes
            },
        }
    return summary


def observation_key(observation, *, scope=None):
    # Grounding can repair the source nature and trim final punctuation.
    return (
        observation.criterion, observation_source_id(observation), scope or observation.scope,
        observation.location, observation.value, observation.unit,
        " ".join(observation.quote.split()).casefold().rstrip(".,;:!?"),
    )


async def compare_mode(
    case_id, item, criteria, provider, photos, visual_issues, model, chain,
    *, prompt_version=DEFAULT_PROMPT_VERSION,
):
    candidates = {}
    trace = {}
    submitted_observations = None
    submitted_criteria = {}

    async def context(property_item, criterion):
        try:
            chunks = await provider(property_item, criterion)
            candidates[criterion] = prepare_sources(property_item, chunks)
        except Exception:
            logging.exception("Falha de contexto em %s/%s/%s", case_id, item.id, criterion)
            raise
        return chunks

    async def invoke(payload):
        nonlocal submitted_observations
        messages = PROMPTS[prompt_version].format_messages(**payload)
        upper_bound = sum(len(message.content.encode("utf-8")) for message in messages) + TEMPLATE_RESERVE
        trace["inputByteBoundWithTemplate"] = upper_bound
        trace["contextLimit"] = model.num_ctx
        # Check the input on its own. Check the combined budget with actual
        # token counts below because the input byte bound overestimates tokens.
        if upper_bound >= model.num_ctx:
            trace["technical"] = "O limite conservador do contexto foi excedido. Nenhum texto foi truncado."
            raise ValueError(trace["technical"])
        try:
            response = await chain.ainvoke(payload)
        except Exception as exc:
            trace["technical"] = f"Falha de chamada ao Ollama ({type(exc).__name__})."
            logging.exception("Falha de extração em %s/%s", case_id, item.id)
            raise
        raw = response["raw"]
        usage = raw.usage_metadata or {}
        trace.update({"usage": usage, "doneReason": raw.response_metadata.get("done_reason")})
        trace["rawOutput"] = raw.content
        try:
            json.loads(raw.content)
        except (TypeError, ValueError):
            trace["jsonValid"] = False
        else:
            trace["jsonValid"] = True
        trace["schemaValid"] = (
            trace["jsonValid"] and response["parsing_error"] is None and response["parsed"] is not None
        )
        if response["parsing_error"] is not None:
            trace["parsingError"] = type(response["parsing_error"]).__name__
        if trace["doneReason"] == "length":
            trace["technical"] = "A geração atingiu o limite de saída."
            raise ValueError(trace["technical"])
        if not usage.get("input_tokens") or usage["total_tokens"] > model.num_ctx:
            trace["technical"] = "O Ollama não confirmou o uso esperado da janela de contexto."
            raise ValueError(trace["technical"])
        if response["parsing_error"] is not None:
            raise response["parsing_error"]
        submitted_observations = response["parsed"].observations
        if prompt_version == CANDIDATE_PROMPT_VERSION:
            submitted_criteria.update({source["candidate_id"]: source["criteria"]
                                       for source in json.loads(payload["sources"])})
        return response["parsed"]

    requested = tuple(criterion for criterion in EVIDENCE_CRITERIA if criterion in criteria.requested())
    evidence, issues = await collect_text_evidence(
        item, context, criteria=requested, invoke=invoke, prompt_version=prompt_version,
    )
    if submitted_observations is not None:
        accepted = Counter(map(observation_key, evidence.textual))
        listing_sources = prepare_sources(item, [])
        attribution = []
        discarded = []
        for observation in submitted_observations:
            source_id = observation_source_id(observation)
            sources = candidates.get(observation.criterion, listing_sources) if observation.criterion in requested else []
            sources_by_id = {source.source_id: source for source in sources}
            if (prompt_version == CANDIDATE_PROMPT_VERSION
                    and observation.criterion not in submitted_criteria.get(source_id, ())):
                sources_by_id.pop(source_id, None)
            source = sources_by_id.get(source_id)
            key = observation_key(observation)
            if not accepted[key] and observation.scope == "entrada":
                try:
                    grounded = ground_observation(observation, sources_by_id)
                except ExtractionError:
                    grounded = None
                if grounded is not None:
                    key = observation_key(observation, scope=grounded.scope)
            entry = {
                "criterion": observation.criterion, "candidateId": source_id, "quote": observation.quote,
                "resolvedSource": None if source is None else source.model_dump(
                    mode="json", include={"property_id", "document_id", "page", "chunk_index", "nature"},
                ),
            }
            if accepted[key]:
                accepted[key] -= 1
                entry["outcome"] = "accepted"
            else:
                reasons = []
                outcome = "extraction"
                try:
                    ground_observation(observation, sources_by_id, discard_reason=reasons)
                except ExtractionError as exc:
                    reasons.append(str(exc))
                    if isinstance(exc, UnknownEvidenceSource):
                        outcome = "invalid_candidate_id"
                    elif isinstance(exc, EvidenceQuoteNotFound):
                        outcome = "quote_not_in_candidate"
                reason = reasons[0] if reasons else "Duplicate observation or criterion not accepted in this batch."
                discarded.append(observation.model_dump(mode="json") | {"reason": reason})
                entry.update({"outcome": outcome, "reason": reason})
            attribution.append(entry)
        trace["discardedObservations"] = discarded
        if prompt_version == CANDIDATE_PROMPT_VERSION:
            trace["attribution"] = attribution
    evidence.visual = photos
    property_evidence = PropertyEvidence(
        propertyId=item.id, title=item.title, evidence=evidence, issues=[*issues, *visual_issues],
    )
    result = calculate_comparison(case_id, [property_evidence], criteria).properties[0]
    return result, candidates, trace


def score_mode(mode_result, answers):
    result, candidates, trace = mode_result
    return {
        "model": trace, "searches": [item.model_dump(mode="json") for item in result.evidence.textSearches],
        "rows": [
            score(item, result.evidence, answers[item.criterion], candidates.get(item.criterion, []),
                  result.issues, trace)
            for item in result.results
        ],
    }


async def run(visual_from, *, num_predict=NUM_PREDICT, case_ids=(), prompt_version=DEFAULT_PROMPT_VERSION):
    validate()
    cases = [case for case in read_json("cases.json") if not case_ids or case["id"] in case_ids]
    properties = catalog()
    model = load_extraction_model(num_predict=num_predict)
    chain = extraction_chain(model, include_raw=True, prompt_version=prompt_version)
    _, embeddings = load_index_config()
    vision = vision_configuration(load_ollama_base_url())
    snapshot = {}
    if visual_from:
        previous = json.loads(visual_from.read_text(encoding="utf-8"))
        for key, entry in previous["visual"].items():
            if entry is None:
                continue
            parsed = PhotoCacheEntry.model_validate(entry)
            prop, directory = properties[parsed.key.property_id]
            photo = next(photo for photo in prop.photos if photo.id == key == parsed.key.photo_id)
            if parsed.key.file_sha256 != sha256(read_photo_bytes(directory, photo.path)).hexdigest():
                raise ValueError(f"A foto mudou desde o pré-processamento: {key}")
            snapshot[key] = parsed

    runs = []
    # Expected answers are used by the validator and scorer, outside model inputs.
    for case in cases:
        criteria = ComparisonCriteria.model_validate(case["criteria"])
        runs.append([])
        for entry in case["inputs"]:
            prop, directory = properties[entry["propertyId"]]
            item = select_property(prop, entry["sourceIds"])
            photos, visual_issues = load_visual(item, directory, snapshot, vision)
            pages = None

            async def direct(property_item, _criterion):
                nonlocal pages
                if pages is None:
                    pages = [
                        page for doc in property_item.documents
                        for page in prepare_chunks(property_item.id, doc, directory, splitter=None)
                    ]
                return pages

            modes = {}
            for mode, provider in zip(MODES, (retrieve_property_context, direct), strict=True):
                print(f"{case['id']} {item.id} {mode}", flush=True)
                modes[mode] = await compare_mode(
                    case["id"], item, criteria, provider, photos, visual_issues, model, chain,
                    prompt_version=prompt_version,
                )
            runs[-1].append((entry, modes))

    expected = read_json("expected.json")
    results = []
    for case, properties_run in zip(cases, runs, strict=True):
        rows = []
        for entry, modes in properties_run:
            answers = {item["criterion"]: item for item in expected[case["id"]][entry["propertyId"]]}
            rows.append({**entry, "modes": {
                mode: score_mode(mode_result, answers) for mode, mode_result in modes.items()
            }})
        results.append({"id": case["id"], "properties": rows})
    check_cited_quotes(results)
    return {
        "runType": "real", "finishedAt": datetime.now(UTC).isoformat(), "caseVersion": CASE_VERSION,
        "caseHashes": {name: sha256((DIRECTORY / name).read_bytes()).hexdigest()
                       for name in ("cases.json", "expected.json")},
        "config": {
            "model": model.model, "embedding": embeddings.model, "temperature": model.temperature,
            "num_ctx": model.num_ctx, "num_predict": model.num_predict, "topK": 4,
            "structuredOutput": "json_schema", "vision": vision.model, "promptVersion": prompt_version,
        },
        "summary": summarize(results),
        "visual": {key: entry.model_dump(mode="json") if entry else None for key, entry in snapshot.items()},
        "cases": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--visual-from", type=Path, help="Reutiliza as observações de uma execução anterior.")
    parser.add_argument("--num-predict", type=int, default=NUM_PREDICT, help="Limite de saída da avaliação.")
    parser.add_argument("--prompt-version", choices=PROMPTS, default=DEFAULT_PROMPT_VERSION,
                        help="Versão do prompt de extração.")
    parser.add_argument("--case", action="append", choices=[case["id"] for case in read_json("cases.json")],
                        help="Executa apenas o caso indicado. Repita para selecionar vários casos.")
    args = parser.parse_args()
    if args.num_predict < 1:
        parser.error("--num-predict deve ser positivo.")
    result = asyncio.run(run(
        args.visual_from, num_predict=args.num_predict, case_ids=args.case, prompt_version=args.prompt_version,
    ))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return int(any(result["summary"][mode][mode]["overall"]["technicalFailures"] for mode in MODES))


if __name__ == "__main__":
    raise SystemExit(main())
