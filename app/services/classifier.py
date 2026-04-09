from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.schemas.pydantic_schemas import (
    ClassificationOutput, CategoryScore, IncidentCategory
)
from app.core.config import settings
import re
import json

# All valid categories passed explicitly into the prompt
CATEGORIES = [e.value for e in IncidentCategory if e != IncidentCategory.UNKNOWN]


CLASSIFICATION_PROMPT_FAST = ChatPromptTemplate.from_messages([
    ("system", """You are a multilingual incident classification assistant.
You support Arabic and English input text.

LANGUAGE DETECTION RULES:
- If the input contains Arabic script (ا ب ت ...), set detected_language to "ar"
- If the input is entirely Latin script, set detected_language to "en"

Score EVERY category with a confidence value between 0.0 and 1.0.
Scores are INDEPENDENT — they do not need to sum to 1.0.
Base scoring ONLY on the provided text.
Keep reasoning to a single short sentence.

Category definitions:
- "Fight": physical altercation, assault, brawl, punching (Arabic: شجار، عراك، اعتداء جسدي)
- "Fire": flames, smoke, burning, fire outbreak (Arabic: حريق، نار، دخان)
- "Accident": collision, crash, fall, unintentional injury (Arabic: حادث، تصادم، سقوط)
- "Suspicious Behaviour": unattended bags, loitering, unusual conduct (Arabic: سلوك مشبوه)
- "Impersonation": pretending to be another person (Arabic: انتحال شخصية)
- "Suicide": self-harm or attempt to end life (Arabic: انتحار)
- "Death": reported death or fatality (Arabic: وفاة)
- "Begging": soliciting money in public (Arabic: تسول)
- "Theft": stealing or robbery (Arabic: سرقة)
- "Strike": work stoppage or labor protest (Arabic: اضراب)
- "Bribery": offering or accepting illegal incentives (Arabic: رشاوي)
- "Vandalism": damaging property (Arabic: تخريب، اتلاف)
- "Harassment": inappropriate or unwanted behavior (Arabic: تحرش)
- "Drug Abuse": use of illegal substances (Arabic: تعاطي ممنوعات)
- "Cyberattack": hacking or unauthorized access (Arabic: اختراق)
- "Fraud": deception for financial or personal gain (Arabic: احتيال)
- "Threat": verbal or physical threat (Arabic: تهديد)
- "Forgery": falsification of documents (Arabic: تزوير)

Return ONLY this JSON, nothing else:
{{
  "detected_language": "<ar or en>",
  "scores": [
    {{"category": "Fight",                "confidence": <float>}},
    {{"category": "Fire",                 "confidence": <float>}},
    {{"category": "Accident",             "confidence": <float>}},
    {{"category": "Suspicious Behaviour", "confidence": <float>}},
    {{"category": "Impersonation",        "confidence": <float>}},
    {{"category": "Suicide",              "confidence": <float>}},
    {{"category": "Death",                "confidence": <float>}},
    {{"category": "Begging",              "confidence": <float>}},
    {{"category": "Theft",                "confidence": <float>}},
    {{"category": "Strike",               "confidence": <float>}},
    {{"category": "Bribery",              "confidence": <float>}},
    {{"category": "Vandalism",            "confidence": <float>}},
    {{"category": "Harassment",           "confidence": <float>}},
    {{"category": "Drug Abuse",           "confidence": <float>}},
    {{"category": "Cyberattack",          "confidence": <float>}},
    {{"category": "Fraud",                "confidence": <float>}},
    {{"category": "Threat",               "confidence": <float>}},
    {{"category": "Forgery",              "confidence": <float>}}
  ],
  "reasoning": "<one short sentence>"
}}"""),
    ("human", "{text}")   # ← no label wrapping, shorter prompt = faster
])


CLASSIFICATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a multilingual incident classification assistant.
You support Arabic and English input text.
     

LANGUAGE DETECTION RULES — follow these strictly:
- Examine the SCRIPT of the input text, not its topic
- If the input contains Arabic script (ا ب ت ث ...), set detected_language to "ar" — even if some words are English
- If the input is entirely Latin script, set detected_language to "en"
- The category names are always in English regardless of input language
- Write your reasoning in the SAME language as the input text
     

Scoring rules:
- Score ALL categories — do not skip any
- Scores are INDEPENDENT — they do not need to sum to 1.0
- 0.0 = category is completely absent, 1.0 = near-perfect match
- Base scoring ONLY on the provided text. Do not assume facts not present.
- Return valid JSON only. No text outside the JSON block.

Category definitions (use these regardless of input language):
- "Fight": physical altercation, assault, brawl, punching, violence between people
           (Arabic: شجار، عراك، اعتداء جسدي، ضرب)
- "Fire": flames, smoke, burning, fire outbreak, combustion
           (Arabic: حريق، نار، دخان، اشتعال)
- "Accident": collision, crash, fall, unintentional injury, vehicle incident
           (Arabic: حادث، تصادم، اصطدام، سقوط)
- "Suspicious Behaviour": unattended bags, loitering, unusual conduct, surveillance evasion
           (Arabic: سلوك مشبوه، حقيبة مهجورة، تجوال مريب)

Return this exact JSON structure:
{{
  "detected_language": "<ar or en>",
  "scores": [
    {{"category": "Fight",                "confidence": <float>}},
    {{"category": "Fire",                 "confidence": <float>}},
    {{"category": "Accident",             "confidence": <float>}},
    {{"category": "Suspicious Behaviour", "confidence": <float>}}
  ],
  "reasoning": "<one sentence in the SAME language as the input text>"
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
        reasoning="Classification failed — LLM output could not be parsed.",
        detected_language = _detect_language(text) if text else "en"
    )


def _detect_language(text: str) -> str:
    arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+')
    matches        = arabic_pattern.findall(text)
    arabic_chars   = len(matches)
    total_words    = len(text.split())

    print(f"=== LANG DETECT: arabic_matches={arabic_chars}, total_words={total_words}, ratio={arabic_chars/total_words if total_words else 0:.2f} ===")

    if total_words > 0 and arabic_chars / total_words > 0.2:
        return "ar"
    return "en"


def _parse_raw(raw: dict, original_text: str = "") -> ClassificationOutput:
    llm_lookup: dict[str, float] = {}
    for entry in raw.get("scores", []):
        llm_lookup[entry.get("category", "")] = float(entry.get("confidence", 0.0))

    scores = [
        CategoryScore(category=cat, confidence=llm_lookup.get(cat.value, 0.0))
        for cat in [
            IncidentCategory.FIGHT,
            IncidentCategory.FIRE,
            IncidentCategory.ACCIDENT,
            IncidentCategory.SUSPICIOUS_BEHAVIOUR,
            IncidentCategory.IMPERSONATION,
            IncidentCategory.SUICIDE,
            IncidentCategory.DEATH,
            IncidentCategory.BEGGING,
            IncidentCategory.THEFT,
            IncidentCategory.STRIKE,
            IncidentCategory.BRIBERY,
            IncidentCategory.VANDALISM,
            IncidentCategory.HARASSMENT,
            IncidentCategory.DRUG_ABUSE,
            IncidentCategory.CYBERATTACK,
            IncidentCategory.FRAUD,
            IncidentCategory.THREAT,
            IncidentCategory.FORGERY
        ]
    ]

    # Always use Python-side detection — never trust LLM for this field
    detected_language = _detect_language(original_text) if original_text else "en"

    return ClassificationOutput(
        scores            = scores,
        reasoning         = raw.get("reasoning", ""),
        detected_language = detected_language
    )


# ── Shared LLM factory ────────────────────────────────────────────────────────

def _get_llm(num_predict: int | None = None) -> ChatOllama:
    """
    Returns a ChatOllama instance with thinking mode disabled.
    qwen3 models output <think> blocks by default which breaks JSON parsing.
    """
    kwargs = dict(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        temperature=0,
        format="json", 
    )
    if num_predict:
        kwargs["num_predict"] = num_predict
    return ChatOllama(**kwargs)



def _extract_json(raw_output: str) -> dict:
    """
    Strips <think>...</think> blocks and extracts the first valid JSON object.
    Guards against any model that leaks reasoning outside JSON mode.
    """
    # Remove thinking blocks
    cleaned = re.sub(r"<think>.*?</think>", "", raw_output, flags=re.DOTALL).strip()

    # Extract first JSON object found
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in output: {raw_output[:200]}")

    return json.loads(match.group())


async def classify_text_fast(text: str) -> ClassificationOutput:
    """
    Lightweight classification for real-time as-you-type suggestions.
    No DB write. Optimized for low latency.
    """
    llm = ChatOllama(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        temperature=0,
        format="json",
        num_predict=2500,   # ← cap token output for speed
        extra_body={"think": False}
    )

    chain = CLASSIFICATION_PROMPT_FAST | llm 

    try:
        print("chain  ->", chain)
        result = await chain.ainvoke({"text": text})
        print("=== RAW LLM OUTPUT ===")
        print("result->>",result)   # ← add this
        print("=== END RAW OUTPUT ===")
        raw    = _extract_json(result.content)
        return _parse_raw(raw, text)  


        # raw = await chain.ainvoke({"text": text})
        # return _parse_raw(raw, text)
    except Exception as e:
        fallback = _build_fallback(text)
        fallback.reasoning = f"Parsing error: {str(e)}"
        return fallback

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
        return _parse_raw(raw, text) 
    except Exception as e:
        fallback = _build_fallback(text)
        fallback.reasoning = f"Parsing error: {str(e)}"
        return fallback























# import httpx

# async def _call_ollama_direct(prompt_messages: list) -> str:
#     async with httpx.AsyncClient(proxies=None, follow_redirects=True, timeout=httpx.Timeout(
#     connect=10.0,
#     read=120.0,   
#     write=10.0,
#     pool=10.0
# )) as client:
#         payload = {
#             "model":  settings.OLLAMA_MODEL,
#             "stream": False,
#             "think":  False,
#             "options": {"temperature": 0},
#             "messages": prompt_messages
#         }

#         print("=== OLLAMA REQUEST ===")
#         print(json.dumps(payload, ensure_ascii=False, indent=2))

#         response = await client.post(
#             f"{settings.OLLAMA_BASE_URL}/api/chat",
#             json=payload
#         )

#         print("=== OLLAMA STATUS ===", response.status_code)
#         print("=== OLLAMA RAW RESPONSE ===")
#         print(response.text)   # full raw response body

#         response.raise_for_status()
#         return response.json()["message"]["content"]


# async def classify_text_fast(text: str) -> ClassificationOutput:
#     # Build messages list from the prompt template
#     prompt_messages = [
#         {"role": "system", "content": CLASSIFICATION_PROMPT_FAST.messages[0].prompt.template},
#         {"role": "user",   "content": text}
#     ]

#     try:
#         raw_output = await _call_ollama_direct(prompt_messages)
#         print("=== EXTRACTED CONTENT ===", repr(raw_output[:500]))
#         raw        = _extract_json(raw_output)
#         return _parse_raw(raw, text)
#     except Exception as e:
#         import traceback
#         print("=== EXCEPTION ===")
#         traceback.print_exc()          # full stack trace, not just message
#         fallback           = _build_fallback()
#         fallback.reasoning = f"Parsing error: {str(e)}"
#         return fallback




























# async def classify_text(text: str) -> ClassificationOutput:
#     llm   = _get_llm()
#     chain = CLASSIFICATION_PROMPT | llm

#     try:
#         result = await chain.ainvoke({"text": text})
#         raw    = _extract_json(result.content)
#         return _parse_raw(raw, text)
#     except Exception as e:
#         fallback           = _build_fallback()
#         fallback.reasoning = f"Parsing error: {str(e)}"
#         return fallback



# async def classify_text_fast(text: str) -> ClassificationOutput:
#     llm   = _get_llm(num_predict=200)
#     chain = CLASSIFICATION_PROMPT_FAST | llm

#     try:
#         result = await chain.ainvoke({"text": text})
#         print("=== RAW LLM OUTPUT ===")
#         print(repr(result))   # ← add this
#         print("=== END RAW OUTPUT ===")
#         raw    = _extract_json(result.content)
#         return _parse_raw(raw, text)
#     except Exception as e:
#         fallback           = _build_fallback()
#         fallback.reasoning = f"Parsing error: {str(e)}"
#         return fallback