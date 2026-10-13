import httpx
import logging
import json
from typing import List, Dict, Any, Tuple
from app.config import settings
from app.services.rag_service import RAGService
from app.services.crop_doctor import CropDoctorFlow
from app.schemas.schemas import SourceCitation

logger = logging.getLogger(__name__)

# Intent detector keywords
INTENT_PATTERNS = {
    "crop_doctor": ["disease", "pest", "worm", "fungus", "yellow", "curl", "blight", "spots", "wilt", "कीड", "रोग", "अळी", "पिवळे", "मुरझाई", "धब्बा", "बोंडअळी"],
    "fertilizer": ["fertilizer", "urea", "dap", "npk", "potash", "manure", "vermicompost", "खत", "युरिया", "खाद", "गोबर", "कंपोस्ट"],
    "irrigation": ["irrigation", "water", "drip", "sprinkler", "flood", "सिंचन", "पाणी", "ठिबक", "तुषार", "सिंचाई"],
    "weather": ["weather", "rain", "temperature", "forecast", "cloud", "पाऊस", "हवामान", "तापमान", "मौसम", "बारिश"],
    "market_prices": ["price", "rate", "mandi", "apmc", "market", "bhav", "दर", "बाजारभाव", "मंडी", "भाव", "किंमत"],
    "schemes": ["scheme", "subsidy", "pm kisan", "pmfby", "fasal bima", "yojana", "योजना", "अनुदान", "विमा", "सब्सिडी", "कर्ज"],
    "crop_planning": ["sow", "rotation", "season", "kharif", "rabi", "zaid", "पेरणी", "हंगाम", "नियोजन", "फसल चक्र"]
}

class AIService:
    @staticmethod
    def detect_intent(text: str) -> str:
        text_lower = text.lower()
        for intent, keywords in INTENT_PATTERNS.items():
            if any(kw in text_lower for kw in keywords):
                return intent
        return "general_agriculture"

    @staticmethod
    def build_system_prompt(
        language: str,
        district: str = "Maharashtra",
        rag_context: str = "",
        intent: str = "general_agriculture"
    ) -> str:
        lang_directives = {
            "Marathi": "मराठी भाषेत संपूर्ण उत्तर द्या. भाषा सोपी, शेतकऱ्याला समजेल अशी आणि सन्मानपूर्वक असावी.",
            "Hindi": "हिंदी भाषा में पूरा उत्तर दें। भाषा सरल, व्यावहारिक और किसान-सुलभ होनी चाहिए।",
            "English": "Respond entirely in clear, simple English accessible to rural farmers.",
            "Punjabi": "ਪੰਜਾਬੀ ਵਿੱਚ ਪੂਰਾ ਜਵਾਬ ਦਿਓ।",
            "Tamil": "தமிழில் பதில் அளிக்கவும்.",
            "Telugu": "తెలుగులో సమాధానం ఇవ్వండి.",
            "Kannada": "ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ.",
            "Bengali": "বাংলায় উত্তর দিন।",
            "Gujarati": "ગુજરાતીમાં જવાબ આપો.",
            "Urdu": "اردو میں جواب دیں۔"
        }

        lang_rule = lang_directives.get(language, f"Respond entirely in {language}.")

        base_prompt = f"""You are KrushiMitra AI (कृषीमित्र AI), an elite agricultural advisor, agronomist, and farmer companion in India.
Current Farmer Region: {district}, India.
Selected Language: {language}.
{lang_rule}

CORE PRINCIPLES:
1. Act as a trusted agricultural scientist and field expert, NOT a generic conversational bot.
2. Maintain context across multiple conversation turns without asking the farmer to repeat information already shared.
3. Distinguish confirmed facts from possible causes and uncertain estimates.
4. Give practical, numbered steps using simple farming terminology.
5. Explain WHY each recommendation helps so the farmer learns the principle.
6. When recommending chemical applications or high-risk treatments:
   - Provide exact dosages per liter of water and per acre only when standard university packages of practices (PoP) support it.
   - Always state safety precautions (gloves, wind direction, mask, pre-harvest interval).
   - For severe epidemics or uncertain crop damage, advise immediate physical consultation with the local Taluka Krishi Adhikari or Krishi Vigyan Kendra (KVK).
7. Never fabricate sources, market rates, or government subsidies.

RESPONSE FORMAT GUIDELINES:
- For general agricultural questions: Provide a direct, concise, and structured explanation.
- For crop problems (diseases, pests, leaf spots, wilting):
  Structure your reply with these bold section headers (translated to {language}):
  **Your problem:** [Short 1-2 sentence factual summary]
  **Possible causes:** [Ranked by plausibility based on available evidence]
  **What to do now:**
  1. [Immediate low-risk practical action]
  2. [Organic or cultural treatment]
  3. [Next curative step or certified chemical spray with dosage]
  **What to avoid:** [Key mistakes, e.g., excessive urea, spraying in hot sun or high wind]
  **One follow-up question:** [Ask the single most useful unanswered question to narrow diagnosis]
  **Sources:** [Mention cited university / ICAR / department source]

VERIFIED AGRICULTURAL KNOWLEDGE BASE:
{rag_context if rag_context else "Use established ICAR and State Agricultural University (MPKV, PDKV, VNMKV) guidelines."}
"""
        return base_prompt

    @staticmethod
    async def generate_response(
        query: str,
        conversation_history: List[Dict[str, str]],
        language: str = "English",
        district: str = "Maharashtra"
    ) -> Tuple[str, str, List[SourceCitation], List[str]]:
        """
        Coordinates RAG retrieval, crop doctor context extraction,
        and LLM completion with fallback resilience.
        """
        intent = AIService.detect_intent(query)
        crop_context = CropDoctorFlow.extract_context(query, conversation_history)

        # Retrieve relevant RAG documents
        search_terms = f"{crop_context.get('crop') or ''} {query}".strip()
        rag_docs = RAGService.search(search_terms, crop=crop_context.get("crop"), limit=3)
        citations = RAGService.format_citations(rag_docs)

        # Prepare RAG text for prompt
        rag_text = ""
        for i, doc in enumerate(rag_docs, 1):
            rag_text += f"\n--- Source {i} ({doc['source_name']}) ---\nTitle: {doc['title']}\nSummary: {doc['summary']}\nGuidance: {doc['content']}\n"

        # Check missing crop details if it's a crop doctor query
        missing_params, follow_up_q = CropDoctorFlow.check_missing_parameters(crop_context, lang=language)
        follow_ups = [follow_up_q] if follow_up_q else []

        system_prompt = AIService.build_system_prompt(
            language=language,
            district=district,
            rag_context=rag_text,
            intent=intent
        )

        # Format conversation messages for LLM
        messages = [{"role": "system", "content": system_prompt}]
        for m in conversation_history[-10:]:
            messages.append({"role": m["role"], "content": m["content"]})
        # Add current query
        messages.append({"role": "user", "content": query})

        # Call AI Provider
        reply = None
        if settings.GROQ_API_KEY:
            candidate_models = settings.get_groq_models()
            for model_name in candidate_models:
                try:
                    headers = {
                        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": model_name,
                        "max_tokens": 1500,
                        "temperature": 0.4,
                        "messages": messages
                    }
                    async with httpx.AsyncClient(timeout=20.0) as client:
                        resp = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                        if resp.status_code == 200:
                            data = resp.json()
                            reply = data["choices"][0]["message"]["content"]
                            break
                        else:
                            logger.warning(f"Groq API model {model_name} error {resp.status_code}: {resp.text}")
                except Exception as e:
                    logger.error(f"Error calling Groq API model {model_name}: {e}")

        # Fallback Agricultural Rule Engine if external API fails or is offline
        if not reply:
            reply = AIService._generate_heuristic_response(
                query=query,
                intent=intent,
                crop_context=crop_context,
                rag_docs=rag_docs,
                language=language
            )

        return reply, intent, citations, follow_ups

    @staticmethod
    def _generate_heuristic_response(
        query: str,
        intent: str,
        crop_context: Dict[str, Any],
        rag_docs: List[Dict[str, Any]],
        language: str
    ) -> str:
        """
        Guaranteed response engine using verified RAG documents and agronomic rules.
        Ensures the application NEVER crashes or fails to respond even in offline/demo mode.
        """
        crop = crop_context.get("crop") or "crop"
        
        # If RAG found verified matching document
        if rag_docs:
            doc = rag_docs[0]
            if language == "Marathi":
                return (
                    f"**आपली समस्या:** {doc['title']} संबंधित शेती सल्ला.\n\n"
                    f"**संभाव्य कारणे व विश्लेषण:**\n{doc['summary']}\n\n"
                    f"**आता काय करावे:**\n"
                    f"1. **तातडीची कृती:** {doc['content'][:250]}...\n"
                    f"2. **सेंद्रिय उपाय:** ५% निंबोळी अर्क (NSKE) किंवा ट्रायकोडर्मा जैविक बुरशीनाशकाचा वापर करा.\n"
                    f"3. **पुढील पायरी:** लक्षणे जास्त असल्यास स्थानिक कृषी विज्ञान केंद्र (KVK) किंवा तालुका कृषी अधिकाऱ्यांशी संपर्क साधा.\n\n"
                    f"**काय टाळावे:** भर उन्हात किंवा सोसाट्याच्या वाऱ्यात रासायनिक फवारणी करू नका.\n\n"
                    f"**महत्त्वाचा प्रश्न:** पिकावर ही लक्षणे नेमकी किती दिवसांपासून दिसत आहेत?\n\n"
                    f"**संदर्भ:** {doc['source_name']} ({doc.get('publication_date', '2024')})"
                )
            elif language == "Hindi":
                return (
                    f"**आपकी समस्या:** {doc['title']} से संबंधित कृषि मार्गदर्शन।\n\n"
                    f"**संभाव्य कारण और विश्लेषण:**\n{doc['summary']}\n\n"
                    f"**अभी क्या करें:**\n"
                    f"1. **तत्काल कदम:** {doc['content'][:250]}...\n"
                    f"2. **जैविक उपचार:** 5% नीम का काढ़ा (NSKE) या जैविक ट्राइकोडर्मा का छिड़काव करें।\n"
                    f"3. **अगला कदम:** अधिक संक्रमण होने पर नजदीकी कृषि विज्ञान केंद्र (KVK) से संपर्क करें।\n\n"
                    f"**क्या न करें:** तेज हवा या बारिश के दौरान कीटनाशक छिड़काव न करें।\n\n"
                    f"**फॉलो-अप सवाल:** यह समस्या खेत के कितने हिस्से में फैली हुई है?\n\n"
                    f"**संदर्भ:** {doc['source_name']}"
                )
            else:
                return (
                    f"**Your problem:** Management guidelines for {doc['title']}.\n\n"
                    f"**Possible causes & assessment:**\n{doc['summary']}\n\n"
                    f"**What to do now:**\n"
                    f"1. **Immediate action:** {doc['content'][:250]}...\n"
                    f"2. **Organic remedy:** Apply 5% Neem Seed Kernel Extract (NSKE) @ 5 ml/L water.\n"
                    f"3. **Inspection step:** Monitor field boundaries and sticky traps regularly.\n\n"
                    f"**What to avoid:** Do not spray chemical pesticides during midday heat (>34°C) or in high winds.\n\n"
                    f"**One follow-up question:** How many days ago did you first observe these symptoms on the crop?\n\n"
                    f"**Sources:** {doc['source_name']} (Published: {doc.get('publication_date', '2024')})"
                )

        # Default structured fallback
        if language == "Marathi":
            return (
                f"**आपली समस्या:** {crop} पिकाबाबत शेती सल्ला.\n\n"
                f"**संभाव्य कारणे:** अन्नद्रव्यांची कमतरता, बुरशीजन्य प्रादुर्भाव किंवा रसशोषक किडींचा प्रादुर्भाव असण्याची शक्यता आहे.\n\n"
                f"**आता काय करावे:**\n"
                f"1. बाधित झाडांचे बारकाईने निरीक्षण करा आणि पानांच्या मागील बाजूस किडी आहेत का ते तपासा.\n"
                f"2. सुरक्षेसाठी ५% निंबोळी अर्क (NSKE) ५ मिली प्रति लिटर पाण्यात मिसळून प्रतिबंधात्मक फवारणी करा.\n"
                f"3. शेतात जास्त पाणी साचले असल्यास पाण्याचा निचरा करा.\n\n"
                f"**काय टाळावे:** योग्य निदानाशिवाय लगेच महागडी रासायनिक कीटकनाशके फवारू नका.\n\n"
                f"**महत्त्वाचा प्रश्न:** आपल्या पिकाचे वय किती आहे आणि पिवळेपणा जुन्या पानांवर आहे की नवीन पानांवर?\n\n"
                f"**संदर्भ:** भारतीय कृषी संशोधन परिषद (ICAR) व म.फु.कृ.वि. राहुरी शिफारसी."
            )
        elif language == "Hindi":
            return (
                f"**आपकी समस्या:** {crop} की फसल से संबंधित परामर्श।\n\n"
                f"**संभाव्य कारण:** पोषक तत्वों की कमी, फफूंद जनित रोग या रस चूसक कीटों का प्रकोप हो सकता है।\n\n"
                f"**अभी क्या करें:**\n"
                f"1. प्रभावित पौधों की पत्तियों के नीचे कीट या जाले की जांच करें।\n"
                f"2. नीम तेल (1500 ppm) 5 मिली प्रति लीटर पानी में मिलाकर प्राथमिक छिड़काव करें।\n"
                f"3. खेत में जलभराव की स्थिति न बनने दें, जल निकासी सुनिश्चित करें।\n\n"
                f"**क्या न करें:** बिना उचित पहचान के भारी रासायनिक कीटनाशकों का अंधाधुंध उपयोग न करें।\n\n"
                f"**फॉलो-अप सवाल:** फसल किस अवस्था में है (वृद्धि, फूल या फल) और खेत का कितना हिस्सा प्रभावित है?\n\n"
                f"**संदर्भ:** ICAR एवं राज्य कृषि विश्वविद्यालय दिशा-निर्देश।"
            )
        else:
            return (
                f"**Your problem:** Consultation regarding {crop} crop health.\n\n"
                f"**Possible causes:** Nutrient deficiency (such as Nitrogen or Zinc), early fungal infection, or sap-sucking insect pests.\n\n"
                f"**What to do now:**\n"
                f"1. Inspect the underside of leaves for small sucking pests like aphids, thrips, or whiteflies.\n"
                f"2. Apply a low-risk preventive spray of 5% Neem Seed Kernel Extract (NSKE) or Neem Oil @ 5 ml/L.\n"
                f"3. Ensure proper soil aeration and avoid waterlogging around the root zone.\n\n"
                f"**What to avoid:** Avoid applying excess chemical Nitrogen (Urea) without balanced Potassium and Phosphorus.\n\n"
                f"**One follow-up question:** Are the yellow/affected symptoms appearing on older bottom leaves or on young top shoots?\n\n"
                f"**Sources:** ICAR & State Agricultural University Integrated Crop Management Guidelines."
            )
