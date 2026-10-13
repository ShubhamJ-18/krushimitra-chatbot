import re
from typing import Dict, Any, List, Tuple

# Crop keyword mapping
CROPS = {
    "cotton": ["cotton", "कापूस", "कापसा", "कपास", "kapas", "kapus"],
    "soybean": ["soybean", "सोयाबीन", "सोया", "soya"],
    "onion": ["onion", "कांदा", "कांद्या", "प्याज", "kanda", "pyaz"],
    "tomato": ["tomato", "टोमॅटो", "टमाटर", "टोमॅट"],
    "wheat": ["wheat", "गहू", "गव्हा", "गेहूं", "gehu", "gahu"],
    "gram": ["gram", "chickpea", "हरभरा", "हरभऱ्या", "चना", "चने", "chana", "harbhara"],
    "sugarcane": ["sugarcane", "ऊस", "उसा", "गन्ना", "गन्ने", "us", "ganna"],
    "pomegranate": ["pomegranate", "डाळिंब", "डाळिंबा", "अनार", "dalimb"],
    "banana": ["banana", "केळी", "केळ्या", "केला", "केले", "keli"],
    "rice": ["rice", "paddy", "भात", "धान", "तांदूळ", "तांदळा", "chawal"]
}

STAGE_KEYWORDS = ["sowing", "germination", "vegetative", "flowering", "boll", "pod", "bulb", "harvest", "पेरणी", "फुलोरा", "गाठ", "कापणी", "फूल", "फल"]
SPREAD_KEYWORDS = ["few plants", "scattered", "patches", "entire field", "whole farm", "काही झाडे", "पूर्ण शेत", "सर्व झाडांवर", "पूरे खेत", "कुछ पौधे"]
RECENT_FACTORS = ["rain", "spray", "fertilizer", "drip", "waterlogged", "पाऊस", "फवारणी", "खत", "सिंचन", "बारिश", "स्प्रे"]

class CropDoctorFlow:
    @staticmethod
    def extract_context(text: str, history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """Scans query and past messages to find known crop consultation parameters."""
        combined_text = (text + " " + " ".join(m.get("content", "") for m in (history or []))).lower()

        extracted = {
            "crop": None,
            "stage": None,
            "symptoms": None,
            "spread": None,
            "recent_actions": None,
            "region": "Maharashtra"
        }

        # Check crops
        for crop_canonical, synonyms in CROPS.items():
            if any(syn in combined_text for syn in synonyms):
                extracted["crop"] = crop_canonical.capitalize()
                break

        # Check stage
        for kw in STAGE_KEYWORDS:
            if kw in combined_text:
                extracted["stage"] = kw
                break

        # Check spread
        for kw in SPREAD_KEYWORDS:
            if kw in combined_text:
                extracted["spread"] = kw
                break

        # Check recent actions
        for kw in RECENT_FACTORS:
            if kw in combined_text:
                extracted["recent_actions"] = kw
                break

        # Common symptom indicators
        symptom_words = ["yellow", "curling", "spots", "rotting", "wilting", "holes", "drying", "बोंडअळी", "पिवळे", "पिवळी", "पिवळ", "वाळणे", "रोग", "कीड", "कीडे", "अळी", "कीड़ा", "पीला", "पीली", "पील", "धब्बे", "डाग", "ठिपके", "सुकणे", "मुरझाना", "सडणे"]
        found_symptoms = [w for w in symptom_words if w in combined_text]
        if found_symptoms:
            extracted["symptoms"] = ", ".join(found_symptoms)

        return extracted

    @staticmethod
    def check_missing_parameters(context: Dict[str, Any], lang: str = "English") -> Tuple[List[str], str]:
        """
        Determines which critical details are missing.
        Returns list of missing parameter keys and 1-2 prioritized follow-up questions.
        """
        missing = []
        questions = []

        if not context.get("crop"):
            missing.append("crop")
            if lang == "Marathi":
                questions.append("कोणत्या पिकावर ही समस्या दिसत आहे? (उदा. सोयाबीन, कापूस, कांदा, टोमॅटो)")
            elif lang == "Hindi":
                questions.append("यह समस्या किस फसल में दिखाई दे रही है? (जैसे सोयाबीन, कपास, प्याज, टमाटर)")
            else:
                questions.append("Which crop is affected? (e.g. Soybean, Cotton, Onion, Tomato)")

        if not context.get("symptoms"):
            missing.append("symptoms")
            if lang == "Marathi":
                questions.append("पानांवर किंवा फळांवर नेमकी काय लक्षणे दिसत आहेत (पिवळे डाग, पाने चुरडणे, कीड)?")
            elif lang == "Hindi":
                questions.append("पत्तियों या तने पर क्या लक्षण दिख रहे हैं (पीलापन, मुड़ना, छेद, फंगस)?")
            else:
                questions.append("What specific symptoms do you observe (yellowing, leaf curl, holes, wilting)?")

        if context.get("crop") and not context.get("stage"):
            missing.append("stage")
            if lang == "Marathi":
                questions.append("पिकाचे वय किती आहे किंवा पीक कोणत्या अवस्थेत आहे (वाढ, फुलोरा, बोंड/शेंगा)?")
            elif lang == "Hindi":
                questions.append("फसल की आयु या अवस्था क्या है (वृद्धि, फूल आने की अवस्था, या फल)?")
            else:
                questions.append("What is the current crop age or growth stage (vegetative, flowering, pod/boll)?")

        if context.get("crop") and not context.get("spread"):
            missing.append("spread")

        # Pick only top 1 or 2 questions so farmer isn't overwhelmed
        top_questions = questions[:2]
        return missing, (top_questions[0] if top_questions else "")

    @staticmethod
    def get_single_follow_up_question(
        crop: str = None,
        symptoms: str = None,
        problem_type: str = None,
        plant_part: str = None,
        spread: str = None,
        timeline: str = None,
        lang: str = "English"
    ) -> Dict[str, Any]:
        """
        Returns only ONE simple multiple-choice question to narrow diagnosis.
        Returns None if information is already sufficient, preventing questionnaire fatigue.
        """
        # If plant part is unknown and symptom is yellowing or spots, ask plant part
        if not plant_part and (problem_type in ["yellow_leaves", "leaf_spots"] or (symptoms and any(w in symptoms.lower() for w in ["yellow", "पिवळे", "पीला", "spots", "डाग", "धब्बे"]))):
            if lang == "Marathi":
                return {
                    "id": "plant_part",
                    "question": "झाडाचा कोणता भाग बाधित आहे?",
                    "options": [
                        {"id": "lower_leaves", "label": "🌿 खालची जुनी पाने"},
                        {"id": "new_leaves", "label": "🌱 वरचे नवीन शेंडे"},
                        {"id": "entire_plant", "label": "🌳 संपूर्ण झाड"},
                        {"id": "not_sure", "label": "❓ माहित नाही"}
                    ]
                }
            elif lang == "Hindi":
                return {
                    "id": "plant_part",
                    "question": "पौधे का कौन सा हिस्सा प्रभावित है?",
                    "options": [
                        {"id": "lower_leaves", "label": "🌿 निचली पुरानी पत्तियां"},
                        {"id": "new_leaves", "label": "🌱 ऊपरी नई पत्तियां"},
                        {"id": "entire_plant", "label": "🌳 पूरा पौधा"},
                        {"id": "not_sure", "label": "❓ पता नहीं"}
                    ]
                }
            else:
                return {
                    "id": "plant_part",
                    "question": "Which part of the plant is affected?",
                    "options": [
                        {"id": "lower_leaves", "label": "🌿 Lower older leaves"},
                        {"id": "new_leaves", "label": "🌱 Upper new shoots"},
                        {"id": "entire_plant", "label": "🌳 Entire plant"},
                        {"id": "not_sure", "label": "❓ Not sure"}
                    ]
                }

        # If spread is unknown and problem is wilting or pest epidemic, ask spread
        if not spread and (problem_type in ["wilting", "pests"] or (symptoms and any(w in symptoms.lower() for w in ["wilt", "सुकणे", "मुरझाना", "अळी", "कीड", "कीड़ा"]))):
            if lang == "Marathi":
                return {
                    "id": "spread",
                    "question": "शेताचा किती भाग बाधित आहे?",
                    "options": [
                        {"id": "few_plants", "label": "🌱 काही मोजकी झाडे"},
                        {"id": "many_plants", "label": "🌾 बराच भाग (पट्टे)"},
                        {"id": "whole_field", "label": "🚜 संपूर्ण शेत"},
                        {"id": "not_sure", "label": "❓ माहित नाही"}
                    ]
                }
            elif lang == "Hindi":
                return {
                    "id": "spread",
                    "question": "खेत का कितना हिस्सा प्रभावित है?",
                    "options": [
                        {"id": "few_plants", "label": "🌱 कुछ ही पौधे"},
                        {"id": "many_plants", "label": "🌾 कई हिस्से (पैच)"},
                        {"id": "whole_field", "label": "🚜 पूरा खेत"},
                        {"id": "not_sure", "label": "❓ पता नहीं"}
                    ]
                }
            else:
                return {
                    "id": "spread",
                    "question": "How much of the field is affected?",
                    "options": [
                        {"id": "few_plants", "label": "🌱 A few plants only"},
                        {"id": "many_plants", "label": "🌾 Scattered patches"},
                        {"id": "whole_field", "label": "🚜 Almost whole field"},
                        {"id": "not_sure", "label": "❓ Not sure"}
                    ]
                }

        return None

    @staticmethod
    def diagnose_simplified(
        query: str = None,
        crop: str = None,
        problem_type: str = None,
        plant_part: str = None,
        spread: str = None,
        timeline: str = None,
        image_base64: str = None,
        language: str = "English",
        district: str = "Maharashtra"
    ) -> Dict[str, Any]:
        """
        Executes a simplified, evidence-backed Crop Doctor diagnosis.
        Returns the 5 farmer-friendly cards:
        1. What we noticed
        2. Possible reason (with uncertainty)
        3. What you can do now (numbered steps)
        4. What to avoid
        5. Need more help (helpline + KVK)
        Plus full audio narration for TTS.
        """
        from app.services.rag_service import RAGService
        from app.schemas.schemas import SourceCitation

        # Resolve Crop
        resolved_crop = crop
        if not resolved_crop and query:
            ctx = CropDoctorFlow.extract_context(query)
            resolved_crop = ctx.get("crop")
        if not resolved_crop:
            resolved_crop = "Cotton" if "cotton" in (query or "").lower() else ("Soybean" if "soya" in (query or "").lower() else "General Crop")

        # Map problem type if query was provided
        combined_text = f"{query or ''} {problem_type or ''}".lower()
        if not problem_type:
            if any(w in combined_text for w in ["yellow", "पिवळे", "पिवळी", "पिवळ", "पीला", "पीली", "पील"]):
                problem_type = "yellow_leaves"
            elif any(w in combined_text for w in ["pest", "worm", "caterpillar", "कीड", "अळी", "कीडे", "कीड़ा", "बोंडअळी"]):
                problem_type = "pests"
            elif any(w in combined_text for w in ["wilt", "dry", "वाळणे", "सुकणे", "मुरझाना", "सुक"]):
                problem_type = "wilting"
            elif any(w in combined_text for w in ["spot", "blight", "ठिपके", "डाग", "धब्बे"]):
                problem_type = "leaf_spots"
            elif any(w in combined_text for w in ["rot", "सडणे", "सड़न"]):
                problem_type = "rotten_fruit"
            else:
                problem_type = "general_issue"

        # Search verified RAG documents
        search_query = f"{resolved_crop} {problem_type.replace('_', ' ')} {plant_part or ''} {query or ''}"
        rag_docs = RAGService.search(search_query, crop=resolved_crop if resolved_crop != "General Crop" else None, limit=2)
        citations = RAGService.format_citations(rag_docs)

        # Build Farmer-Friendly Structured Output based on Crop and Issue
        c_lower = resolved_crop.lower()

        # 1. COTTON - Yellow Leaves
        if "cotton" in c_lower and problem_type == "yellow_leaves":
            if plant_part == "lower_leaves":
                if language == "Marathi":
                    noticed = "कापसाच्या झाडाची खालची जुनी पाने पिवळी पडत आहेत."
                    reasons = "नत्राची (Nitrogen) कमतरता किंवा जमिनीतून मुळांना अन्नद्रव्ये न मिळणे. सुरुवातीला रसशोषक किडींची शक्यता नाकारता येत नाही."
                    actions = [
                        "१९:१९:१९ विद्राव्य खत ५ ग्रॅम प्रति लिटर पाण्यात मिसळून पानांवर फवारणी करा.",
                        "किडींच्या प्रतिबंधासाठी ५% निंबोळी अर्क (NSKE) ५ मिली प्रति लिटर फवारा.",
                        "सकाळी पानांच्या मागील बाजूस हिरवे तुडतुडे आहेत का ते तपासा."
                    ]
                    avoid = "जास्त रासायनिक युरिया जमिनीतून फेकू नका; भर दुपारी कडक उन्हात फवारणी करणे टाळा."
                elif language == "Hindi":
                    noticed = "कपास के पौधे की निचली पुरानी पत्तियां पीली पड़ रही हैं।"
                    reasons = "नाइट्रोजन की कमी या जड़ों तक पोषक तत्व न पहुंचना। शुरुआती रस चूसक कीटों की भी संभावना हो सकती है।"
                    actions = [
                        "19:19:19 घुलनशील खाद 5 ग्राम प्रति लीटर पानी में मिलाकर पत्तियों पर छिड़काव करें।",
                        "कीट सुरक्षा के लिए 5% नीम अर्क (NSKE) 5 मिली प्रति लीटर का छिड़काव करें।",
                        "सुबह के समय पत्तियों के नीचे हरे फुदके (जैसिड्स) की जांच करें।"
                    ]
                    avoid = "जमीन में जरूरत से ज्यादा सूखा यूरिया न डालें; तेज धूप या हवा में कीटनाशक न छिड़कें।"
                else:
                    noticed = "Lower older leaves of the cotton crop are turning yellow."
                    reasons = "Nitrogen deficiency or early root uptake limitation. Sucking pests (Jassids) may also contribute."
                    actions = [
                        "Foliar spray of water-soluble NPK 19:19:19 @ 5 g/L water.",
                        "Apply 5% Neem Seed Kernel Extract (NSKE) @ 5 ml/L water as organic pest protection.",
                        "Inspect the underside of leaves in the morning for green leafhoppers."
                    ]
                    avoid = "Do not apply excessive solid urea without soil moisture; avoid spraying during midday heat (>32°C)."
            else:
                if language == "Marathi":
                    noticed = "कापसाची पाने पिवळी पडत असून पानांच्या शिरांमधील भाग फिकट दिसत आहे."
                    reasons = "मॅग्नेशियम किंवा सूक्ष्म अन्नद्रव्यांची कमतरता, किंवा रसशोषक किडींचा (मावा/तुडतुडे) प्रादुर्भाव असण्याची दाट शक्यता आहे."
                    actions = [
                        "मॅग्नेशियम सल्फेट (Magnesium Sulphate) १० ग्रॅम प्रति लिटर पाण्यात मिसळून फवारा.",
                        "५% निंबोळी अर्क (NSKE) ५ मिली प्रति लिटर पाण्यात प्रतिबंधात्मक फवारा.",
                        "शेतात पिवळे चिकट सापळे (Yellow Sticky Traps) एकरी १० ते १५ लावा."
                    ]
                    avoid = "कार्डाशिवाय महागडी विषारी कीटकनाशके वापरू नका; पाण्याचा ताण किंवा साचलेले पाणी टाळा."
                elif language == "Hindi":
                    noticed = "कपास की पत्तियां पीली पड़ रही हैं और शिराओं के बीच का भाग हल्का हरा दिख रहा है।"
                    reasons = "मैग्नीशियम या सूक्ष्म पोषक तत्वों की कमी, या रस चूसक कीटों (माहू/जैसिड्स) का प्रकोप संभावित कारण हो सकता है।"
                    actions = [
                        "मैग्नीशियम सल्फेट 10 ग्राम प्रति लीटर पानी में मिलाकर छिड़कें।",
                        "5% नीम अर्क (NSKE) 5 मिली प्रति लीटर पानी में मिलाकर प्राथमिक छिड़काव करें।",
                        "खेत में पीले चिपचिपे जाल (Yellow Sticky Traps) प्रति एकड़ 10-15 लगाएं।"
                    ]
                    avoid = "बिना उचित पहचान के महंगे रासायनिक कीटनाशक न छिड़कें; खेत में जलभराव न होने दें।"
                else:
                    noticed = "Cotton leaves are turning yellow with pale discoloration between veins."
                    reasons = "Magnesium or micronutrient deficiency, or sucking pest pressure (jassids/aphids)."
                    actions = [
                        "Spray Magnesium Sulphate @ 10 g/L water.",
                        "Spray 5% Neem Seed Kernel Extract (NSKE) @ 5 ml/L water.",
                        "Install yellow sticky traps @ 10-15 per acre to monitor and trap sucking pests."
                    ]
                    avoid = "Avoid mixing incompatible chemical pesticides; do not apply excessive fertilizers without irrigation."

        # 2. COTTON - Pests (Bollworm / Sucking pests)
        elif "cotton" in c_lower and problem_type == "pests":
            if language == "Marathi":
                noticed = "कापसावर बोंडअळी किंवा किडींचा प्रादुर्भाव दिसून येत आहे."
                reasons = "गुलाबी बोंडअळी (Pink Bollworm) किंवा अमेरिकन बोंडअळीचा प्रादुर्भाव. फुलोरा किंवा बोंड तयार होण्याच्या काळात ही कीड वाढते."
                actions = [
                    "शेतात कामगंध सापळे (Pheromone Traps) एकरी ५ ते ८ लावा, जेणेकरून पतंग पकडले जातील.",
                    "जैविक नियंत्रण म्हणून ट्रायकोकार्ड (Trichogramma) ३ कार्ड प्रति एकर लावा.",
                    "प्रादुर्भाव जास्त असल्यास इमामेक्टिन बेन्झोएट ५% SG ४ ग्रॅम प्रति १० लिटर पाण्यात फवारा."
                ]
                avoid = "किडींचा प्रादुर्भाव समजण्याआधी अनियंत्रित सिंथेटिक पायरेथ्रॉईड्स फवारू नका."
            elif language == "Hindi":
                noticed = "कपास की फसल में गुलाबी सुंडी या कीटों का प्रकोप दिख रहा है।"
                reasons = "गुलाबी सुंडी (Pink Bollworm) का संक्रमण। फूल और गूलर बनते समय यह कीट सबसे अधिक नुकसान पहुंचाता है।"
                actions = [
                    "खेत में फेरोमोन ट्रैप (Pheromone Traps) प्रति एकड़ 5-8 लगाएं।",
                    "जैविक नियंत्रण के लिए ट्राइकोग्रामा कार्ड 3 कार्ड प्रति एकड़ उपयोग करें।",
                    "संक्रमण अधिक होने पर इमामेक्टिन बेंजोएट 5% SG 4 ग्राम प्रति 10 लीटर पानी में छिड़कें।"
                ]
                avoid = "बिना निगरानी के अत्यधिक सिंथेटिक कीटनाशक न छिड़कें; शाम के समय ही छिड़काव करें।"
            else:
                noticed = "Bollworm or caterpillar infestation observed in the cotton field."
                reasons = "Pink Bollworm (Pectinophora gossypiella) infestation during flowering or boll formation stage."
                actions = [
                    "Install Pheromone traps @ 5-8 per acre to monitor and trap adult male moths.",
                    "Release Trichogramma egg parasitoids @ 3 cards per acre for natural biocontrol.",
                    "If ETL is crossed (>8 moths/trap/night), spray Emamectin Benzoate 5% SG @ 4 g/10L water."
                ]
                avoid = "Avoid indiscriminate use of synthetic pyrethroids which induce resurgence of sucking pests."

        # 3. SOYBEAN - Yellow Leaves / Disease
        elif "soybean" in c_lower and (problem_type == "yellow_leaves" or problem_type == "leaf_spots"):
            if language == "Marathi":
                noticed = "सोयाबीनची पाने पिवळी पडत आहेत किंवा पिवळसर डाग दिसत आहेत."
                reasons = "यलो मोझॅक व्हायरस (पांढऱ्या माशीमुळे पसरतो) किंवा शेतात पाणी साचल्यामुळे मुळांना हवेची कमतरता."
                actions = [
                    "शेतातील अतिरिक्त पाण्याचा तातडीने निचरा करा जेणेकरून मुळांना ऑक्सिजन मिळेल.",
                    "व्हायरस पसरवणाऱ्या पांढऱ्या माशीच्या नियंत्रणासाठी पिवळे चिकट सापळे एकरी १० लावा.",
                    "किडी नियंत्रणासाठी ५% निंबोळी अर्क किंवा थायामेथोक्सम १२.६% + लॅम्बडा सायहेलोथ्रिन ९.५% झेडसी ३ मिली/१० लिटर फवारा."
                ]
                avoid = "रोगट झाडे शेतात तशीच ठेवू नका; जास्त पाणी साचू देऊ नका."
            elif language == "Hindi":
                noticed = "सोयाबीन की पत्तियां पीली पड़ रही हैं या पीले धब्बे दिख रहे हैं।"
                reasons = "येलो मोजेक वायरस (सफेद मक्खी द्वारा फैलने वाला) या खेत में पानी भरने से जड़ों का घुटन।"
                actions = [
                    "खेत से तुरंत अतिरिक्त पानी निकालें ताकि जड़ों को हवा मिल सके।",
                    "सफेद मक्खी नियंत्रण के लिए पीले चिपचिपे ट्रैप प्रति एकड़ 10 लगाएं।",
                    "सुरक्षा के लिए 5% नीम अर्क 5 मिली प्रति लीटर पानी में मिलाकर छिड़कें।"
                ]
                avoid = "रोगग्रस्त पौधों को खेत में न छोड़ें; जलभराव की स्थिति न बनने दें।"
            else:
                noticed = "Soybean leaves turning yellow with mottled patches or chlorosis."
                reasons = "Yellow Mosaic Virus (vectored by whitefly) or temporary root asphyxiation from waterlogging."
                actions = [
                    "Ensure immediate drainage of excess rainwater from the field.",
                    "Install yellow sticky traps @ 10/acre to control the whitefly vector.",
                    "Apply prophylactic spray of 5% Neem Seed Kernel Extract (NSKE) @ 5 ml/L water."
                ]
                avoid = "Do not allow standing water around the root zone; do not apply urea when soil is waterlogged."

        # 4. TOMATO / ONION / GENERAL
        elif "tomato" in c_lower or "onion" in c_lower:
            crop_name_mr = "टोमॅटो" if "tomato" in c_lower else "कांदा"
            crop_name_hi = "टमाटर" if "tomato" in c_lower else "प्याज"
            if language == "Marathi":
                noticed = f"{crop_name_mr} पिकावर {problem_type.replace('_', ' ')} संबंधी लक्षणे दिसत आहेत."
                reasons = "बुरशीजन्य करपा (Purple Blotch / Blight) किंवा थ्रिप्स (फुलकिडे) किडींचा प्रादुर्भाव असण्याची शक्यता आहे."
                actions = [
                    "सेंद्रिय उपाय म्हणून ट्रायकोडर्मा व्हिरिडी किंवा स्युडोमोनास ५ ग्रॅम प्रति लिटर पाण्यात फवारा.",
                    "थ्रिप्स नियंत्रणासाठी निळे व पिवळे चिकट सापळे एकरी १५ लावा.",
                    "बुरशीचा प्रादुर्भाव असल्यास मँकोझेब ७५ WP २.५ ग्रॅम प्रति लिटर पाण्यात मिसळून फवारा."
                ]
                avoid = "दुपारच्या कडक उन्हात फवारणी करू नका; एकाच औषधाचा वारंवार वापर टाळा."
            elif language == "Hindi":
                noticed = f"{crop_name_hi} की फसल पर {problem_type.replace('_', ' ')} के लक्षण दिख रहे हैं।"
                reasons = "फंगल ब्लाइट या थ्रिप्स (रस चूसक कीट) का प्रकोप संभावित कारण हो सकता है।"
                actions = [
                    "जैविक उपचार के लिए ट्राइकोडर्मा विरिडी 5 ग्राम प्रति लीटर पानी में मिलाकर छिड़कें।",
                    "थ्रिप्स नियंत्रण के लिए नीले और पीले ट्रैप 15 प्रति एकड़ लगाएं।",
                    "फंगल संक्रमण रोकने के लिए मेंकोजेब 75 WP 2.5 ग्राम प्रति लीटर छिड़कें।"
                ]
                avoid = "कड़क धूप में छिड़काव न करें; एक ही कीटनाशक का बार-बार इस्तेमाल न करें।"
            else:
                noticed = f"Symptoms of {problem_type.replace('_', ' ')} observed on the {resolved_crop} crop."
                reasons = "Fungal blight (Purple blotch / Alternaria) or Thrips sap-sucking pest infestation."
                actions = [
                    "Apply bio-fungicide Trichoderma viride @ 5 g/L water.",
                    "Install blue and yellow sticky traps @ 15 per acre to trap thrips.",
                    "If fungal lesions spread, spray Mancozeb 75% WP @ 2.5 g/L water with sticker."
                ]
                avoid = "Do not spray during midday heat (>32°C); do not spray without personal protective equipment."

        # 5. GENERAL FALLBACK
        else:
            if language == "Marathi":
                noticed = f"{resolved_crop} पिकावर {problem_type.replace('_', ' ')} लक्षणे आढळून आली आहेत."
                reasons = "अन्नद्रव्यांची कमतरता, सुरुवातीचा बुरशीजन्य प्रादुर्भाव किंवा रसशोषक किडींचे आक्रमण असण्याची शक्यता आहे."
                actions = [
                    "बाधित पानांचे बारकाईने निरीक्षण करा आणि मुळांजवळ पाण्याचा निचरा व्यवस्थित ठेवा.",
                    "सेंद्रिय सुरक्षेसाठी ५% निंबोळी अर्क (NSKE) ५ मिली प्रति लिटर पाण्यात फवारा.",
                    "लक्षणे जास्त असल्यास स्थानिक कृषी विज्ञान केंद्र (KVK) च्या शास्त्रज्ञांचा सल्ला घ्या."
                ]
                avoid = "तज्ज्ञांच्या सल्ल्याशिवाय अवाजवी रासायनिक कीटकनाशके फवारू नका."
            elif language == "Hindi":
                noticed = f"{resolved_crop} की फसल पर {problem_type.replace('_', ' ')} के लक्षण दिखाई दे रहे हैं।"
                reasons = "पोषक तत्वों की कमी, फफूंद जनित रोग या रस चूसक कीटों का प्रारंभिक प्रकोप हो सकता है।"
                actions = [
                    "प्रभावित पौधों का निरीक्षण करें और खेत में जल निकासी सुनिश्चित करें।",
                    "जैविक सुरक्षा के लिए 5% नीम तेल/अर्क 5 मिली प्रति लीटर पानी में मिलाकर छिड़कें।",
                    "संक्रमण अधिक होने पर नजदीकी कृषि विज्ञान केंद्र (KVK) के वैज्ञानिकों से संपर्क करें।"
                ]
                avoid = "बिना उचित सलाह के अत्यधिक रसायनों का अंधाधुंध उपयोग न करें।"
            else:
                noticed = f"Symptoms of {problem_type.replace('_', ' ')} observed in {resolved_crop} field."
                reasons = "Nutrient deficiency, early fungal infection, or sap-sucking insect pests."
                actions = [
                    "Inspect affected foliage closely and ensure proper root zone drainage.",
                    "Apply a preventive organic spray of 5% Neem Seed Kernel Extract (NSKE) @ 5 ml/L water.",
                    "If symptoms persist or spread rapidly, consult your local Krishi Vigyan Kendra (KVK)."
                ]
                avoid = "Avoid indiscriminate use of chemical cocktails without diagnostic confirmation."

        # Generate Audio Narration Text (optimized for Web Speech API TTS)
        if language == "Marathi":
            helpline = "किसान कॉल सेंटर (टोल-फ्री): 1800-180-1551 किंवा आपल्या तालुक्याचे कृषी विज्ञान केंद्र (KVK)."
            narration = f"आपल्या पिकाची तपासणी पूर्ण झाली आहे. आम्ही पाहिले की: {noticed} संभाव्य कारण: {reasons} आपण आता हे करू शकता: पहिली पायरी, {actions[0]} दुसरी पायरी, {actions[1]} तिसरी पायरी, {actions[2]} काय टाळावे: {avoid} अधिक मदतीसाठी १८०० १८० १५५१ या मोफत नंबरवर कॉल करा."
        elif language == "Hindi":
            helpline = "किसान कॉल सेंटर (टोल-फ्री): 1800-180-1551 या नजदीकी कृषि विज्ञान केंद्र (KVK)।"
            narration = f"आपकी फसल की जांच पूरी हो गई है। हमने देखा: {noticed} संभावित कारण: {reasons} आप अभी यह कदम उठा सकते हैं: पहला, {actions[0]} दूसरा, {actions[1]} तीसरा, {actions[2]} क्या न करें: {avoid} अधिक सहायता के लिए 1800 180 1551 पर मुफ्त कॉल करें।"
        else:
            helpline = "Kisan Call Center (Toll-Free): 1800-180-1551 or your local Krishi Vigyan Kendra (KVK)."
            narration = f"Crop consultation summary. What we noticed: {noticed}. Possible cause: {reasons}. What you can do now: First, {actions[0]}. Second, {actions[1]}. Third, {actions[2]}. What to avoid: {avoid}. For further assistance, contact toll-free 1800-180-1551."

        return {
            "crop": resolved_crop,
            "symptoms_noticed": noticed,
            "possible_reasons": reasons,
            "immediate_actions": actions,
            "what_to_avoid": avoid,
            "expert_helpline": helpline,
            "audio_narration": narration,
            "follow_up_question": None,
            "sources": citations,
            "language": language
        }
