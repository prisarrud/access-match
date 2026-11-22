"""Validate the evaluation files without calling the models."""
import json
import re
from pathlib import Path

from PIL import Image
from pydantic import TypeAdapter, ValidationError
from pypdf import PdfReader

from api.app.comparison.schemas import ComparisonCriteria, CriterionResult, PendingConfirmation
from api.app.properties.catalog import load_catalog

DIRECTORY = Path(__file__).resolve().parent
ROOT = DIRECTORY.parent


def read_json(name):
    return json.loads((DIRECTORY / name).read_text(encoding="utf-8"))


def require(condition, label):
    if not condition:
        raise ValueError(label)


def load_sources():
    sources = {}
    for catalog_path in (ROOT / "data/demo/properties.json", DIRECTORY / "fixtures/properties.json"):
        require(catalog_path.is_file(), f"Missing catalog {catalog_path}")
        for item in load_catalog(catalog_path).properties:
            require(item.id not in sources, f"Duplicate property {item.id}")
            entries = {f"listing:{item.id}": ("declaracao_anuncio", None)}
            for photo in item.photos:
                with Image.open(catalog_path.parent / photo.path) as image:
                    image.verify()
                entries[photo.id] = ("photo", None)
            for document in item.documents:
                pages = [page.extract_text() for page in PdfReader(catalog_path.parent / document.path).pages]
                require(all(page.strip() for page in pages), f"Empty PDF page in {document.id}")
                nature = "observacao_vistoria" if document.type == "vistoria" else "especificacao_projeto"
                entries[document.id] = (nature, pages)
            sources[item.id] = entries
    return sources


def validate():
    sources = load_sources()
    cases = read_json("cases.json")
    expected = read_json("expected.json")
    ids = {case["id"] for case in cases}
    require(len(cases) == len(ids) == 20 and ids == set(expected), "Expected 20 unique, matched case IDs")
    pending_adapter = TypeAdapter(list[PendingConfirmation])

    for case in cases:
        case_id = case["id"]
        require(set(case) == {"id", "scenario", "inputs", "criteria"} and case["scenario"].strip(), case_id)
        criteria = ComparisonCriteria.model_validate(case["criteria"]).requested()
        inputs = case["inputs"]
        properties = {item["propertyId"] for item in inputs}
        require(1 <= len(inputs) == len(properties) <= 2 and properties == set(expected[case_id]), case_id)
        for item in inputs:
            property_id = item["propertyId"]
            label = f"{case_id}/{property_id}"
            require(set(item) == {"propertyId", "sourceIds"}, label)
            available = sources[property_id]
            allowed = set(item["sourceIds"])
            require(allowed and len(allowed) == len(item["sourceIds"]) and allowed <= available.keys(), label)
            outcomes = expected[case_id][property_id]
            require(len(outcomes) == len(criteria) and {entry["criterion"] for entry in outcomes} == set(criteria), label)
            for outcome in outcomes:
                result = CriterionResult.model_validate({
                    key: outcome[key] for key in ("criterion", "status", "justification", "divergence", "toConfirm")
                })
                require(result.justification.strip(), label)
                pending_adapter.validate_python(outcome["toConfirm"])
                require(result.status != "a_confirmar" or result.toConfirm, label)
                refs = outcome["references"]
                require(result.status == "a_confirmar" or refs, label)
                require(not result.divergence or len({ref["sourceId"] for ref in refs}) >= 2, label)
                optional = outcome.get("optionalReferences", [])
                all_refs = refs + optional
                require(len({(ref["sourceId"], ref.get("page")) for ref in all_refs}) == len(all_refs), label)
                for ref in all_refs:
                    require(ref["sourceId"] in allowed, label)
                    _, pages = available[ref["sourceId"]]
                    if pages is None:
                        require(set(ref) == {"sourceId"}, label)
                    else:
                        require(set(ref) == {"sourceId", "page"} and type(ref["page"]) is int
                                and 1 <= ref["page"] <= len(pages), label)
                for measurement in outcome["measurements"]:
                    ref = measurement["reference"]
                    require(result.criterion == "largura" and ref in refs, label)
                    nature, pages = available[ref["sourceId"]]
                    require(pages is not None and nature == measurement["nature"], label)
                    require(measurement["unit"] in {"mm", "cm", "m"} and measurement["value"] > 0, label)
                    value = re.escape(str(measurement["value"])).replace(r"\.", "[.,]")
                    unit = measurement["unit"]
                    require(re.search(rf"(?<![\w.,]){value}\s*{unit}\b", pages[ref["page"] - 1]), label)


if __name__ == "__main__":
    try:
        validate()
    except (KeyError, TypeError, OSError, ValueError, ValidationError) as exc:
        raise SystemExit(f"Dados de avaliação inválidos: {exc}") from exc
    print("20 casos validados, com critérios, referências e páginas consistentes.")
