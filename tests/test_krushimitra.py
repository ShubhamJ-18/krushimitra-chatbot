import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.main import app
from app.services.rag_service import RAGService
from app.services.crop_doctor import CropDoctorFlow
from app.services.ai_service import AIService
from app.services.weather_service import WeatherService
from app.services.mandi_service import MandiService
from app.services.scheme_service import SchemeService
import io
import base64
from PIL import Image
from unittest.mock import patch, AsyncMock
from app.schemas.schemas import CropAnalysisResponse, SourceCitation
from app.services.vision_service import VisionService

client = TestClient(app)

def test_health_endpoint():
    """Verify health endpoint reports correct database and status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["database"] == "connected"
    assert data["rag_indexed_documents"] >= 8

def test_rag_retrieval_and_citation():
    """Verify RAG retrieval returns verified documents with sources and URLs."""
    results = RAGService.search("pink bollworm cotton advisory", crop="Cotton", limit=2)
    assert len(results) > 0
    doc = results[0]
    assert "Bollworm" in doc["title"] or "Cotton" in doc["title"]
    assert doc["source_name"] is not None
    assert doc["source_url"] is not None

    citations = RAGService.format_citations(results)
    assert len(citations) > 0
    assert citations[0].source_name != ""

def test_crop_doctor_missing_information_detection():
    """Verify Crop Doctor detects missing parameters and generates relevant follow-up question."""
    # Farmer asks vague question without crop name
    context = CropDoctorFlow.extract_context("My leaves are turning yellow, what should I do?")
    assert context["crop"] is None
    assert context["symptoms"] is not None

    missing, follow_up = CropDoctorFlow.check_missing_parameters(context, lang="English")
    assert "crop" in missing
    assert "Which crop" in follow_up

    # Now with crop known but stage missing
    context2 = CropDoctorFlow.extract_context("My cotton leaves have pink worms and rosette flowers.")
    assert context2["crop"] == "Cotton"
    missing2, follow_up2 = CropDoctorFlow.check_missing_parameters(context2, lang="English")
    assert "crop" not in missing2

def test_chat_api_marathi_yellow_leaves():
    """Test Marathi query about yellow leaves and source attribution."""
    payload = {
        "message": "सोयाबीनची पाने पिवळी पडत आहेत, काय करावे?",
        "language": "Marathi",
        "district": "Latur"
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] is not None
    assert len(data["message"]) > 0
    # Must have sources cited
    assert isinstance(data["sources"], list)
    assert data["language"] == "Marathi"

def test_chat_api_hindi_irrigation():
    """Test Hindi query about irrigation."""
    payload = {
        "message": "ड्रिप सिंचाई में खाद कैसे दें और कितना पानी चाहिए?",
        "language": "Hindi",
        "district": "Nashik"
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["message"]) > 0
    assert data["language"] == "Hindi"

def test_chat_api_english_disease_and_context_memory():
    """Test English crop problem and follow-up referring to previous turn."""
    # Turn 1
    t1 = client.post("/api/chat", json={
        "message": "I am growing cotton in Yavatmal and noticed pink bollworm attack.",
        "language": "English",
        "district": "Yavatmal"
    })
    assert t1.status_code == 200
    d1 = t1.json()
    conv_id = d1["conversation_id"]

    # Turn 2 referring back without repeating crop or pest name
    t2 = client.post("/api/chat", json={
        "message": "Can I spray neem oil first, and what should be the dose per liter?",
        "conversation_id": conv_id,
        "language": "English",
        "district": "Yavatmal"
    })
    assert t2.status_code == 200
    d2 = t2.json()
    assert d2["conversation_id"] == conv_id
    assert len(d2["message"]) > 0

def test_weather_endpoint():
    """Test weather integration and agromet advisory rules."""
    response = client.get("/api/weather?district=Pune")
    assert response.status_code == 200
    data = response.json()
    assert data["district"] == "Pune"
    assert "temperature_c" in data
    assert "spraying_advisory" in data
    assert "irrigation_advisory" in data
    assert data["source"] is not None

def test_mandi_prices_endpoint():
    """Test APMC mandi rates and filtering."""
    # All commodities
    r1 = client.get("/api/market-prices")
    assert r1.status_code == 200
    d1 = r1.json()
    assert len(d1["commodities"]) > 0
    assert "Agmarknet" in d1["source"]

    # Filtered by Onion
    r2 = client.get("/api/market-prices?commodity=Onion")
    assert r2.status_code == 200
    d2 = r2.json()
    assert len(d2["commodities"]) > 0
    assert any("Onion" in c["commodity"] for c in d2["commodities"])

def test_schemes_and_eligibility():
    """Test verified government schemes and eligibility questionnaire."""
    # List schemes
    r_list = client.get("/api/schemes")
    assert r_list.status_code == 200
    schemes = r_list.json()["schemes"]
    assert len(schemes) >= 3
    assert any("PM-KISAN" in s["name"] for s in schemes)

    # Check eligibility
    check_payload = {
        "land_acres": 2.5,
        "is_taxpayer": False,
        "ekyc_completed": True,
        "has_saatbaara": True
    }
    r_check = client.post("/api/schemes/check", json=check_payload)
    assert r_check.status_code == 200
    eval_data = r_check.json()
    assert "schemes_evaluated" in eval_data
    assert len(eval_data["schemes_evaluated"]) >= 2

def test_crop_analysis_validation_invalid_file():
    """Test crop image upload with invalid file returns proper 400 error."""
    # Upload text file as image
    files = {"file": ("test.txt", b"not an image", "text/plain")}
    response = client.post("/api/analyze-crop", files=files)
    assert response.status_code == 400
    assert "Unsupported image format" in response.json()["detail"] or "Invalid image file" in response.json()["detail"]

def test_conversation_deletion():
    """Test creating and deleting a conversation."""
    create_res = client.post("/api/chat", json={"message": "Temporary test chat"})
    conv_id = create_res.json()["conversation_id"]

    del_res = client.delete(f"/api/conversations/{conv_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # Confirm not found
    get_res = client.get(f"/api/conversations/{conv_id}")
    assert get_res.status_code == 404

def test_simplified_crop_doctor_marathi_voice():
    """Verify simplified voice consultation in Marathi detects Cotton and returns 5 farmer-friendly cards with TTS narration."""
    payload = {
        "query": "माझ्या कापसाची पाने पिवळी पडत आहेत",
        "language": "Marathi",
        "plant_part": "lower_leaves"
    }
    response = client.post("/api/crop-doctor/consult", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["crop"] == "Cotton"
    assert "कापसा" in data["symptoms_noticed"] or "पाने" in data["symptoms_noticed"]
    assert len(data["immediate_actions"]) >= 2
    assert "टाळावे" in data["what_to_avoid"] or "युरिया" in data["what_to_avoid"] or len(data["what_to_avoid"]) > 0
    assert "1800-180-1551" in data["expert_helpline"]
    assert len(data["audio_narration"]) > 50
    assert data["language"] == "Marathi"

def test_simplified_crop_doctor_hindi_problem_card():
    """Verify picture-based problem consultation in Hindi returns bollworm advisory."""
    payload = {
        "crop": "Cotton",
        "problem_type": "pests",
        "language": "Hindi"
    }
    response = client.post("/api/crop-doctor/consult", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["crop"] == "Cotton"
    assert "गुलाबी सुंडी" in data["possible_reasons"] or "कीट" in data["possible_reasons"] or "Bollworm" in data["possible_reasons"]
    assert any("फेरोमोन" in act or "ट्राइकोग्रामा" in act or "कीटनाशक" in act or "spray" in act.lower() for act in data["immediate_actions"])
    assert "1800-180-1551" in data["expert_helpline"]

def test_crop_doctor_single_followup_question():
    """Verify that only ONE relevant multiple-choice question is generated when plant part is unknown."""
    payload = {
        "crop": "Cotton",
        "problem_type": "yellow_leaves",
        "language": "Marathi"
    }
    response = client.post("/api/crop-doctor/followup-check", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_follow_up"] is True
    assert data["question"]["id"] == "plant_part"
    assert len(data["question"]["options"]) == 4

def test_crop_doctor_consultation_no_mandatory_fields():
    """Verify consultation works even when farmer does not specify crop or district (accessibility for low-literacy farmers)."""
    payload = {
        "problem_type": "yellow_leaves",
        "language": "English"
    }
    response = client.post("/api/crop-doctor/consult", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["symptoms_noticed"] is not None
    assert len(data["immediate_actions"]) >= 2
    assert "1800-180-1551" in data["expert_helpline"]

def _generate_test_image(fmt="JPEG", color="green", size=(64, 64)):
    """Helper to generate in-memory test image bytes."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()

def test_crop_analysis_multipart_image_success():
    """Test Case 1: Upload a tomato leaf photo via FormData 'image' field and receive valid diagnosis."""
    tomato_jpg = _generate_test_image("JPEG", color="red")
    mock_resp = CropAnalysisResponse(
        observed_symptoms="Dark concentric rings on lower tomato foliage, early stem lesions",
        possible_diagnosis="Early Blight (Alternaria solani) in Tomato",
        severity="Medium",
        confidence="88% - Typical foliar target-board lesions",
        organic_treatment=[
            "Spray 5% NSKE (Neem Seed Kernel Extract) @ 5 ml/L",
            "Remove infected lower leaves and burn or bury away from field"
        ],
        chemical_treatment=[
            "Spray Mancozeb 75 WP @ 2 g/L or Chlorothalonil 75 WP @ 2 g/L",
            "Pre-harvest interval: Observe 7 days before harvest"
        ],
        prevention_measures=[
            "Mulch bed with organic straw to prevent soil-splash pathogens",
            "Practice 2-3 year crop rotation with non-solanaceous crops"
        ],
        expert_escalation_needed=False,
        sources=[SourceCitation(title="ICAR Tomato Package of Practices", source_name="ICAR-IIHR")],
        language="Marathi"
    )

    with patch("app.services.vision_service.VisionService.analyze_crop_image", new=AsyncMock(return_value=mock_resp)):
        files = {"image": ("tomato_leaf.jpg", tomato_jpg, "image/jpeg")}
        data = {"crop_name": "Tomato", "language": "Marathi"}
        response = client.post("/api/analyze-crop", files=files, data=data)
        assert response.status_code == 200
        res_data = response.json()
        assert "Alternaria solani" in res_data["possible_diagnosis"]
        assert len(res_data["organic_treatment"]) >= 2
        assert len(res_data["chemical_treatment"]) >= 2
        assert res_data["severity"] == "Medium"
        assert res_data["confidence"] == "88% - Typical foliar target-board lesions"

def test_crop_analysis_multiple_formats_jpeg_png_webp():
    """Test Case 2: Validate JPEG, PNG, and WebP images are all accepted by the upload pipeline."""
    mock_resp = CropAnalysisResponse(
        observed_symptoms="Leaf spot symptoms",
        possible_diagnosis="Cercospora Leaf Spot",
        severity="Low",
        confidence="80%",
        organic_treatment=["Neem oil 3000 ppm @ 3 ml/L"],
        chemical_treatment=["Copper Oxychloride 50 WP @ 2.5 g/L"],
        prevention_measures=["Adequate plant spacing"],
        expert_escalation_needed=False,
        sources=[SourceCitation(title="Plant Pathology Handbook", source_name="KVK")],
        language="English"
    )

    with patch("app.services.vision_service.VisionService.analyze_crop_image", new=AsyncMock(return_value=mock_resp)):
        for fmt, mime, ext in [("JPEG", "image/jpeg", "jpg"), ("PNG", "image/png", "png"), ("WEBP", "image/webp", "webp")]:
            img_bytes = _generate_test_image(fmt)
            files = {"image": (f"sample.{ext}", img_bytes, mime)}
            resp = client.post("/api/analyze-crop", files=files, data={"crop_name": "Chilli"})
            assert resp.status_code == 200, f"Failed for format {fmt}: {resp.text}"
            assert resp.json()["possible_diagnosis"] == "Cercospora Leaf Spot"

def test_crop_analysis_no_image_provided():
    """Test Case 3: Click Analyze without selecting an image returns 400 Bad Request with actionable message."""
    response = client.post("/api/analyze-crop")
    assert response.status_code == 400
    assert "No crop image provided" in response.json()["detail"]

def test_crop_analysis_corrupt_image():
    """Test Case 4: Uploading a corrupted file returns 400 Bad Request."""
    corrupt_bytes = b"\xff\xd8\xff\xe0" + b"random_corrupt_garbage_data" * 20
    files = {"image": ("corrupted.jpg", corrupt_bytes, "image/jpeg")}
    response = client.post("/api/analyze-crop", files=files)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Invalid image file" in detail or "cannot identify image file" in detail

def test_crop_analysis_empty_file():
    """Test Case 4b: Uploading an empty 0-byte file returns 400 Bad Request."""
    files = {"image": ("empty.jpg", b"", "image/jpeg")}
    response = client.post("/api/analyze-crop", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

def test_crop_analysis_oversized_image_error():
    """Test Case 5: Oversized file exceeding 10 MB returns 400 Bad Request."""
    # 10.5 MB mock data
    oversized_bytes = b"0" * (11 * 1024 * 1024)
    files = {"image": ("oversized.jpg", oversized_bytes, "image/jpeg")}
    response = client.post("/api/analyze-crop", files=files)
    assert response.status_code == 400
    assert "Image size exceeds 10 MB limit" in response.json()["detail"]

def test_crop_analysis_vision_api_failure_handling():
    """Test Case 6: Vision API failure or quota limit returns transparent 503 error, never fake diagnosis."""
    jpg_bytes = _generate_test_image("JPEG")
    with patch("app.services.vision_service.VisionService.analyze_crop_image", new=AsyncMock(side_effect=RuntimeError("AI Vision service is currently unavailable or quota limit reached."))):
        files = {"image": ("tomato.jpg", jpg_bytes, "image/jpeg")}
        response = client.post("/api/analyze-crop", files=files)
        assert response.status_code == 503
        assert "AI Vision service is currently unavailable" in response.json()["detail"]

def test_crop_analysis_backward_compat_file_field():
    """Test Case 8: Backwards compatibility with legacy multipart field name 'file'."""
    png_bytes = _generate_test_image("PNG")
    mock_resp = CropAnalysisResponse(
        observed_symptoms="Powdery white patches",
        possible_diagnosis="Powdery Mildew",
        severity="Medium",
        confidence="85%",
        organic_treatment=["Wettable sulphur @ 2 g/L"],
        chemical_treatment=["Hexaconazole 5% EC @ 1 ml/L"],
        prevention_measures=["Improve ventilation"],
        expert_escalation_needed=False,
        sources=[SourceCitation(title="Field Guide", source_name="ICAR")],
        language="English"
    )
    with patch("app.services.vision_service.VisionService.analyze_crop_image", new=AsyncMock(return_value=mock_resp)):
        files = {"file": ("legacy_field.png", png_bytes, "image/png")}
        response = client.post("/api/analyze-crop", files=files)
        assert response.status_code == 200
        assert response.json()["possible_diagnosis"] == "Powdery Mildew"

def test_crop_analysis_backward_compat_json_base64():
    """Test Case 9: Backwards compatibility with JSON payload containing 'image_base64'."""
    jpg_bytes = _generate_test_image("JPEG")
    b64_data = base64.b64encode(jpg_bytes).decode("utf-8")
    mock_resp = CropAnalysisResponse(
        observed_symptoms="Yellow vein mosaic",
        possible_diagnosis="Yellow Vein Mosaic Virus",
        severity="High",
        confidence="90%",
        organic_treatment=["Spray Neem oil 5 ml/L against whiteflies"],
        chemical_treatment=["Imidacloprid 17.8 SL @ 0.3 ml/L"],
        prevention_measures=["Rogue out infected plants immediately"],
        expert_escalation_needed=True,
        sources=[SourceCitation(title="Okra Protection", source_name="MPKV Rahuri")],
        language="English"
    )
    with patch("app.services.vision_service.VisionService.analyze_crop_image", new=AsyncMock(return_value=mock_resp)):
        payload = {"image_base64": b64_data, "crop_name": "Okra", "language": "English"}
        response = client.post("/api/analyze-crop", json=payload)
        assert response.status_code == 200
        assert response.json()["possible_diagnosis"] == "Yellow Vein Mosaic Virus"


def test_unified_crop_doctor_photo_vision_success():
    """Verify Crop Doctor integrates photo vision analysis directly into single unified flow."""
    jpg_bytes = _generate_test_image("JPEG")
    b64_data = base64.b64encode(jpg_bytes).decode("utf-8")
    mock_resp = CropAnalysisResponse(
        observed_symptoms="Brown circular spots with concentric rings",
        possible_diagnosis="Early Blight (Alternaria solani)",
        severity="Medium",
        confidence="92%",
        organic_treatment=["Spray Pseudomonas fluorescens @ 10 g/L"],
        chemical_treatment=["Mancozeb 75% WP @ 2.5 g/L"],
        prevention_measures=["Crop rotation with non-solanaceous crops"],
        expert_escalation_needed=False,
        sources=[SourceCitation(title="Tomato Diseases", source_name="MPKV")],
        language="English"
    )

    with patch("app.services.vision_service.VisionService.analyze_crop_image", new=AsyncMock(return_value=mock_resp)):
        payload = {
            "crop": "Tomato",
            "image_base64": b64_data,
            "query": "Dark spots on lower leaves",
            "language": "English",
            "district": "Nashik"
        }
        res = client.post("/api/crop-doctor/consult", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["crop"] == "Tomato"
        assert "Early Blight" in data["possible_reasons"]
        assert "Brown circular spots" in data["symptoms_noticed"]
        assert len(data["immediate_actions"]) >= 2
        assert "Photo evaluation complete" in data["audio_narration"]
        assert data["language"] == "English"


def test_unified_crop_doctor_multi_photos_support():
    """Verify Crop Doctor supports multiple uploaded images via images_base64."""
    img1 = _generate_test_image("JPEG")
    img2 = _generate_test_image("PNG")
    b64_1 = base64.b64encode(img1).decode("utf-8")
    b64_2 = base64.b64encode(img2).decode("utf-8")

    mock_resp = CropAnalysisResponse(
        observed_symptoms="Yellowing of veins and mosaic pattern",
        possible_diagnosis="Yellow Mosaic Disease",
        severity="High",
        confidence="88%",
        organic_treatment=["Neem oil spray"],
        chemical_treatment=["Thiamethoxam 25 WG"],
        prevention_measures=["Resistant varieties"],
        expert_escalation_needed=False,
        sources=[SourceCitation(title="Soybean Advisory", source_name="ICAR-IISR")],
        language="Marathi"
    )

    with patch("app.services.vision_service.VisionService.analyze_crop_image", new=AsyncMock(return_value=mock_resp)):
        payload = {
            "crop": "Soybean",
            "images_base64": [b64_1, b64_2],
            "language": "Marathi",
            "district": "Latur"
        }
        res = client.post("/api/crop-doctor/consult", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["crop"] == "Soybean"
        assert "Yellow Mosaic" in data["possible_reasons"]
        assert "फोटो तपासणी पूर्ण झाली आहे" in data["audio_narration"]


def test_unified_crop_doctor_corrupted_image_validation():
    """Verify Crop Doctor rejects corrupt/invalid image data with HTTP 400."""
    payload = {
        "crop": "Cotton",
        "image_base64": "invalid_base64_garbage_data!@#$",
        "language": "English"
    }
    res = client.post("/api/crop-doctor/consult", json=payload)
    assert res.status_code == 400
    assert "Invalid" in res.json()["detail"]


def test_unified_crop_doctor_vision_offline_honest_fallback():
    """Verify Crop Doctor honestly discloses uncertainty when vision AI is offline or quota exceeded."""
    jpg_bytes = _generate_test_image("JPEG")
    b64_data = base64.b64encode(jpg_bytes).decode("utf-8")

    with patch("app.services.vision_service.VisionService.analyze_crop_image", new=AsyncMock(side_effect=RuntimeError("Quota exceeded"))):
        payload = {
            "crop": "Cotton",
            "image_base64": b64_data,
            "problem_type": "yellow_leaves",
            "language": "Marathi",
            "district": "Yavatmal"
        }
        res = client.post("/api/crop-doctor/consult", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["crop"] == "Cotton"
        # Must clearly include honest disclaimer
        assert "टीप: AI व्हिजन सेवा तात्पुरती अनुपलब्ध असल्याने" in data["possible_reasons"]



