import re

FULL_ROUTE = re.compile(r"\b(?:da|desde a) calçada (?:até|à|a) (?:a )?(?:porta(?: de entrada)?|entrada)\b")
SCOPE_LIMIT = re.compile(r"\b(?:exceto|fora do escopo|fora da inspeção|não cobre|não abrange|não (?:foi|foram) (?:avaliad[oa]s?|vistoriad[oa]s?))\b")


def describes_full_route(quote: str) -> bool:
    text = " ".join(quote.casefold().split())
    return bool(FULL_ROUTE.search(text) and not SCOPE_LIMIT.search(text))
