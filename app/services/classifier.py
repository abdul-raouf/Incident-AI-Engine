from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.schemas.pydantic_schemas import (
    ClassificationOutput, CategoryScore, IncidentCategory
)
from app.core.config import settings
import json

# All valid categories passed explicitly into the prompt
CATEGORIES = [e.value for e in IncidentCategory if e != IncidentCategory.UNKNOWN]

CLASSIFICATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an incident classification assistant.
You will be given incident text and a fixed list of categories.

Your job is to score EVERY category with a confidence value between 0.0 and 1.0,
representing how strongly the text matches that category.

Rules:
- Score ALL categories — do not skip any.
- Scores are INDEPENDENT — they do not need to sum to 1.0.
- A score of 0.0 means the category is completely absent from the text.
- A score of 1.0 means the text is a near-perfect match for that category.
- Base scoring ONLY on the provided text. Do not assume facts not present.
- Return valid JSON only. No text outside the JSON block.

Return this exact JSON structure:
{{
  "scores": [
    {{"category": "Fight",                "confidence": <float>}},
    {{"category": "Fire",                 "confidence": <float>}},
    {{"category": "Accident",             "confidence": <float>}},
    {{"category": "Suspicious Behaviour", "confidence": <float>}}
  ],
  "reasoning": "<one sentence explaining the top classification>"
}}"""),
    ("human", "Classify the following incident text:\n\n{text}")
])

def _build_fallback() -> ClassificationOutput:
    """Returns a zero-confidence fallback when LLM output cannot be parsed."""
    return ClassificationOutput(
        scores=[
            CategoryScore(category=IncidentCategory.FIGHT,                confidence=0.0),
            CategoryScore(category=IncidentCategory.FIRE,                 confidence=0.0),
            CategoryScore(category=IncidentCategory.ACCIDENT,             confidence=0.0),
            CategoryScore(category=IncidentCategory.SUSPICIOUS_BEHAVIOUR, confidence=0.0),
        ],
        reasoning="Classification failed — LLM output could not be parsed."
    )


def _parse_raw(raw: dict) -> ClassificationOutput:
    """Validates and coerces raw LLM JSON into ClassificationOutput."""
    raw_scores = raw.get("scores", [])

    # Build a lookup from whatever the LLM returned
    llm_lookup: dict[str, float] = {}
    for entry in raw_scores:
        cat = entry.get("category", "")
        score = float(entry.get("confidence", 0.0))
        llm_lookup[cat] = score

    # Always produce a score for EVERY known category
    # If LLM missed one, default to 0.0
    scores = []
    for category in [
        IncidentCategory.FIGHT,
        IncidentCategory.FIRE,
        IncidentCategory.ACCIDENT,
        IncidentCategory.SUSPICIOUS_BEHAVIOUR,
    ]:
        scores.append(CategoryScore(
            category   = category,
            confidence = llm_lookup.get(category.value, 0.0)
        ))

    return ClassificationOutput(
        scores    = scores,
        reasoning = raw.get("reasoning", "")
    )


async def classify_text(text: str) -> ClassificationOutput:
    llm = ChatOllama(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        temperature=0,
        format="json"
    )

    chain = CLASSIFICATION_PROMPT | llm | JsonOutputParser()

    try:
        raw = await chain.ainvoke({"text": text})
        return _parse_raw(raw)
    except Exception as e:
        fallback = _build_fallback()
        fallback.reasoning = f"Parsing error: {str(e)}"
        return fallback