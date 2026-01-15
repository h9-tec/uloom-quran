"""
AI API Routes for علوم القرآن Platform
Provides endpoints for semantic search, Q&A, and AI-powered analysis
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, AsyncGenerator
import logging
import json
import re

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["AI"])

# Beta disclaimer to append to all AI responses
AI_DISCLAIMER = """

---
**تنبيه هام:** هذه النسخة التجريبية (Beta). والله أعلم، واستشر شيخاً وعالماً للتأكد من المعلومات الشرعية."""


# =============================================================================
# Mutashabihat Detection Helpers
# =============================================================================

# Map of Arabic surah names to numbers
SURAH_NAMES = {
    'الفاتحة': 1, 'البقرة': 2, 'آل عمران': 3, 'النساء': 4, 'المائدة': 5,
    'الأنعام': 6, 'الأعراف': 7, 'الأنفال': 8, 'التوبة': 9, 'يونس': 10,
    'هود': 11, 'يوسف': 12, 'الرعد': 13, 'إبراهيم': 14, 'الحجر': 15,
    'النحل': 16, 'الإسراء': 17, 'الكهف': 18, 'مريم': 19, 'طه': 20,
    'الأنبياء': 21, 'الحج': 22, 'المؤمنون': 23, 'النور': 24, 'الفرقان': 25,
    'الشعراء': 26, 'النمل': 27, 'القصص': 28, 'العنكبوت': 29, 'الروم': 30,
    'لقمان': 31, 'السجدة': 32, 'الأحزاب': 33, 'سبأ': 34, 'فاطر': 35,
    'يس': 36, 'الصافات': 37, 'ص': 38, 'الزمر': 39, 'غافر': 40,
    'فصلت': 41, 'الشورى': 42, 'الزخرف': 43, 'الدخان': 44, 'الجاثية': 45,
    'الأحقاف': 46, 'محمد': 47, 'الفتح': 48, 'الحجرات': 49, 'ق': 50,
    'الذاريات': 51, 'الطور': 52, 'النجم': 53, 'القمر': 54, 'الرحمن': 55,
    'الواقعة': 56, 'الحديد': 57, 'المجادلة': 58, 'الحشر': 59, 'الممتحنة': 60,
    'الصف': 61, 'الجمعة': 62, 'المنافقون': 63, 'التغابن': 64, 'الطلاق': 65,
    'التحريم': 66, 'الملك': 67, 'القلم': 68, 'الحاقة': 69, 'المعارج': 70,
    'نوح': 71, 'الجن': 72, 'المزمل': 73, 'المدثر': 74, 'القيامة': 75,
    'الإنسان': 76, 'المرسلات': 77, 'النبأ': 78, 'النازعات': 79, 'عبس': 80,
    'التكوير': 81, 'الانفطار': 82, 'المطففين': 83, 'الانشقاق': 84, 'البروج': 85,
    'الطارق': 86, 'الأعلى': 87, 'الغاشية': 88, 'الفجر': 89, 'البلد': 90,
    'الشمس': 91, 'الليل': 92, 'الضحى': 93, 'الشرح': 94, 'التين': 95,
    'العلق': 96, 'القدر': 97, 'البينة': 98, 'الزلزلة': 99, 'العاديات': 100,
    'القارعة': 101, 'التكاثر': 102, 'العصر': 103, 'الهمزة': 104, 'الفيل': 105,
    'قريش': 106, 'الماعون': 107, 'الكوثر': 108, 'الكافرون': 109, 'النصر': 110,
    'المسد': 111, 'الإخلاص': 112, 'الفلق': 113, 'الناس': 114
}


def _detect_mutashabihat_question(question: str) -> tuple:
    """
    Check if the question is about mutashabihat and extract verse reference.
    Returns: (is_mutashabihat, verse_key or None)
    """
    mutashabihat_keywords = [
        'متشابه', 'المتشابه', 'تشابه', 'مشابه', 'similar',
        'mutashabih', 'تتشابه', 'يتشابه', 'شبيه', 'المشابهة'
    ]

    is_mutashabihat = any(keyword in question.lower() for keyword in mutashabihat_keywords)

    # Try to extract verse reference
    verse_key = None

    # Pattern 1: verse_key format like "2:14" or "2:255"
    verse_pattern = r'(\d{1,3}):(\d{1,3})'
    match = re.search(verse_pattern, question)
    if match:
        verse_key = f"{match.group(1)}:{match.group(2)}"
        return is_mutashabihat, verse_key

    # Pattern 2: Arabic surah name with ayah number
    for surah_name, surah_num in SURAH_NAMES.items():
        if surah_name in question:
            # Look for ayah number
            ayah_patterns = [
                rf'(?:الآية|آية|الايه|ايه|اية|الاية)\s*(\d+)',
                rf'(\d+)\s*(?:من\s*)?(?:سورة\s*)?{surah_name}',
                rf'{surah_name}\s*(?:الآية|آية|الايه|ايه|اية)?\s*(\d+)',
            ]

            for pattern in ayah_patterns:
                ayah_match = re.search(pattern, question)
                if ayah_match:
                    ayah_num = ayah_match.group(1)
                    verse_key = f"{surah_num}:{ayah_num}"
                    return is_mutashabihat, verse_key

    return is_mutashabihat, verse_key


def _get_mutashabihat_data(verse_key: str) -> tuple:
    """
    Get mutashabihat data for a verse from local service and Quranpedia.
    Returns: (context_string, sources_list)
    """
    try:
        sources = []
        context_parts = []
        similar_verses = []

        # Try local service first
        try:
            from src.services.mutashabihat_service import get_mutashabihat_service
            mutashabihat_svc = get_mutashabihat_service()
            result = mutashabihat_svc.get_mutashabihat(verse_key)
            if result.get("success"):
                source_verse = result.get("source_verse", {})
                if source_verse:
                    context_parts.append(f"الآية الأصلية ({verse_key}):")
                    context_parts.append(f"  {source_verse.get('text_uthmani', '')}")
                    context_parts.append(f"  سورة {source_verse.get('surah_name_ar', '')}")
                similar_verses = result.get("similar_verses", [])
        except ImportError:
            logger.warning("Mutashabihat service not available")

        # If no local data, try Quranpedia
        if not similar_verses:
            try:
                from src.services.quranpedia_service import get_quranpedia_service
                parts = verse_key.split(":")
                if len(parts) == 2:
                    surah, ayah = int(parts[0]), int(parts[1])
                    qp_service = get_quranpedia_service()
                    qp_data = qp_service.get_similar_verses_sync(surah, ayah)

                    if qp_data and isinstance(qp_data, list):
                        for item in qp_data:
                            if not item.get("ayahs") or not isinstance(item["ayahs"], list):
                                continue

                            notes = item.get("notes", "")
                            ayahs_list = item["ayahs"]

                            # Check if source verse is in this group
                            source_in_group = any(
                                f"{(a.get('info') or a).get('surah_id', '')}:{(a.get('info') or a).get('number', '')}" == verse_key
                                for a in ayahs_list
                            )
                            if not source_in_group:
                                continue
                            if "انفرادات" in notes:
                                continue

                            for ayah_item in ayahs_list:
                                info = ayah_item.get("info", ayah_item)
                                sv_key = f"{info.get('surah_id', '')}:{info.get('number', '')}"
                                if sv_key == verse_key:
                                    continue
                                similar_verses.append({
                                    "verse_key": sv_key,
                                    "text_uthmani": info.get("text", ""),
                                    "notes": notes,
                                    "source": "quranpedia"
                                })

                        if not context_parts:
                            context_parts.append(f"الآية الأصلية ({verse_key}):")
            except Exception as e:
                logger.warning(f"Error getting Quranpedia mutashabihat: {e}")

        # Format similar verses
        if similar_verses:
            context_parts.append(f"\nالآيات المتشابهة لفظياً ({len(similar_verses)} آية):")
            for i, sv in enumerate(similar_verses, 1):
                sv_key = sv.get("verse_key", "")
                sv_text = sv.get("text_uthmani", "")
                sv_notes = sv.get("notes", "")
                context_parts.append(f"{i}. ({sv_key}):")
                context_parts.append(f"   {sv_text}")
                if sv_notes:
                    context_parts.append(f"   ملاحظة: {sv_notes}")
                sources.append({
                    "type": "mutashabihat",
                    "reference": sv_key,
                    "source": sv.get("source", "local")
                })

        return "\n".join(context_parts), sources

    except Exception as e:
        logger.error(f"Error getting mutashabihat data: {e}")
        return "", []


# Request/Response Models
class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=3, description="السؤال بالعربية أو الإنجليزية")
    include_verses: bool = Field(default=True, description="تضمين الآيات في السياق")
    include_tafsir: bool = Field(default=True, description="تضمين التفاسير في السياق")
    include_qiraat: bool = Field(default=False, description="تضمين القراءات في السياق")
    surah_filter: Optional[int] = Field(default=None, ge=1, le=114, description="تصفية حسب السورة")
    language: str = Field(default="ar", description="لغة الإجابة")


class VerseExplanationRequest(BaseModel):
    surah_id: int = Field(..., ge=1, le=114)
    ayah_id: int = Field(..., ge=1)
    verse_text: Optional[str] = None


class QiraatAnalysisRequest(BaseModel):
    surah_id: int = Field(..., ge=1, le=114)
    ayah_id: int = Field(..., ge=1)
    verse_text: Optional[str] = None


class TafsirComparisonRequest(BaseModel):
    surah_id: int = Field(..., ge=1, le=114)
    ayah_id: int = Field(..., ge=1)
    verse_text: Optional[str] = None
    tafsir_ids: Optional[List[int]] = None


class MutashabihatAnalysisRequest(BaseModel):
    surah_id: int = Field(..., ge=1, le=114)
    ayah_id: int = Field(..., ge=1)
    verse_text: Optional[str] = None
    similar_verses: Optional[List[Dict[str, Any]]] = None


class HifzAssistantRequest(BaseModel):
    """Request model for Quran memorization (Hifz) assistance"""
    question: str = Field(..., min_length=3, description="سؤال عن الحفظ أو المراجعة")
    mode: str = Field(
        default="general",
        description="نوع المساعدة: general, mutashabihat, revision_plan, memorization_tips, verse_distinction"
    )
    surah_id: Optional[int] = Field(default=None, ge=1, le=114, description="رقم السورة")
    ayah_id: Optional[int] = Field(default=None, ge=1, description="رقم الآية")
    juz_memorized: Optional[int] = Field(default=None, ge=1, le=30, description="عدد الأجزاء المحفوظة")
    daily_time_minutes: Optional[int] = Field(default=None, ge=10, le=480, description="الوقت المتاح يومياً بالدقائق")
    language: str = Field(default="ar", description="لغة الإجابة")


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="استعلام البحث")
    search_type: str = Field(default="all", description="نوع البحث: verses, tafsir, qiraat, all")
    limit: int = Field(default=10, ge=1, le=50)
    surah_filter: Optional[int] = Field(default=None, ge=1, le=114)


class ChatMessage(BaseModel):
    role: str = Field(..., description="user أو assistant")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    include_context: bool = Field(default=True, description="تضمين السياق القرآني")


class AIResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None


def get_rag_service():
    """Lazy import to avoid circular dependencies and handle missing dependencies."""
    try:
        from src.ai.services.rag_service import get_rag_service as _get_rag_service
        return _get_rag_service()
    except ImportError as e:
        logger.error(f"Failed to import RAG service: {e}")
        raise HTTPException(
            status_code=503,
            detail="AI service unavailable. Please ensure all dependencies are installed."
        )
    except Exception as e:
        logger.error(f"Failed to initialize RAG service: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"AI service initialization failed: {str(e)}"
        )


@router.post("/ask", response_model=AIResponse)
async def ask_question(request: QuestionRequest):
    """
    اسأل سؤالاً عن القرآن الكريم

    Ask a question about the Quran and get an AI-powered answer
    with relevant verses and tafsir as context.
    """
    try:
        rag_service = get_rag_service()
        result = rag_service.answer_question(
            question=request.question,
            include_verses=request.include_verses,
            include_tafsir=request.include_tafsir,
            include_qiraat=request.include_qiraat,
            surah_filter=request.surah_filter,
            language=request.language
        )
        return AIResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error in ask_question: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask/stream")
async def ask_question_stream(request: QuestionRequest):
    """
    اسأل سؤالاً مع البث المباشر للإجابة

    Ask a question and receive a streaming response.
    """
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            import re
            from openai import AzureOpenAI
            from src.ai.config import azure_config, rag_config, SYSTEM_PROMPTS
            from src.ai.services.embedding_service import get_embedding_service
            from src.ai.services.qdrant_service import get_qdrant_service

            embedding_service = get_embedding_service()
            qdrant_service = get_qdrant_service()

            # Check if this is a mutashabihat question
            is_mutashabihat, verse_key = _detect_mutashabihat_question(request.question)

            # Retrieve relevant context
            context_parts = []
            sources = []

            # If mutashabihat question with verse reference, get mutashabihat data first
            if is_mutashabihat and verse_key:
                mutashabihat_context, mutashabihat_sources = _get_mutashabihat_data(verse_key)
                if mutashabihat_context:
                    context_parts.append("بيانات المتشابهات:\n" + mutashabihat_context)
                    sources.extend(mutashabihat_sources)

            # Generate embedding for the question
            query_vector = embedding_service.get_embedding(request.question)

            if request.include_verses:
                verses = qdrant_service.search_verses(
                    query_vector=query_vector,
                    limit=rag_config.top_k_verses,
                    surah_id=request.surah_filter
                )
                if verses:
                    for v in verses:
                        payload = v.get("payload", {})
                        vk = payload.get("verse_key", "")
                        text_ar = payload.get("text_ar", "")
                        surah_name = payload.get("surah_name_ar", "")
                        context_parts.append(f"- {surah_name} ({vk}): {text_ar}")
                        sources.append({"type": "verse", "reference": vk, "score": v["score"]})

            if request.include_tafsir:
                tafsir = qdrant_service.search_tafsir(
                    query_vector=query_vector,
                    limit=rag_config.top_k_tafsir
                )
                if tafsir:
                    for t in tafsir:
                        payload = t.get("payload", {})
                        tafsir_name = payload.get("tafsir_name", "")
                        text = payload.get("text", "")[:500]
                        vk = payload.get("verse_key", "")
                        context_parts.append(f"- {tafsir_name} ({vk}):\n{text}...")
                        sources.append({"type": "tafsir", "reference": tafsir_name, "verse_key": vk})

            combined_context = "\n".join(context_parts) if context_parts else "لا يوجد سياق متاح"

            # Send sources first
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

            # Create streaming response
            client = AzureOpenAI(
                azure_endpoint=azure_config.endpoint,
                api_key=azure_config.api_key,
                api_version=azure_config.api_version,
                timeout=60.0
            )

            # Use special prompt for mutashabihat questions
            if is_mutashabihat and verse_key:
                prompt = f"""أنت متخصص في علم المتشابهات في القرآن الكريم.

مهمتك الإجابة على السؤال التالي باستخدام البيانات المتاحة.

السياق:
{combined_context}

السؤال: {request.question}

قدم إجابة شاملة تتضمن:
1. تحديد الآيات المتشابهة لفظياً (التي تتشابه في الكلمات والعبارات)
2. أوجه التشابه اللفظي بين الآيات
3. الفروق الدقيقة بين الآيات
4. السياق المختلف لكل آية
5. نصائح للتمييز بينها للحفظ

ملاحظة مهمة: المتشابهات اللفظية هي الآيات التي تتشابه في الألفاظ والكلمات، وليس فقط في الموضوع.
إذا لم تجد آيات متشابهة لفظياً في البيانات، اذكر ذلك بوضوح."""
            else:
                prompt = SYSTEM_PROMPTS["general_qa"].format(
                    context=combined_context,
                    question=request.question
                )

            stream = client.chat.completions.create(
                model=azure_config.chat_deployment,
                messages=[{"role": "system", "content": prompt}],
                temperature=azure_config.chat_temperature,
                max_tokens=azure_config.chat_max_tokens,
                stream=True
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

            # Append beta disclaimer
            yield f"data: {json.dumps({'type': 'content', 'content': AI_DISCLAIMER})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Error in streaming: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/explain-verse", response_model=AIResponse)
async def explain_verse(request: VerseExplanationRequest):
    """
    شرح آية قرآنية

    Get a detailed explanation of a specific Quran verse,
    including tafsir, linguistic analysis, and asbab al-nuzul.
    """
    try:
        rag_service = get_rag_service()
        result = rag_service.explain_verse(
            surah_id=request.surah_id,
            ayah_id=request.ayah_id,
            verse_text=request.verse_text
        )
        return AIResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error in explain_verse: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-qiraat", response_model=AIResponse)
async def analyze_qiraat(request: QiraatAnalysisRequest):
    """
    تحليل القراءات المختلفة لآية

    Analyze different qiraat (recitation) variations for a verse,
    explaining linguistic and semantic differences.
    """
    try:
        rag_service = get_rag_service()
        result = rag_service.analyze_qiraat(
            surah_id=request.surah_id,
            ayah_id=request.ayah_id,
            verse_text=request.verse_text
        )
        return AIResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error in analyze_qiraat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare-tafsir", response_model=AIResponse)
async def compare_tafsir(request: TafsirComparisonRequest):
    """
    مقارنة التفاسير المختلفة

    Compare different tafsir interpretations of a verse,
    highlighting agreements and differences between scholars.
    """
    try:
        rag_service = get_rag_service()
        result = rag_service.compare_tafsir(
            surah_id=request.surah_id,
            ayah_id=request.ayah_id,
            verse_text=request.verse_text,
            tafsir_ids=request.tafsir_ids
        )
        return AIResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error in compare_tafsir: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-mutashabihat", response_model=AIResponse)
async def analyze_mutashabihat(request: MutashabihatAnalysisRequest):
    """
    تحليل المتشابهات

    Analyze similar verses (mutashabihat) using AI,
    explaining similarities, differences, and context.
    """
    try:
        rag_service = get_rag_service()
        result = rag_service.analyze_mutashabihat(
            surah_id=request.surah_id,
            ayah_id=request.ayah_id,
            verse_text=request.verse_text,
            similar_verses=request.similar_verses
        )
        return AIResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error in analyze_mutashabihat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# المساعدة في حفظ القرآن الكريم - Hifz Assistant
# =============================================================================

# Comprehensive Hifz prompts based on best practices research
HIFZ_PROMPTS = {
    "general": """أنت مساعد متخصص في حفظ القرآن الكريم، تستند إلى أفضل الممارسات والتقنيات المثبتة علمياً.

خبراتك تشمل:
1. **تقنيات الحفظ الفعالة**: طريقة التكرار (20 مرة)، طريقة 3×3، طريقة 6-4-4-6
2. **التعامل مع المتشابهات**: تحديد الآيات المتشابهة وتقنيات التمييز بينها
3. **جداول المراجعة**: نظام المراجعة الثلاثي (يومي، أسبوعي، شهري)
4. **التكرار المتباعد (Spaced Repetition)**: جدولة المراجعة على فترات متزايدة
5. **أفضل أوقات الحفظ**: بعد الفجر مباشرة
6. **استخدام مصحف واحد**: لتثبيت الذاكرة البصرية

القواعد الذهبية:
- الحفظ الجديد فضة، والمراجعة ذهب
- 20 دقيقة حفظ + 40 دقيقة مراجعة
- لا تنتقل لجديد قبل إتقان السابق
- التسميع على شخص متقن ضروري""",

    "mutashabihat_hifz": """أنت متخصص في علم المتشابهات لمساعدة حفاظ القرآن الكريم.

تقنيات التمييز بين المتشابهات:
1. **تقنية الأنماط العكسية**: ملاحظة ترتيب الكلمات المختلف
2. **تقنية الحروف الأولى (Mnemonics)**: صنع كلمات من الحروف الأولى للتمييز
3. **تقنية النهايات**: التركيز على اختلاف نهايات الآيات
4. **تقنية المذكر والمؤنث**: عادة المذكر أولاً ثم المؤنث
5. **تقنية موقع الصفحة**: الآيات المتشابهة في مواقع محددة
6. **تقنية الربط السياقي**: فهم سياق كل آية للتمييز
7. **تقنية الكتابة**: كتابة الآيات المتشابهة للتثبيت

نصيحة مهمة: سجل الآيات المتشابهة في دفتر خاص مع ملاحظات الفروق.""",

    "revision_plan": """أنت خبير في وضع جداول مراجعة القرآن الكريم.

نظام المراجعة الثلاثي الفعال:

**المستوى الأول - المراجعة اليومية:**
- الأجزاء الأخيرة (1-3 أجزاء) تُراجع يومياً
- بعد صلاة الفجر مباشرة
- التكرار 5 مرات من الحفظ

**المستوى الثاني - المراجعة الأسبوعية:**
- الأجزاء المحفوظة منذ أسابيع/أشهر
- توزيع 1.5-2 جزء يومياً
- مراجعة منتظمة على مدار الأسبوع

**المستوى الثالث - المراجعة الشهرية:**
- ختمة كاملة من الحفظ كل شهر
- جزء واحد يومياً تقريباً
- للأجزاء القديمة (أكثر من 6 أشهر)

**جدول 90 يوم المكثف:**
- 7-8 صفحات يومياً
- 4 ختمات سنوياً
- مناسب للحفاظ المتمكنين

**التكرار المتباعد:**
- اليوم 0: حفظ جديد
- اليوم 1: مراجعة
- اليوم 3: مراجعة
- اليوم 7: مراجعة
- اليوم 14: مراجعة
- اليوم 30: مراجعة""",

    "memorization_tips": """أنت مدرب حفظ القرآن الكريم، تقدم نصائح عملية مبنية على أفضل الممارسات.

**تقنيات الحفظ المثبتة:**

1. **طريقة التكرار العشريني:**
   - تكرار الآية 20 مرة نظراً
   - تكرار من الحفظ 20 مرة
   - ربط كل 4 آيات معاً

2. **طريقة 6-4-4-6:**
   - قراءة الآية 6 مرات من المصحف
   - تسميع 4 مرات من الحفظ
   - قراءة 4 مرات من المصحف
   - تسميع 6 مرات من الحفظ

3. **طريقة الكتابة (الموريتانية):**
   - كتابة الآيات قبل البدء بالحفظ
   - تساعد على ملاحظة كل حرف وحركة

4. **نصائح ذهبية:**
   - استخدم مصحفاً واحداً (يفضل مصحف المدينة)
   - احفظ بصوت مرتفع
   - التغني بنغمة ثابتة
   - الحفظ بعد الفجر مباشرة
   - لا تتجاوز 5 آيات في الجلسة الواحدة للمبتدئين

5. **للمشغولين:**
   - جلسات قصيرة 10-15 دقيقة
   - استغلال أوقات التنقل
   - المراجعة قبل النوم
   - الربط بالصلوات الخمس""",

    "verse_distinction": """أنت متخصص في مساعدة الحفاظ على التمييز بين الآيات المتشابهة.

عند تحليل آيتين متشابهتين، قدم:

1. **التشابه اللفظي**: حدد الكلمات والعبارات المشتركة
2. **الاختلافات الدقيقة**: كل كلمة مختلفة وموقعها
3. **السياق القرآني**: موضوع كل سورة وسبب الاختلاف
4. **تقنية التمييز المقترحة**: أفضل طريقة للتفريق
5. **جملة مساعدة للحفظ**: عبارة سهلة للتذكر

مثال للتحليل:
- آية البقرة 14: "وَإِذَا خَلَوْا إِلَى شَيَاطِينِهِمْ" → المنافقون مع شياطينهم
- آية البقرة 76: "وَإِذَا خَلَا بَعْضُهُمْ إِلَى بَعْضٍ" → اليهود مع بعضهم

**نصيحة الحفظ:** "شياطين" في الآية الأولى (14) لأنها تتحدث عن المنافقين الذين يتبعون الشياطين، بينما "بعضهم" في الآية الثانية (76) لأنها عن اليهود يتشاورون فيما بينهم."""
}


@router.post("/hifz-assistant", response_model=AIResponse)
async def hifz_assistant(request: HifzAssistantRequest):
    """
    المساعدة في حفظ القرآن الكريم

    AI-powered Quran memorization assistant providing:
    - Memorization techniques (تقنيات الحفظ)
    - Mutashabihat analysis for memorization (المتشابهات للحفظ)
    - Revision schedules (جداول المراجعة)
    - Tips for distinguishing similar verses (التمييز بين الآيات)
    - Spaced repetition plans (التكرار المتباعد)
    """
    try:
        from openai import AzureOpenAI
        from src.ai.config import azure_config

        # Get mutashabihat context if verse specified
        context_parts = []
        sources = []

        if request.surah_id and request.ayah_id:
            verse_key = f"{request.surah_id}:{request.ayah_id}"
            mutashabihat_context, mutashabihat_sources = _get_mutashabihat_data(verse_key)
            if mutashabihat_context:
                context_parts.append(mutashabihat_context)
                sources.extend(mutashabihat_sources)

        # Build personalized context
        user_context = []
        if request.juz_memorized:
            user_context.append(f"عدد الأجزاء المحفوظة: {request.juz_memorized}")
        if request.daily_time_minutes:
            user_context.append(f"الوقت المتاح يومياً: {request.daily_time_minutes} دقيقة")

        # Select appropriate prompt based on mode
        base_prompt = HIFZ_PROMPTS.get(request.mode, HIFZ_PROMPTS["general"])

        # Build full prompt
        full_prompt = f"""{base_prompt}

{"معلومات عن الطالب:" + chr(10) + chr(10).join(user_context) if user_context else ""}

{"السياق:" + chr(10) + chr(10).join(context_parts) if context_parts else ""}

السؤال: {request.question}

قدم إجابة مفصلة وعملية تساعد في الحفظ والمراجعة. استخدم التنسيق بالعناوين والنقاط للوضوح."""

        # Call Azure OpenAI
        client = AzureOpenAI(
            azure_endpoint=azure_config.endpoint,
            api_key=azure_config.api_key,
            api_version=azure_config.api_version,
            timeout=60.0
        )

        response = client.chat.completions.create(
            model=azure_config.chat_deployment,
            messages=[{"role": "system", "content": full_prompt}],
            temperature=0.7,
            max_tokens=2000
        )

        answer = response.choices[0].message.content + AI_DISCLAIMER

        return AIResponse(
            success=True,
            data={
                "answer": answer,
                "mode": request.mode,
                "sources": sources,
                "tips": _get_quick_hifz_tips(request.mode),
                "tokens_used": response.usage.total_tokens
            }
        )

    except Exception as e:
        logger.error(f"Error in hifz_assistant: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hifz-assistant/stream")
async def hifz_assistant_stream(request: HifzAssistantRequest):
    """
    المساعدة في حفظ القرآن الكريم - بث مباشر

    Streaming version of the Hifz assistant for real-time responses.
    """
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            from openai import AzureOpenAI
            from src.ai.config import azure_config

            # Get mutashabihat context if verse specified
            context_parts = []
            sources = []

            if request.surah_id and request.ayah_id:
                verse_key = f"{request.surah_id}:{request.ayah_id}"
                mutashabihat_context, mutashabihat_sources = _get_mutashabihat_data(verse_key)
                if mutashabihat_context:
                    context_parts.append(mutashabihat_context)
                    sources.extend(mutashabihat_sources)

            # Build personalized context
            user_context = []
            if request.juz_memorized:
                user_context.append(f"عدد الأجزاء المحفوظة: {request.juz_memorized}")
            if request.daily_time_minutes:
                user_context.append(f"الوقت المتاح يومياً: {request.daily_time_minutes} دقيقة")

            # Select appropriate prompt
            base_prompt = HIFZ_PROMPTS.get(request.mode, HIFZ_PROMPTS["general"])

            full_prompt = f"""{base_prompt}

{"معلومات عن الطالب:" + chr(10) + chr(10).join(user_context) if user_context else ""}

{"السياق:" + chr(10) + chr(10).join(context_parts) if context_parts else ""}

السؤال: {request.question}

قدم إجابة مفصلة وعملية تساعد في الحفظ والمراجعة."""

            # Send sources first
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'mode': request.mode})}\n\n"

            # Stream response
            client = AzureOpenAI(
                azure_endpoint=azure_config.endpoint,
                api_key=azure_config.api_key,
                api_version=azure_config.api_version,
                timeout=60.0
            )

            stream = client.chat.completions.create(
                model=azure_config.chat_deployment,
                messages=[{"role": "system", "content": full_prompt}],
                temperature=0.7,
                max_tokens=2000,
                stream=True
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

            # Append beta disclaimer
            yield f"data: {json.dumps({'type': 'content', 'content': AI_DISCLAIMER})}\n\n"

            # Send tips at the end
            tips = _get_quick_hifz_tips(request.mode)
            yield f"data: {json.dumps({'type': 'tips', 'tips': tips})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Error in hifz_assistant_stream: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


def _get_quick_hifz_tips(mode: str) -> List[str]:
    """Get quick tips based on the mode"""
    tips_map = {
        "general": [
            "احفظ بعد صلاة الفجر - أفضل وقت للحفظ",
            "استخدم مصحفاً واحداً لتثبيت الذاكرة البصرية",
            "كرر الآية 20 مرة على الأقل",
            "لا تنتقل لجديد قبل إتقان السابق"
        ],
        "mutashabihat_hifz": [
            "سجل المتشابهات في دفتر خاص",
            "ركز على الكلمات المختلفة بين الآيات",
            "افهم سياق كل آية للتمييز",
            "استخدم تقنية الحروف الأولى للتذكر"
        ],
        "revision_plan": [
            "20 دقيقة حفظ + 40 دقيقة مراجعة",
            "راجع الجديد يومياً، والقديم أسبوعياً",
            "اختم من الحفظ مرة كل شهر",
            "اربط المراجعة بالصلوات الخمس"
        ],
        "memorization_tips": [
            "احفظ بصوت مرتفع",
            "التغني يساعد على الحفظ",
            "اكتب الآيات لتثبيتها",
            "5 آيات كحد أقصى للمبتدئين"
        ],
        "verse_distinction": [
            "ركز على نهايات الآيات المختلفة",
            "افهم موضوع كل سورة",
            "لاحظ الكلمات الفارقة",
            "اربط الآية بسياقها"
        ]
    }
    return tips_map.get(mode, tips_map["general"])


@router.post("/search", response_model=AIResponse)
async def semantic_search(request: SemanticSearchRequest):
    """
    البحث الدلالي في القرآن

    Perform semantic search across Quranic content
    including verses, tafsir, and qiraat.
    """
    try:
        rag_service = get_rag_service()
        result = rag_service.semantic_search(
            query=request.query,
            search_type=request.search_type,
            limit=request.limit,
            surah_filter=request.surah_filter
        )
        return AIResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error in semantic_search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def semantic_search_get(
    q: str = Query(..., min_length=2, description="استعلام البحث"),
    type: str = Query(default="all", description="نوع البحث"),
    limit: int = Query(default=10, ge=1, le=50),
    surah: Optional[int] = Query(default=None, ge=1, le=114)
):
    """
    البحث الدلالي (GET)

    GET endpoint for semantic search - useful for browser navigation.
    """
    try:
        rag_service = get_rag_service()
        result = rag_service.semantic_search(
            query=q,
            search_type=type,
            limit=limit,
            surah_filter=surah
        )
        return AIResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error in semantic_search_get: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", response_model=AIResponse)
async def chat(request: ChatRequest):
    """
    محادثة ذكية عن القرآن

    Multi-turn chat interface with Quranic context.
    Maintains conversation history for follow-up questions.
    """
    try:
        rag_service = get_rag_service()
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        result = rag_service.chat(
            messages=messages,
            include_context=request.include_context
        )
        return AIResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def ai_health():
    """
    فحص حالة خدمات الذكاء الاصطناعي

    Check health status of AI services (Qdrant, Azure OpenAI).
    Fast check - only verifies config, minimal external calls.
    """
    import httpx

    health = {
        "qdrant": False,
        "azure_openai": False,
        "qdrant_url": None
    }

    # Check Azure OpenAI config (no API call - just verify credentials exist)
    try:
        from src.ai.config import azure_config
        health["azure_openai"] = bool(azure_config.endpoint and azure_config.api_key)
        health["azure_endpoint"] = azure_config.endpoint[:30] + "..." if azure_config.endpoint else None
    except Exception as e:
        health["azure_openai_error"] = str(e)

    # Check Qdrant connectivity via simple HTTP call (not using qdrant-client)
    try:
        from src.ai.config import qdrant_config
        qdrant_url = qdrant_config.url
        health["qdrant_url"] = qdrant_url
        if qdrant_url:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{qdrant_url}/collections")
                if resp.status_code == 200:
                    data = resp.json()
                    health["qdrant"] = True
                    health["collections"] = [c["name"] for c in data.get("result", {}).get("collections", [])]
    except Exception as e:
        health["qdrant_error"] = str(e)

    return {
        "status": "healthy" if all([health["qdrant"], health["azure_openai"]]) else "degraded",
        "services": health
    }


@router.get("/stats")
async def ai_stats():
    """
    إحصائيات خدمات الذكاء الاصطناعي

    Get statistics about AI services and indexed content.
    """
    try:
        from src.ai.services.qdrant_service import get_qdrant_service
        qdrant = get_qdrant_service()
        collections = qdrant.get_all_collections_stats()

        total_vectors = sum(
            c.get("vectors_count", 0) or 0
            for c in collections.values()
            if isinstance(c, dict) and "error" not in c
        )

        return {
            "total_vectors": total_vectors,
            "collections": collections,
            "embedding_model": "text-embedding-3-large",
            "chat_model": "gpt-4o",
            "vector_dimensions": 3072
        }
    except Exception as e:
        logger.error(f"Error getting AI stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initialize")
async def initialize_collections():
    """
    تهيئة مجموعات Qdrant

    Initialize Qdrant collections for storing vectors.
    Should be called once during setup.
    """
    try:
        from src.ai.services.qdrant_service import get_qdrant_service
        qdrant = get_qdrant_service()
        qdrant.initialize_collections()
        return {
            "success": True,
            "message": "Collections initialized successfully",
            "collections": qdrant.get_all_collections_stats()
        }
    except Exception as e:
        logger.error(f"Error initializing collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))
