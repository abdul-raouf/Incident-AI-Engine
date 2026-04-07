from pathlib import Path
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from app.schemas.pydantic_schemas import IncidentCategory, ClassificationOutput
from app.core.config import settings

TEMPLATE_DIR = Path(__file__).parent.parent / "sop_templates"

TEMPLATE_MAP = {
    IncidentCategory.FIGHT:                "fight.md",
    IncidentCategory.FIRE:                 "fire.md",
    IncidentCategory.ACCIDENT:             "accident.md",
    IncidentCategory.SUSPICIOUS_BEHAVIOUR: "suspicious_behaviour.md",
}


MULTI_SOP_THRESHOLD = 0.15


LANGUAGE_INSTRUCTION = {
    "ar": "يجب أن تكون جميع القيم التي تملأها باللغة العربية فقط. لا تترجم عناوين القالب أو خطواته.",
    "en": "Fill all placeholder values in English only. Do not translate template headers or steps.",
}

SOP_FILL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an SOP completion assistant.
You are given an SOP template with placeholders like {{location}}, {{incident_time}}, {{parties_involved}}, etc.
Fill in the placeholders using ONLY the information present in the incident text.
     
{language_instruction}
    
Important placeholder guidance:
- {{incident_time}}: Look for any time mention (e.g. "14:32", "2pm", "الساعة 2", "١٤:٣٢")
- {{location}}: Look for any place, gate, station, zone mention
- {{parties_involved}}: Look for any description of people involved
- {{injuries_mentioned}}: Look for any mention of injuries or casualties
- {{additional_context}}: Any other relevant details from the text

If a placeholder's value truly cannot be found in the text, write "Not specified" or "غير محدد" (Arabic).
Do NOT add new steps. Do NOT remove existing steps. Only fill in the placeholders.
Return the completed SOP as plain text."""),
    ("human", """Incident Text:
{incident_text}

SOP Template:
{template}

Return the completed SOP:""")
])



def _load_template(category: IncidentCategory) -> str:
    filename = TEMPLATE_MAP.get(category)
    if not filename:
        return "No SOP template available for this category."
    template_path = TEMPLATE_DIR / filename
    if not template_path.exists():
        return f"SOP template file not found: {filename}"
    return template_path.read_text(encoding="utf-8")

def _get_active_categories(classification: ClassificationOutput) -> list[IncidentCategory]:
    """
    Returns all categories that should have SOPs generated.
    Includes the top category + any others within MULTI_SOP_THRESHOLD of it.
    Excludes UNKNOWN and zero-confidence categories.
    """
    top_score = classification.primary_confidence

    active = [
        score for score in classification.scores
        if score.category != IncidentCategory.UNKNOWN
        and score.confidence > 0.0
        and (top_score - score.confidence) <= MULTI_SOP_THRESHOLD
    ]

    # Sort descending by confidence
    return [s.category for s in sorted(active, key=lambda x: x.confidence, reverse=True)]


async def _fill_template(incident_text: str, category: IncidentCategory, language: str) -> str | None:
    template = _load_template(category)
    if not template:
        return None

    llm = ChatOllama(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        temperature=0.2
    )

    chain  = SOP_FILL_PROMPT | llm
    result = await chain.ainvoke({
        "incident_text": incident_text,
        "template":      template,
        "language_instruction": LANGUAGE_INSTRUCTION.get(language, LANGUAGE_INSTRUCTION["en"])
    })
    return result.content


async def generate_sop(incident_text: str, classification: ClassificationOutput) -> str:
    if classification.primary_category == IncidentCategory.UNKNOWN:
        no_sop_msg = {
            "ar": "لم يتم إنشاء إجراء تشغيل — تعذّر تصنيف الحادث.",
            "en": "No SOP generated — incident could not be classified."
        }
        return no_sop_msg.get(classification.detected_language, no_sop_msg["en"])


    active_categories = _get_active_categories(classification)

    if not active_categories:
        return "No SOP generated — no categories met the confidence threshold."

    # Generate SOP for each active category concurrently
    import asyncio
    sop_tasks  = [_fill_template(incident_text, cat, classification.detected_language) for cat in active_categories]
    sop_results = await asyncio.gather(*sop_tasks)

    # Merge all valid SOPs with clear section headers
    merged_parts = []
    for category, sop in zip(active_categories, sop_results):
        if sop:
            merged_parts.append(
                f"---\n##Detected Incident: {category.value}\n\n{sop}"
            )

    return "\n\n".join(merged_parts) if merged_parts else "No SOP could be generated."