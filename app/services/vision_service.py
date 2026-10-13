import io
import re
import json
import base64
import httpx
import logging
from PIL import Image
from typing import Dict, Any, List, Optional, Tuple
from app.config import settings
from app.schemas.schemas import CropAnalysisResponse, SourceCitation
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

Tuple_Validation = Tuple[bool, str]

class VisionService:
    @staticmethod
    def validate_image(image_bytes: bytes) -> Tuple_Validation:
        """Validates that bytes represent a valid readable image."""
        if not image_bytes or len(image_bytes) == 0:
            return False, "Uploaded image file is empty. Please select a valid photo."
        if len(image_bytes) > 10 * 1024 * 1024:
            return False, "Image size exceeds 10 MB limit."
        try:
            img = Image.open(io.BytesIO(image_bytes))
            format_name = (img.format or "").lower()
            if format_name not in ["jpeg", "jpg", "png", "webp"]:
                return False, f"Unsupported image format: {format_name or 'unknown'}. Please upload JPG, PNG, or WEBP."
            img.verify()
            return True, format_name
        except Exception as e:
            return False, f"Invalid image file: {str(e)}"

    @staticmethod
    async def analyze_crop_image(
        image_base64: str,
        crop_hint: Optional[str] = None,
        language: str = "English",
        additional_notes: Optional[str] = None
    ) -> CropAnalysisResponse:
        """
        Performs actual AI vision analysis on the uploaded leaf/crop image.
        """
        # Clean base64 data uri prefix if present
        if "," in image_base64:
            _, b64_data = image_base64.split(",", 1)
        else:
            b64_data = image_base64

        try:
            raw_bytes = base64.b64decode(b64_data)
        except Exception:
            raise ValueError("Invalid Base64 encoded image data.")

        is_valid, format_or_err = VisionService.validate_image(raw_bytes)
        if not is_valid:
            raise ValueError(format_or_err)

        fmt = format_or_err
        if fmt == "jpg":
            fmt = "jpeg"
        mime_type = f"image/{fmt}"

        # Retrieve relevant RAG context if crop hint is available
        rag_docs = []
        if crop_hint:
            rag_docs = RAGService.search(f"{crop_hint} pest disease symptoms", crop=crop_hint, limit=2)

        prompt = f"""You are a senior agricultural plant pathologist and entomologist.
Analyze this crop/plant/leaf image thoroughly.
Language for response: {language}.
Farmer notes: {additional_notes or 'None'}.
Crop hint: {crop_hint or 'Detect from image'}.

You must format your response EXACTLY as a valid JSON object with the following keys:
{{
  "observed_symptoms": "Detailed visual description of spots, curling, lesions, discoloration, pest presence, or fungal signs",
  "possible_diagnosis": "Most plausible pest, fungal disease, bacterial pathogen, or nutrient deficiency with scientific and common name",
  "severity": "High or Medium or Low",
  "confidence": "e.g. 85% based on visual leaf lesions",
  "organic_treatment": [
    "Step 1 practical organic remedy with exact dosage (e.g. Neem oil / NSKE)",
    "Step 2 biological control or cultural practice",
    "Step 3 field sanitation"
  ],
  "chemical_treatment": [
    "Certified chemical option 1 with dosage per liter (mention safety precautions)",
    "Chemical option 2 with pre-harvest interval reminder"
  ],
  "prevention_measures": [
    "Preventive practice 1 for future seasons",
    "Resistant variety or seed treatment"
  ],
  "expert_escalation_needed": true or false
}}

Respond ONLY with valid JSON. Do not include markdown code block formatting or backticks around the json."""

        # Attempt Groq Vision API
        if settings.GROQ_API_KEY:
            try:
                headers = {
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
                body = {
                    "model": settings.GROQ_VISION_MODEL,
                    "max_tokens": 2048,
                    "temperature": 0.2,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{b64_data}"
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": prompt
                                }
                            ]
                        }
                    ]
                }
                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=body)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_content = data["choices"][0]["message"]["content"].strip()
                        # Clean potential markdown backticks
                        clean_json = re.sub(r"^```json\s*", "", raw_content)
                        clean_json = re.sub(r"^```\s*", "", clean_json)
                        clean_json = re.sub(r"\s*```$", "", clean_json)
                        parsed = json.loads(clean_json)

                        citations = RAGService.format_citations(rag_docs)
                        return CropAnalysisResponse(
                            observed_symptoms=parsed.get("observed_symptoms", "Visible foliar lesions"),
                            possible_diagnosis=parsed.get("possible_diagnosis", "Plant leaf disease"),
                            severity=parsed.get("severity", "Medium"),
                            confidence=parsed.get("confidence", "75% - Field visual evaluation"),
                            organic_treatment=parsed.get("organic_treatment", ["Spray 5% Neem Seed Kernel Extract (NSKE) @ 5 ml/L"]),
                            chemical_treatment=parsed.get("chemical_treatment", ["Consult local KVK for verified chemical dosage"]),
                            prevention_measures=parsed.get("prevention_measures", ["Remove infected leaves and sanitize field tools"]),
                            expert_escalation_needed=parsed.get("expert_escalation_needed", False),
                            sources=citations,
                            language=language
                        )
                    else:
                        logger.error(f"Groq vision returned error: {resp.status_code} - {resp.text}")
            except Exception as e:
                logger.error(f"Vision API call failed: {e}")

        # If vision API is not configured or failed, do NOT fake analysis with random answers!
        # Return transparent failure with safe actionable next step
        raise RuntimeError("AI Vision service is currently unavailable or quota limit reached. Please describe your crop symptoms directly to our Crop Doctor assistant in chat, or contact your nearest Krishi Vigyan Kendra (KVK).")
