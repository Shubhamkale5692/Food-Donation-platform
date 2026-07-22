"""
FoodBridge AI API Router

Endpoints:
  POST /api/v1/ai/analyze-image        - 4-layer food freshness analysis
  POST /api/v1/ai/check-food-freshness - Legacy compatibility endpoint
  GET  /api/v1/ai/hunger-heatmap
  POST /api/v1/ai/fraud-check
  GET  /api/v1/ai/recommendations
  GET  /api/v1/ai/impact-insights
  POST /api/v1/ai/assign-volunteer
"""

import inspect
import os
from typing import Any, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.services.ai_service import AIService
from app.domain import schemas
from app.interfaces.deps import get_current_user, get_db
from app.domain.models import User, RoleEnum

router = APIRouter()


# ---
# NEW: 4-Layer AI Image Analysis
# ---
@router.post("/analyze-image", response_model=schemas.AiImageAnalysisResponse)
async def analyze_food_image(
    file: UploadFile = File(...),
    image_source: str = Form(default="upload"),  # "camera" | "upload"
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    AI Module 2 (Upgraded): 4-Layer Food Freshness Analysis

    Accepts a raw image file (multipart/form-data) and runs:
      Layer 1 - Image source validation
      Layer 2 - EXIF metadata timestamp check
      Layer 3 - MobileNetV2 CNN classification simulation
      Layer 4 - Confidence scoring + duplicate hash detection

    Returns freshness_status, confidence_score, probabilities, warnings.
    """
    # ---
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded file must be an image. Received: {content_type}",
        )

    # Whitelist: only jpg/jpeg/png are supported by the AI analysis pipeline
    _allowed_exts = {"jpg", "jpeg", "png"}
    _file_ext = os.path.splitext(file.filename or "")[1].lstrip(".").lower()
    if _file_ext not in _allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Only JPG and PNG images are supported by the AI pipeline. Got: .{_file_ext or 'unknown'}",
        )

    # Security check: Limit size before full processing (10MB) - Check header first
    content_length = file.headers.get("content-length")
    if content_length and int(content_length) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (Max 10MB)")

    file_data = await file.read()
    if len(file_data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (Max 10MB)")

    # ---
    # Run the full AI pipeline instead of returning static mock values.
    analysis = AIService.analyze_food_image(
        image_bytes=file_data,
        image_source=image_source,
        db=db,
        filename=file.filename or "",
    )
    return analysis


# ---
# LEGACY: kept for existing frontend compatibility
# ---
@router.post("/check-food-freshness", response_model=schemas.AiFreshnessResponse)
def check_food_freshness(
    payload: schemas.AiFreshnessRequest,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    AI Module 2 (Legacy): Food Freshness Detection
    Kept for backwards compatibility - use /analyze-image for the full pipeline.
    """
    result = AIService.check_food_freshness(payload.image_url)
    return result


@router.post("/assign-volunteer", response_model=schemas.AiVolunteerAssignmentResponse)
async def assign_volunteer_ai(
    payload: schemas.AiVolunteerAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    AI volunteer assignment for an accepted donation.
    """
    if current_user.role != RoleEnum.NGO:
        raise HTTPException(
            status_code=403, detail="Only NGOs can use AI volunteer assignment"
        )

    assigned = AIService.assign_best_volunteer(
        db=db, donation_id=payload.donation_id, ngo_id=current_user.id
    )
    if inspect.isawaitable(assigned):
        assigned = await assigned
    if not assigned:
        raise HTTPException(
            status_code=400,
            detail="Unable to assign volunteer for this donation",
        )
    return assigned


# ---
# ---
# ---
@router.get("/hunger-heatmap", response_model=List[schemas.AiHeatmapPoint])
def hunger_heatmap(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """AI Module 3: Donation Demand Prediction (Time-series Mock)"""
    return AIService.get_hunger_heatmap(db)


# ---
# ---
# ---
@router.post("/fraud-check", response_model=schemas.AiFraudCheckResponse)
def fraud_check(
    payload: schemas.AiFraudCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """AI Module 4: Fraud Detection System"""
    return AIService.check_fraud(db, payload.user_id)


# ---
# ---
# ---
@router.get("/recommendations", response_model=schemas.AiRecommendationsResponse)
def get_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """AI Module 5: Smart Recommendation Engine"""
    return AIService.get_recommendations(db, current_user.id)


# ---
# ---
# ---
@router.get("/impact-insights", response_model=schemas.AiImpactInsightsResponse)
def get_impact_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """AI Module 6: Impact Analytics AI"""
    return AIService.get_impact_insights(db)
