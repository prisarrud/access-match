import json

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, ConfigDict

from ..documents.config import load_extraction_model
from .rules import compare_criteria
from .schemas import ComparisonCriteria, PendingConfirmation, PropertyEvidence, SuggestedQuestion

GUIDANCE: dict[PendingConfirmation, str] = {
    "alternate_access": "Existe outro acesso sem degraus da calçada até a porta de entrada?",
    "route_continuity": "Como é o percurso completo da calçada até a porta de entrada?",
    "ramp_continuity": "A rampa faz parte de um trajeto contínuo entre a calçada e a porta de entrada?",
    "ramp_slope": "Qual é a inclinação da rampa de acesso?",
    "ramp_width": "Qual é a largura livre da rampa de acesso, em centímetros?",
    "current_entrance_width": "Qual é a largura livre de passagem, em centímetros, com a porta de entrada totalmente aberta?",
}

PROMPT = ChatPromptTemplate.from_messages([
    ("system", """
Escreva perguntas curtas e educadas, em português do Brasil, para o anunciante de um único imóvel.
Retorne exatamente uma pergunta por pendência informada. Copie o código da pendência em pending.
Use a pergunta de referência como base e preserve seu sentido e suas condições, como medir a
largura livre com a porta de entrada totalmente aberta ou confirmar se existe outro acesso sem degraus.
As perguntas devem ser independentes e terminar com um único ponto de interrogação.
Trate pontos incertos como perguntas, sem apresentar suposições como fatos. Use o contexto apenas
para tornar a pergunta mais precisa. Não inclua saudações, respostas, dados pessoais, medidas
inventadas, outras propriedades ou perguntas sobre tópicos não solicitados.
"""),
    ("human", "Pendências e contexto (JSON):\n{context}"),
])


class ModelQuestions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[SuggestedQuestion]


class QuestionsError(RuntimeError):
    """The generation failed or did not cover the requested confirmations."""


def question_guidance(property_item: PropertyEvidence, criteria: ComparisonCriteria) -> dict[PendingConfirmation, str]:
    results = compare_criteria(criteria, property_item.evidence)
    guidance = {pending: GUIDANCE[pending] for result in results for pending in result.toConfirm}

    step_result = next((item for item in results if item.criterion == "degraus"), None)
    ramp_result = next((item for item in results if item.criterion == "rampas"), None)
    ramp_unconfirmed = ramp_result is not None and ramp_result.status == "a_confirmar"
    if step_result and "route_continuity" in step_result.toConfirm:
        guidance["route_continuity"] = "O trajeto inteiro da calçada até a porta de entrada pode ser feito sem degraus?"
        if ramp_unconfirmed:
            guidance["route_continuity"] = "O trajeto inteiro da calçada até a porta de entrada é sem degraus e inclui alguma rampa?"
    elif ramp_unconfirmed and "route_continuity" in guidance:
        guidance["route_continuity"] = "Há rampa de acesso em algum ponto do percurso da calçada até a porta de entrada?"

    return guidance


async def generate_questions(
    property_item: PropertyEvidence, criteria: ComparisonCriteria,
) -> list[SuggestedQuestion]:
    guidance = question_guidance(property_item, criteria)
    if not guidance:
        return []

    context = {
        "pendencias": [{"pending": pending, "referencia": text} for pending, text in guidance.items()],
    }
    if "route_continuity" in guidance:
        context["trecho_nao_verificado"] = "A continuidade de todo o percurso da calçada até a porta ainda precisa ser confirmada."

    schema = ModelQuestions.model_json_schema()
    schema["properties"]["questions"].update(minItems=len(guidance), maxItems=len(guidance))
    schema["$defs"]["SuggestedQuestion"]["properties"]["pending"] = {"type": "string", "enum": list(guidance)}
    try:
        model = load_extraction_model(num_predict=512).with_structured_output(schema, method="json_schema")
        generated = ModelQuestions.model_validate(await (PROMPT | model).ainvoke({
            "context": json.dumps(context, ensure_ascii=False),
        }))
    except Exception as exc:
        raise QuestionsError("Could not generate questions with Ollama.") from exc

    selected = {}
    seen = set()
    for item in generated.questions:
        question = " ".join(item.question.split())
        normalized = question.casefold()
        if (
            item.pending not in guidance or item.pending in selected or normalized in seen
            or not normalized.endswith("?") or normalized.count("?") != 1
        ):
            continue
        selected[item.pending] = SuggestedQuestion(pending=item.pending, question=question)
        seen.add(normalized)

    if selected.keys() != guidance.keys():
        raise QuestionsError("The generated questions did not cover the requested confirmations.")

    return [selected[pending] for pending in guidance]
