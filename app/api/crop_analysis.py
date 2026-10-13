import base64
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, status
from typing import Optional
from app.schemas.schemas import CropAnalysisRequest, CropAnalysisResponse, SimpleCropDoctorRequest, SimpleCropDoctorResponse
from app.services.vision_service import VisionService

router = APIRouter(prefix="/api", tags=["Crop Analysis"])

@router.post("/analyze-crop", response_model=CropAnalysisResponse)
async def analyze_crop(
    request: Request,
    image: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    crop_name: Optional[str] = Form(None),
    language: Optional[str] = Form("English"),
    additional_notes: Optional[str] = Form(None)
):
    """
    Analyzes an uploaded leaf or crop photo using real Vision AI.
    Accepts multipart/form-data with 'image' (preferred) or 'file',
    as well as JSON payloads containing 'image_base64'.
    """
    uploaded_file = image or file
    image_b64 = None
    crop = crop_name
    lang = language or "English"
    notes = additional_notes

    if uploaded_file is not None:
        content = await uploaded_file.read()
        if not content or len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded image file is empty. Please select a valid photo."
            )
        is_valid, msg = VisionService.validate_image(content)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
        image_b64 = base64.b64encode(content).decode("utf-8")
    else:
        # Check if request has a JSON payload with image_base64
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                json_data = await request.json()
                if isinstance(json_data, dict):
                    image_b64 = json_data.get("image_base64")
                    crop = json_data.get("crop_name") or crop
                    lang = json_data.get("language") or lang
                    notes = json_data.get("additional_notes") or notes
            except Exception:
                pass

        if not image_b64:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No crop image provided. Please upload an image file or provide image_base64."
            )

        # Validate base64 image data
        try:
            clean_b64 = image_b64.split(",", 1)[1] if "," in image_b64 else image_b64
            raw_bytes = base64.b64decode(clean_b64)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Base64 encoded image data."
            )

        is_valid, msg = VisionService.validate_image(raw_bytes)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    try:
        result = await VisionService.analyze_crop_image(
            image_base64=image_b64,
            crop_hint=crop,
            language=lang,
            additional_notes=notes
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))

@router.post("/crop-doctor/followup-check")
def check_crop_doctor_followup(payload: SimpleCropDoctorRequest):
    """
    Checks if a single, non-intrusive multiple choice question should be asked
    to narrow diagnosis before providing the final answer.
    """
    from app.services.crop_doctor import CropDoctorFlow
    q = CropDoctorFlow.get_single_follow_up_question(
        crop=payload.crop,
        symptoms=payload.query,
        problem_type=payload.problem_type,
        plant_part=payload.plant_part,
        spread=payload.spread,
        timeline=payload.timeline,
        lang=payload.language or "English"
    )
    return {
        "has_follow_up": q is not None,
        "question": q
    }

@router.post("/crop-doctor/consult", response_model=SimpleCropDoctorResponse)
async def simple_crop_doctor_consult(payload: SimpleCropDoctorRequest):
    """
    Voice-first, picture-based simplified Crop Doctor consultation endpoint.
    Returns 5 farmer-friendly cards:
    1. What we noticed
    2. Possible reasons
    3. What to do now (numbered actionable steps)
    4. What to avoid
    5. Need more help (Kisan Call Center / KVK)
    Includes complete audio narration text for Web Speech API TTS.
    """
    from app.services.crop_doctor import CropDoctorFlow

    # Check for uploaded image (supports single image_base64 or list images_base64)
    primary_image = payload.image_base64
    if not primary_image and payload.images_base64 and len(payload.images_base64) > 0:
        primary_image = payload.images_base64[0]

    vision_offline_note = None

    if primary_image:
        # Validate base64 image data first
        try:
            clean_b64 = primary_image.split(",", 1)[1] if "," in primary_image else primary_image
            raw_bytes = base64.b64decode(clean_b64)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Base64 encoded image data."
            )

        is_valid, msg = VisionService.validate_image(raw_bytes)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

        try:
            vision_res = await VisionService.analyze_crop_image(
                image_base64=primary_image,
                crop_hint=payload.crop,
                language=payload.language or "English",
                additional_notes=payload.query
            )
            # Adapt vision response to farmer-friendly 5-card structure
            lang = payload.language or "English"
            if lang == "Marathi":
                avoid = "दुपारच्या कडक उन्हात किंवा वाऱ्यात फवारणी करू नका; सुरक्षा मास्क व हातमोजे वापरा."
                helpline = "किसान कॉल सेंटर (टोल-फ्री): 1800-180-1551 किंवा जवळचे कृषी विज्ञान केंद्र (KVK)."
                narration = f"फोटो तपासणी पूर्ण झाली आहे. आम्ही पाहिले: {vision_res.observed_symptoms}. संभाव्य कारण: {vision_res.possible_diagnosis}. आता काय करावे: पहिली पायरी, {vision_res.organic_treatment[0] if vision_res.organic_treatment else 'निंबोळी अर्क फवारा'}. दुसरी पायरी, {vision_res.chemical_treatment[0] if vision_res.chemical_treatment else 'कृषी तज्ज्ञांचा सल्ला घ्या'}. काय टाळावे: {avoid} अधिक मदतीसाठी 1800 180 1551 वर कॉल करा."
            elif lang == "Hindi":
                avoid = "कड़क धूप या तेज हवा में छिड़काव न करें; सुरक्षा मास्क और दस्ताने पहनें।"
                helpline = "किसान कॉल सेंटर (टोल-फ्री): 1800-180-1551 या नजदीकी कृषि विज्ञान केंद्र (KVK)।"
                narration = f"फोटो जांच पूरी हो गई है। हमने देखा: {vision_res.observed_symptoms}. संभावित कारण: {vision_res.possible_diagnosis}. अभी क्या करें: पहला, {vision_res.organic_treatment[0] if vision_res.organic_treatment else 'नीम अर्क छिड़कें'}. दूसरा, {vision_res.chemical_treatment[0] if vision_res.chemical_treatment else 'विशेषज्ञ की सलाह लें'}. क्या न करें: {avoid} अधिक सहायता के लिए 1800 180 1551 पर कॉल करें।"
            else:
                avoid = "Avoid spraying during midday heat (>32°C) or in high winds; always wear protective gear."
                helpline = "Kisan Call Center (Toll-Free): 1800-180-1551 or your local Krishi Vigyan Kendra (KVK)."
                narration = f"Photo evaluation complete. What we noticed: {vision_res.observed_symptoms}. Possible diagnosis: {vision_res.possible_diagnosis}. What to do now: First, {vision_res.organic_treatment[0] if vision_res.organic_treatment else 'Apply organic remedy'}. Second, {vision_res.chemical_treatment[0] if vision_res.chemical_treatment else 'Consult local KVK'}. What to avoid: {avoid}. For help call 1800-180-1551."

            actions = []
            if vision_res.organic_treatment:
                actions.append(vision_res.organic_treatment[0])
            if vision_res.chemical_treatment:
                actions.append(vision_res.chemical_treatment[0])
            if vision_res.prevention_measures:
                actions.append(vision_res.prevention_measures[0])

            return SimpleCropDoctorResponse(
                crop=payload.crop or "Plant Leaf Photo",
                symptoms_noticed=vision_res.observed_symptoms,
                possible_reasons=f"{vision_res.possible_diagnosis} ({vision_res.confidence})",
                immediate_actions=actions if actions else ["Spray 5% NSKE @ 5 ml/L", "Monitor leaf underside regularly"],
                what_to_avoid=avoid,
                expert_helpline=helpline,
                audio_narration=narration,
                sources=vision_res.sources,
                language=lang
            )
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
        except Exception:
            # If vision model is offline or unconfigured, fall back honestly to diagnostic heuristics
            lang = payload.language or "English"
            if lang == "Marathi":
                vision_offline_note = "(टीप: AI व्हिजन सेवा तात्पुरती अनुपलब्ध असल्याने विद्यापीठांच्या शिफारसींनुसार लक्षण-आधारित सल्ला दिला आहे)"
            elif lang == "Hindi":
                vision_offline_note = "(नोट: AI विज़न सेवा अस्थायी रूप से अनुपलब्ध है; कृषि विश्वविद्यालय के दिशानिर्देशों के आधार पर सलाह दी गई है)"
            else:
                vision_offline_note = "(Note: AI vision service currently unavailable; advisory estimated from university guidelines based on reported symptoms)"

    diag = CropDoctorFlow.diagnose_simplified(
        query=payload.query,
        crop=payload.crop,
        problem_type=payload.problem_type,
        plant_part=payload.plant_part,
        spread=payload.spread,
        timeline=payload.timeline,
        image_base64=primary_image,
        language=payload.language or "English",
        district=payload.district or "Maharashtra"
    )

    if vision_offline_note and "possible_reasons" in diag:
        diag["possible_reasons"] = f"{diag['possible_reasons']} {vision_offline_note}"

    return SimpleCropDoctorResponse(**diag)
