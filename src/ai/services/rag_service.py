"""
RAG (Retrieval Augmented Generation) Service
Combines Qdrant vector search with Azure OpenAI GPT-4o for intelligent Q&A
"""

import logging
import re
from typing import List, Dict, Any, Optional
from openai import AzureOpenAI
from .embedding_service import get_embedding_service, EmbeddingService
from .qdrant_service import get_qdrant_service, QdrantService
from ..config import azure_config, rag_config, SYSTEM_PROMPTS

logger = logging.getLogger(__name__)

# Beta disclaimer to append to all AI responses
AI_DISCLAIMER = """

---
**تنبيه هام:** هذه النسخة التجريبية (Beta). والله أعلم، واستشر شيخاً وعالماً للتأكد من المعلومات الشرعية."""


def get_mutashabihat_service():
    """Get the mutashabihat service for local data."""
    try:
        from src.services.mutashabihat_service import get_mutashabihat_service as _get_service
        return _get_service()
    except ImportError:
        logger.warning("Mutashabihat service not available")
        return None


class RAGService:
    """
    RAG Service for Quranic Q&A and analysis.
    Retrieves relevant context from Qdrant and generates responses using GPT-4o.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService = None,
        qdrant_service: QdrantService = None
    ):
        self.embedding_service = embedding_service or get_embedding_service()
        self.qdrant_service = qdrant_service or get_qdrant_service()
        self.client = AzureOpenAI(
            azure_endpoint=azure_config.endpoint,
            api_key=azure_config.api_key,
            api_version=azure_config.api_version,
            timeout=60.0  # 60 second timeout for chat
        )
        self.chat_deployment = azure_config.chat_deployment

    def _is_mutashabihat_question(self, question: str) -> tuple:
        """
        Check if the question is about mutashabihat and extract verse reference if present.
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
        # Map of Arabic surah names to numbers
        surah_names = {
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

        # Try to find surah name and ayah number
        for surah_name, surah_num in surah_names.items():
            if surah_name in question:
                # Look for ayah number near the surah name
                # Patterns: "الآية 14", "آية 14", "الايه 14", "ايه 14", just number
                ayah_patterns = [
                    rf'(?:الآية|آية|الايه|ايه|اية|الاية)\s*(\d+)',  # الآية 14
                    rf'(\d+)\s*(?:من\s*)?(?:سورة\s*)?{surah_name}',  # 14 سورة البقرة
                    rf'{surah_name}\s*(?:الآية|آية|الايه|ايه|اية)?\s*(\d+)',  # البقرة آية 14 or البقرة 14
                ]

                for pattern in ayah_patterns:
                    ayah_match = re.search(pattern, question)
                    if ayah_match:
                        ayah_num = ayah_match.group(1)
                        verse_key = f"{surah_num}:{ayah_num}"
                        return is_mutashabihat, verse_key

        return is_mutashabihat, verse_key

    def _get_mutashabihat_context(self, verse_key: str) -> tuple:
        """
        Get mutashabihat data for a verse from local service and Quranpedia.
        Returns: (context_string, sources_list)
        """
        try:
            sources = []
            context_parts = []
            similar_verses = []

            # Try local service first (more accurate, curated data)
            mutashabihat_svc = get_mutashabihat_service()
            if mutashabihat_svc:
                result = mutashabihat_svc.get_mutashabihat(verse_key)
                if result.get("success"):
                    source_verse = result.get("source_verse", {})
                    if source_verse:
                        context_parts.append(f"الآية الأصلية ({verse_key}):")
                        context_parts.append(f"  {source_verse.get('text_uthmani', '')}")
                        context_parts.append(f"  سورة {source_verse.get('surah_name_ar', '')}")

                    similar_verses = result.get("similar_verses", [])

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
                            # Extract similar verses from Quranpedia format
                            for item in qp_data:
                                if not item.get("ayahs") or not isinstance(item["ayahs"], list):
                                    continue

                                notes = item.get("notes", "")
                                ayahs_list = item["ayahs"]

                                # Check if source verse is in this group
                                source_in_group = False
                                for ayah_item in ayahs_list:
                                    info = ayah_item.get("info", ayah_item)
                                    check_key = f"{info.get('surah_id', '')}:{info.get('number', '')}"
                                    if check_key == verse_key:
                                        source_in_group = True
                                        break

                                # Skip groups that don't contain the source verse
                                if not source_in_group:
                                    continue

                                # Skip "انفرادات" (unique phrases, not similarities)
                                if "انفرادات" in notes:
                                    continue

                                # Extract other verses from this group
                                for ayah_item in ayahs_list:
                                    info = ayah_item.get("info", ayah_item)
                                    sv_surah = info.get("surah_id", "")
                                    sv_ayah = info.get("number", "")
                                    sv_key = f"{sv_surah}:{sv_ayah}"

                                    # Skip source verse
                                    if sv_key == verse_key:
                                        continue

                                    similar_verses.append({
                                        "verse_key": sv_key,
                                        "text_uthmani": info.get("text", ""),
                                        "notes": notes,
                                        "source": "quranpedia"
                                    })

                            if not context_parts:
                                # Add source verse info from database
                                context_parts.append(f"الآية الأصلية ({verse_key}):")

                except Exception as e:
                    logger.warning(f"Error getting Quranpedia mutashabihat: {e}")

            # Format similar verses
            if similar_verses:
                context_parts.append(f"\nالآيات المتشابهة ({len(similar_verses)} آية):")
                for i, sv in enumerate(similar_verses, 1):
                    sv_key = sv.get("verse_key", "")
                    sv_text = sv.get("text_uthmani", "")
                    sv_surah = sv.get("surah_name_ar", "")
                    sv_notes = sv.get("notes", "")
                    context_parts.append(f"{i}. ({sv_key}) - {sv_surah}:")
                    context_parts.append(f"   {sv_text}")
                    if sv_notes:
                        context_parts.append(f"   ملاحظة: {sv_notes}")
                    sources.append({
                        "type": "mutashabihat",
                        "reference": sv_key,
                        "surah": sv_surah,
                        "source": sv.get("source", "local")
                    })

            return "\n".join(context_parts), sources

        except Exception as e:
            logger.error(f"Error getting mutashabihat context: {e}")
            return "", []

    def answer_question(
        self,
        question: str,
        include_verses: bool = True,
        include_tafsir: bool = True,
        include_qiraat: bool = False,
        surah_filter: int = None,
        language: str = "ar"
    ) -> Dict[str, Any]:
        """
        Answer a question about the Quran using RAG.

        Args:
            question: User's question in Arabic or English
            include_verses: Include verse search in context
            include_tafsir: Include tafsir search in context
            include_qiraat: Include qiraat differences in context
            surah_filter: Optional filter by surah number
            language: Response language (ar, en, both)

        Returns:
            Dict with answer, sources, and metadata
        """
        try:
            # Check if this is a mutashabihat question
            is_mutashabihat, verse_key = self._is_mutashabihat_question(question)

            # Generate embedding for the question
            query_vector = self.embedding_service.get_embedding(question)

            # Retrieve relevant context
            context_parts = []
            sources = []

            # If mutashabihat question with verse reference, get mutashabihat data first
            if is_mutashabihat and verse_key:
                mutashabihat_context, mutashabihat_sources = self._get_mutashabihat_context(verse_key)
                if mutashabihat_context:
                    context_parts.append("بيانات المتشابهات:\n" + mutashabihat_context)
                    sources.extend(mutashabihat_sources)

            if include_verses:
                verses = self.qdrant_service.search_verses(
                    query_vector=query_vector,
                    limit=rag_config.top_k_verses,
                    surah_id=surah_filter
                )
                if verses:
                    verses_context = self._format_verses_context(verses)
                    context_parts.append(verses_context)
                    sources.extend([{
                        "type": "verse",
                        "reference": v["payload"].get("verse_key", ""),
                        "score": v["score"]
                    } for v in verses])

            if include_tafsir:
                tafsir = self.qdrant_service.search_tafsir(
                    query_vector=query_vector,
                    limit=rag_config.top_k_tafsir
                )
                if tafsir:
                    tafsir_context = self._format_tafsir_context(tafsir)
                    context_parts.append(tafsir_context)
                    sources.extend([{
                        "type": "tafsir",
                        "reference": t["payload"].get("tafsir_name", ""),
                        "verse_key": t["payload"].get("verse_key", ""),
                        "score": t["score"]
                    } for t in tafsir])

            if include_qiraat:
                qiraat = self.qdrant_service.search_qiraat(
                    query_vector=query_vector,
                    limit=rag_config.top_k_qiraat,
                    surah_id=surah_filter
                )
                if qiraat:
                    qiraat_context = self._format_qiraat_context(qiraat)
                    context_parts.append(qiraat_context)
                    sources.extend([{
                        "type": "qiraat",
                        "reference": q["payload"].get("verse_key", ""),
                        "score": q["score"]
                    } for q in qiraat])

            # Combine context
            combined_context = "\n\n".join(context_parts) if context_parts else "لا يوجد سياق متاح"

            # Truncate context if too long
            if len(combined_context) > rag_config.max_context_length:
                combined_context = combined_context[:rag_config.max_context_length] + "..."

            # Use special prompt for mutashabihat questions
            if is_mutashabihat and verse_key:
                prompt = f"""أنت متخصص في علم المتشابهات في القرآن الكريم.

مهمتك الإجابة على السؤال التالي باستخدام البيانات المتاحة.

السياق:
{combined_context}

السؤال: {question}

قدم إجابة شاملة تتضمن:
1. تحديد الآيات المتشابهة
2. أوجه التشابه اللفظي
3. الفروق الدقيقة بين الآيات
4. السياق المختلف لكل آية
5. نصائح للتمييز بينها للحفظ

إذا لم تجد آيات متشابهة، اذكر ذلك بوضوح."""
            else:
                prompt = SYSTEM_PROMPTS["general_qa"].format(
                    context=combined_context,
                    question=question
                )

            response = self.client.chat.completions.create(
                model=self.chat_deployment,
                messages=[
                    {"role": "system", "content": prompt}
                ],
                temperature=azure_config.chat_temperature,
                max_tokens=azure_config.chat_max_tokens
            )

            answer = response.choices[0].message.content + AI_DISCLAIMER

            return {
                "answer": answer,
                "sources": sources,
                "question": question,
                "context_used": len(context_parts) > 0,
                "is_mutashabihat_query": is_mutashabihat,
                "tokens_used": {
                    "prompt": response.usage.prompt_tokens,
                    "completion": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
                }
            }

        except Exception as e:
            logger.error(f"Error answering question: {e}")
            raise

    def explain_verse(
        self,
        surah_id: int,
        ayah_id: int,
        verse_text: str = None
    ) -> Dict[str, Any]:
        """
        Provide detailed explanation of a specific verse.

        Args:
            surah_id: Surah number
            ayah_id: Ayah number
            verse_text: Optional verse text (will be fetched if not provided)

        Returns:
            Dict with explanation and metadata
        """
        try:
            verse_key = f"{surah_id}:{ayah_id}"

            # Search for tafsir context for this specific verse
            if verse_text:
                query_vector = self.embedding_service.get_embedding(verse_text)
            else:
                query_vector = self.embedding_service.get_embedding(f"تفسير الآية {verse_key}")

            # Get tafsir for this verse
            tafsir = self.qdrant_service.search_tafsir(
                query_vector=query_vector,
                limit=5,
                verse_key=verse_key
            )

            # Get asbab al-nuzul
            asbab = self.qdrant_service.search_asbab(
                query_vector=query_vector,
                limit=2
            )

            # Format context
            context_parts = []
            sources = []

            if tafsir:
                context_parts.append(self._format_tafsir_context(tafsir))
                sources.extend([{
                    "type": "tafsir",
                    "name": t["payload"].get("tafsir_name", ""),
                    "score": t["score"]
                } for t in tafsir])

            if asbab:
                context_parts.append("أسباب النزول:\n" + "\n".join([
                    a["payload"].get("text", "") for a in asbab
                ]))
                sources.extend([{
                    "type": "asbab",
                    "score": a["score"]
                } for a in asbab])

            combined_context = "\n\n".join(context_parts) if context_parts else ""

            # Get surah name (placeholder - should come from database)
            prompt = SYSTEM_PROMPTS["verse_explanation"].format(
                context=combined_context,
                verse=verse_text or verse_key,
                surah=surah_id,
                ayah=ayah_id
            )

            response = self.client.chat.completions.create(
                model=self.chat_deployment,
                messages=[
                    {"role": "system", "content": prompt}
                ],
                temperature=azure_config.chat_temperature,
                max_tokens=azure_config.chat_max_tokens
            )

            return {
                "explanation": response.choices[0].message.content + AI_DISCLAIMER,
                "verse_key": verse_key,
                "sources": sources,
                "tokens_used": response.usage.total_tokens
            }

        except Exception as e:
            logger.error(f"Error explaining verse: {e}")
            raise

    def analyze_qiraat(
        self,
        surah_id: int,
        ayah_id: int,
        verse_text: str = None
    ) -> Dict[str, Any]:
        """
        Analyze qiraat differences for a specific verse.

        Args:
            surah_id: Surah number
            ayah_id: Ayah number
            verse_text: Optional verse text

        Returns:
            Dict with qiraat analysis
        """
        try:
            verse_key = f"{surah_id}:{ayah_id}"

            query = verse_text or f"القراءات المختلفة للآية {verse_key}"
            query_vector = self.embedding_service.get_embedding(query)

            qiraat = self.qdrant_service.search_qiraat(
                query_vector=query_vector,
                limit=10,
                surah_id=surah_id
            )

            context = self._format_qiraat_context(qiraat) if qiraat else "لا توجد معلومات متاحة"

            prompt = SYSTEM_PROMPTS["qiraat_analysis"].format(
                context=context,
                verse=verse_text or verse_key
            )

            response = self.client.chat.completions.create(
                model=self.chat_deployment,
                messages=[
                    {"role": "system", "content": prompt}
                ],
                temperature=azure_config.chat_temperature,
                max_tokens=azure_config.chat_max_tokens
            )

            return {
                "analysis": response.choices[0].message.content + AI_DISCLAIMER,
                "verse_key": verse_key,
                "qiraat_found": len(qiraat) if qiraat else 0,
                "tokens_used": response.usage.total_tokens
            }

        except Exception as e:
            logger.error(f"Error analyzing qiraat: {e}")
            raise

    def compare_tafsir(
        self,
        surah_id: int,
        ayah_id: int,
        verse_text: str = None,
        tafsir_ids: List[int] = None
    ) -> Dict[str, Any]:
        """
        Compare different tafsir interpretations of a verse.

        Args:
            surah_id: Surah number
            ayah_id: Ayah number
            verse_text: Optional verse text
            tafsir_ids: Optional list of specific tafsir IDs to compare

        Returns:
            Dict with tafsir comparison
        """
        try:
            verse_key = f"{surah_id}:{ayah_id}"

            query = verse_text or f"تفسير الآية {verse_key}"
            query_vector = self.embedding_service.get_embedding(query)

            tafsir = self.qdrant_service.search_tafsir(
                query_vector=query_vector,
                limit=10,
                verse_key=verse_key
            )

            context = self._format_tafsir_context(tafsir) if tafsir else "لا توجد تفاسير متاحة"

            prompt = SYSTEM_PROMPTS["tafsir_comparison"].format(
                context=context,
                verse=verse_text or verse_key
            )

            response = self.client.chat.completions.create(
                model=self.chat_deployment,
                messages=[
                    {"role": "system", "content": prompt}
                ],
                temperature=azure_config.chat_temperature,
                max_tokens=azure_config.chat_max_tokens
            )

            return {
                "comparison": response.choices[0].message.content + AI_DISCLAIMER,
                "verse_key": verse_key,
                "tafsir_count": len(tafsir) if tafsir else 0,
                "tokens_used": response.usage.total_tokens
            }

        except Exception as e:
            logger.error(f"Error comparing tafsir: {e}")
            raise

    def semantic_search(
        self,
        query: str,
        search_type: str = "verses",
        limit: int = 10,
        surah_filter: int = None
    ) -> Dict[str, Any]:
        """
        Perform semantic search across Quranic content.

        Args:
            query: Search query in Arabic or English
            search_type: Type of content to search (verses, tafsir, qiraat, all)
            limit: Maximum results
            surah_filter: Optional surah filter

        Returns:
            Dict with search results
        """
        try:
            query_vector = self.embedding_service.get_embedding(query)
            results = {}

            if search_type in ["verses", "all"]:
                results["verses"] = self.qdrant_service.search_verses(
                    query_vector=query_vector,
                    limit=limit,
                    surah_id=surah_filter
                )

            if search_type in ["tafsir", "all"]:
                results["tafsir"] = self.qdrant_service.search_tafsir(
                    query_vector=query_vector,
                    limit=limit
                )

            if search_type in ["qiraat", "all"]:
                results["qiraat"] = self.qdrant_service.search_qiraat(
                    query_vector=query_vector,
                    limit=limit,
                    surah_id=surah_filter
                )

            return {
                "query": query,
                "search_type": search_type,
                "results": results,
                "total_results": sum(len(v) for v in results.values())
            }

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            raise

    def chat(
        self,
        messages: List[Dict[str, str]],
        include_context: bool = True
    ) -> Dict[str, Any]:
        """
        Multi-turn chat with Quranic context.

        Args:
            messages: List of chat messages [{"role": "user/assistant", "content": "..."}]
            include_context: Whether to retrieve context for the last message

        Returns:
            Dict with response and metadata
        """
        try:
            sources = []

            if include_context and messages:
                # Get context for the last user message
                last_user_msg = None
                for msg in reversed(messages):
                    if msg["role"] == "user":
                        last_user_msg = msg["content"]
                        break

                if last_user_msg:
                    query_vector = self.embedding_service.get_embedding(last_user_msg)

                    # Retrieve relevant context
                    verses = self.qdrant_service.search_verses(
                        query_vector=query_vector,
                        limit=3
                    )
                    tafsir = self.qdrant_service.search_tafsir(
                        query_vector=query_vector,
                        limit=2
                    )

                    context_parts = []
                    if verses:
                        context_parts.append(self._format_verses_context(verses))
                        sources.extend([{"type": "verse", "ref": v["payload"].get("verse_key")} for v in verses])
                    if tafsir:
                        context_parts.append(self._format_tafsir_context(tafsir))

                    if context_parts:
                        context = "\n\n".join(context_parts)
                        system_msg = f"""أنت مساعد ذكي متخصص في علوم القرآن الكريم.
استخدم السياق التالي للإجابة على أسئلة المستخدم:

{context}

قواعد:
- استشهد بالآيات والتفاسير عند الإجابة
- لا تختلق معلومات غير موجودة في السياق
- إذا لم تعرف الإجابة، اعترف بذلك"""
                        messages = [{"role": "system", "content": system_msg}] + messages

            response = self.client.chat.completions.create(
                model=self.chat_deployment,
                messages=messages,
                temperature=azure_config.chat_temperature,
                max_tokens=azure_config.chat_max_tokens
            )

            return {
                "response": response.choices[0].message.content + AI_DISCLAIMER,
                "sources": sources,
                "tokens_used": response.usage.total_tokens
            }

        except Exception as e:
            logger.error(f"Error in chat: {e}")
            raise

    def analyze_mutashabihat(
        self,
        surah_id: int,
        ayah_id: int,
        verse_text: str = None,
        similar_verses: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Analyze similar verses (mutashabihat) using AI.

        Args:
            surah_id: Surah number
            ayah_id: Ayah number
            verse_text: Optional verse text
            similar_verses: Optional list of similar verses from Quranpedia

        Returns:
            Dict with mutashabihat analysis
        """
        try:
            verse_key = f"{surah_id}:{ayah_id}"

            # Build context from similar verses
            context_parts = []

            if verse_text:
                context_parts.append(f"الآية الأصلية ({verse_key}):\n{verse_text}")

            if similar_verses:
                context_parts.append("الآيات المتشابهة:")
                for i, sv in enumerate(similar_verses[:10], 1):
                    sv_key = sv.get('verse_key', sv.get('surah', '') + ':' + str(sv.get('ayah', '')))
                    sv_text = sv.get('text', sv.get('text_uthmani', ''))
                    context_parts.append(f"{i}. ({sv_key}): {sv_text}")

            combined_context = "\n".join(context_parts) if context_parts else "لا توجد بيانات"

            # Create analysis prompt
            prompt = f"""أنت متخصص في علم المتشابهات في القرآن الكريم.

مهمتك تحليل الآيات المتشابهة التالية وتوضيح:
1. أوجه التشابه اللفظي بين الآيات
2. الفروق الدقيقة في الألفاظ والمعاني
3. السياق المختلف لكل آية وأثره في المعنى
4. الحكمة من التشابه والاختلاف
5. نصائح للحفاظ على التمييز بينها

{combined_context}

قدم تحليلاً علمياً مفصلاً ومفيداً للقارئ والحافظ."""

            response = self.client.chat.completions.create(
                model=self.chat_deployment,
                messages=[
                    {"role": "system", "content": prompt}
                ],
                temperature=azure_config.chat_temperature,
                max_tokens=azure_config.chat_max_tokens
            )

            return {
                "analysis": response.choices[0].message.content + AI_DISCLAIMER,
                "verse_key": verse_key,
                "similar_count": len(similar_verses) if similar_verses else 0,
                "tokens_used": response.usage.total_tokens
            }

        except Exception as e:
            logger.error(f"Error analyzing mutashabihat: {e}")
            raise

    def _format_verses_context(self, verses: List[Dict]) -> str:
        """Format verse results for context."""
        lines = ["الآيات ذات الصلة:"]
        for v in verses:
            payload = v.get("payload", {})
            verse_key = payload.get("verse_key", "")
            text_ar = payload.get("text_ar", "")
            surah_name = payload.get("surah_name_ar", "")
            lines.append(f"- {surah_name} ({verse_key}): {text_ar}")
        return "\n".join(lines)

    def _format_tafsir_context(self, tafsir: List[Dict]) -> str:
        """Format tafsir results for context."""
        lines = ["التفاسير:"]
        for t in tafsir:
            payload = t.get("payload", {})
            tafsir_name = payload.get("tafsir_name", "")
            text = payload.get("text", "")
            verse_key = payload.get("verse_key", "")
            lines.append(f"- {tafsir_name} ({verse_key}):\n{text[:500]}...")
        return "\n".join(lines)

    def _format_qiraat_context(self, qiraat: List[Dict]) -> str:
        """Format qiraat results for context."""
        lines = ["فروق القراءات:"]
        for q in qiraat:
            payload = q.get("payload", {})
            verse_key = payload.get("verse_key", "")
            reader = payload.get("reader_name", "")
            text = payload.get("text", "")
            lines.append(f"- {verse_key} ({reader}): {text}")
        return "\n".join(lines)


# Singleton instance
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Get or create singleton RAGService instance."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
