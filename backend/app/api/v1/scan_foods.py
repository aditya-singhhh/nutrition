from __future__ import annotations

import hashlib
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.providers import AIGateway, DishCandidate, ProviderError, ProviderNotConfigured
from app.api.deps import current_user, decode_image_b64, get_db, get_gateway, read_image
from app.core.config import get_settings
from app.domain.barcode import InvalidBarcode, normalize_barcode
from app.domain.label import parse_label_nutrition
from app.domain.compat import FoodView, evaluate_personal
from app.domain.ingredients import analyze_ingredients
from app.domain.nutrition import round_nutrients, scale_range
from app.domain.scoring import score_food
from app.models import FoodItem, ModelPrediction, PackagedProduct, User
from app.schemas import AnalyzeIn, BarcodeIn, LabelTextIn, SmartScanIn
from app.services import catalog, openfoodfacts
from app.services.audit import audit
from app.services.scan_log import record_scan
from app.services.catalog import user_context

logger = logging.getLogger(__name__)
router = APIRouter()

LOW_CONFIDENCE = 0.5


def _barcode_or_422(raw: str) -> str:
    try:
        return normalize_barcode(raw)
    except InvalidBarcode as e:
        raise HTTPException(422, str(e)) from None


def _product_or_404(db: Session, code: str):
    prod = catalog.get_product(db, code)
    if prod is None and get_settings().off_lookup:
        prod = openfoodfacts.lookup_and_store(db, code)
    if prod is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, {
            "code": "product_not_found", "barcode": code,
            "message": "We don't have this product yet. Scan its ingredient label to analyse it."})
    return prod


# ------------------------------------------------------------------ foods & products
@router.get("/foods", tags=["foods"])
def list_foods(q: str = Query(min_length=1, max_length=80), limit: int = Query(10, ge=1, le=50),
               _: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"items": [catalog.food_summary(f) for f in catalog.search_foods(db, q, limit)]}


@router.get("/foods/{food_id}", tags=["foods"])
def get_food(food_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    f = catalog.get_food(db, food_id)
    if f is None:
        raise HTTPException(404, "food not found")
    return catalog.evaluate_food(f, user_context(user))


@router.get("/products/{barcode}", tags=["products"])
def get_product(barcode: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    prod = _product_or_404(db, _barcode_or_422(barcode))
    return catalog.evaluate_product(prod, user_context(user))


@router.post("/scan/barcode", tags=["scan"])
def scan_barcode(body: BarcodeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    code = _barcode_or_422(body.barcode)
    try:
        prod = _product_or_404(db, code)
    except HTTPException:
        record_scan(db, user, "barcode", barcode=code, outcome={"found": False})  # missing products are the most useful signal
        raise
    audit(db, user.id, "scan_barcode", "product", prod.id)
    out = catalog.evaluate_product(prod, user_context(user))
    record_scan(db, user, "barcode", barcode=code,
                outcome={"found": True, "source": prod.source, "score": out["quality_score"].get("score")})
    return out


@router.post("/food/analyze", tags=["foods"])
def analyze_food(body: AnalyzeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ctx = user_context(user)
    if body.food_slug:
        f = catalog.get_food_by_slug(db, body.food_slug)
        if f is None:
            raise HTTPException(404, "food not found")
        g = body.grams if body.grams is not None else (body.servings or 1) * f.serving_g
        return catalog.evaluate_food(f, ctx, grams=g)
    prod = _product_or_404(db, _barcode_or_422(body.barcode or ""))
    g = body.grams if body.grams is not None else (body.servings or 1) * (prod.serving_g or 100.0)
    return catalog.evaluate_product(prod, ctx, grams=g)


# ------------------------------------------------------------------ label OCR / ingredient analysis
def analyze_label_text(text: str, user: User, nutrients: dict | None) -> dict:
    analysis = analyze_ingredients(text)
    ctx = user_context(user)
    per100 = nutrients or {}
    score = score_food(per100, nova=analysis.estimated_nova, additives=analysis.additives,
                       ingredient_flags=analysis.flags, ingredients_known=bool(analysis.ingredients), verified=False)
    compat = evaluate_personal(FoodView("Scanned product", per100, allergens=analysis.allergens,
                                        may_contain=analysis.may_contain), ctx)
    return {
        "ingredients": analysis.to_dict(),
        "quality_score": score,
        "score_is_partial": not nutrients,
        "personal_compatibility": compat,
        "data_quality": {"source": "user_scan", "confidence": "ai_extracted" if nutrients is None else "user_submitted",
                         "verified": False,
                         "warning": "Parsed from a scanned/typed label and not verified. Check it against the pack."},
    }


@router.post("/scan/label-text", tags=["scan"])
def scan_label_text(body: LabelTextIn, user: User = Depends(current_user)):
    return analyze_label_text(body.text, user, body.nutrients_per_100g)


@router.post("/scan/label", tags=["scan"])
def scan_label(image: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db),
               gw: AIGateway = Depends(get_gateway)):
    data = read_image(image, get_settings().max_upload_bytes)
    try:
        ocr = gw.ocr.extract_text(data)
    except ProviderNotConfigured as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from None
    except ProviderError as e:
        logger.warning("OCR failed: %s", e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "label reading failed, please try again") from None
    pred = ModelPrediction(user_id=user.id, kind="label_ocr", model_name=gw.ocr.name, model_version=gw.ocr.version,
                           confidence=ocr.confidence, input_type="image",
                           input_digest=hashlib.sha256(data).hexdigest(), output={"chars": len(ocr.text)})
    db.add(pred)
    db.commit()
    out = analyze_label_text(ocr.text, user, None)
    out.update({"prediction_id": pred.id, "extracted_text": ocr.text, "ocr_confidence": ocr.confidence,
                "note": "Please check the extracted text; you can correct it and re-submit to /scan/label-text."})
    return out


# ------------------------------------------------------------------ food photo
def _known_foods(db: Session) -> list[tuple[str, str]]:
    return [(f.slug, f.name) for f in db.scalars(select(FoodItem))]


def _call_provider(fn):
    try:
        return fn()
    except ProviderNotConfigured as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from None
    except ProviderError as e:
        logger.warning("provider failed: %s", e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Recognition service problem: {e}") from None


def _food_response(db: Session, user: User, gw: AIGateway, data: bytes, cands: list, unmatched_names: list | None = None) -> dict:
    items, unknown = [], list(unmatched_names or [])
    for c in cands:
        f = catalog.get_food_by_slug(db, c.food_slug)
        if f is None:  # model proposed a dish we have no verified data for - never invent nutrition for it
            unknown.append(c.food_slug)
            continue
        lo, hi = sorted((c.portion_g_min, c.portion_g_max))
        rng = scale_range(f.nutrients_per_100g, lo, hi)
        items.append({
            "food": catalog.food_summary(f), "confidence": round(c.confidence, 3),
            "needs_confirmation": c.confidence < LOW_CONFIDENCE,
            "portion_g_range": [lo, hi],
            "nutrition_range": {"min": round_nutrients(rng["min"]), "max": round_nutrients(rng["max"])},
            "data_quality": catalog.data_quality(f),
        })
    pred = ModelPrediction(
        user_id=user.id, kind="food_photo", model_name=gw.vision.name, model_version=gw.vision.version,
        confidence=max((c.confidence for c in cands), default=None), input_type="image",
        input_digest=hashlib.sha256(data).hexdigest(),
        output={"items": [{"slug": i["food"]["slug"], "confidence": i["confidence"], "portion": i["portion_g_range"]}
                          for i in items], "unknown_slugs": unknown})
    db.add(pred)
    db.commit()
    return {"kind": "food", "prediction_id": pred.id, "items": items, "unrecognised": unknown,
            "message": "Portions are estimates, not exact weights. Please confirm or correct the items before logging.",
            "correction_endpoint": f"/api/v1/predictions/{pred.id}/feedback"}


@router.post("/scan/food-photo", tags=["scan"])
def scan_food_photo(image: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db),
                    gw: AIGateway = Depends(get_gateway)):
    data = read_image(image, get_settings().max_upload_bytes)
    cands = _call_provider(lambda: gw.vision.detect_dishes(data, _known_foods(db)))
    return _food_response(db, user, gw, data, cands)


@router.post("/scan/smart", tags=["scan"])
def scan_smart(body: SmartScanIn, user: User = Depends(current_user), db: Session = Depends(get_db),
               gw: AIGateway = Depends(get_gateway)):
    """One scan button: the photo is food (-> dish estimates) or a label (-> ingredient analysis). Base64 JSON body,
    which is more reliable than multipart from React Native."""
    data = decode_image_b64(body.image_base64, get_settings().max_upload_bytes)
    res = _call_provider(lambda: gw.vision.smart(data, _known_foods(db)))
    ctx = user_context(user)
    if res.kind == "product":
        code = _barcode_or_422(res.barcode)
        try:
            prod = _product_or_404(db, code)
        except HTTPException:
            record_scan(db, user, "product", barcode=code, model=gw.vision.name, image=data, outcome={"found": False})
            raise
        audit(db, user.id, "scan_barcode", "product", prod.id)
        out = {**catalog.evaluate_product(prod, ctx), "kind": "product"}
        record_scan(db, user, "product", barcode=code, model=gw.vision.name, image=data,
                    outcome={"found": True, "source": prod.source, "score": out["quality_score"].get("score")})
        return out
    if res.kind == "food":
        dishes, names = list(res.dishes), []
        have = {d.food_slug for d in dishes}
        for g in res.unmatched:  # model named a dish without a valid id: try our own name/alias search
            hit = next(iter(catalog.search_foods(db, g.name, 1)), None)
            if hit is not None and hit.slug not in have:
                dishes.append(DishCandidate(hit.slug, g.confidence * 0.85, g.portion_g_min, g.portion_g_max))
                have.add(hit.slug)
            elif hit is None:
                names.append(g.name)
        out = _food_response(db, user, gw, data, dishes, names)
        record_scan(db, user, "food", model=gw.vision.name, image=data, prediction_id=out["prediction_id"],
                    extracted={"dishes": [d.food_slug for d in dishes], "unmatched": names},
                    outcome={"items": [i["food"]["slug"] for i in out["items"]]})
        return out
    if res.kind == "label":
        ln = parse_label_nutrition(res.label_nutrition)
        per100 = ln.per_100g or None
        out = analyze_label_text(res.label_text, user, per100)
        if per100:
            out["data_quality"] = {"source": "label_scan", "confidence": "ai_read_label", "verified": False,
                                   "warning": "Read from your photo by AI and not verified. Check the numbers against the pack."}
            out["nutrition_per_100g"] = per100
            if ln.serving_g and ln.per_serving:
                out["portion"] = {"grams": ln.serving_g, "label": "1 serving"}
                out["nutrition_for_portion"] = ln.per_serving
        out["name"] = res.product_name or "Scanned label"
        pred = ModelPrediction(user_id=user.id, kind="label_ocr", model_name=gw.vision.name, model_version=gw.vision.version,
                               confidence=None, input_type="image", input_digest=hashlib.sha256(data).hexdigest(),
                               output={"chars": len(res.label_text), "basis": ln.basis})
        db.add(pred)
        db.commit()
        out.update({"kind": "label", "prediction_id": pred.id, "extracted_text": res.label_text,
                    "label_nutrition": ln.to_dict(), "label_warnings": ln.warnings,
                    "note": "Please check what we read against the pack."})
        code = None
        try:
            code = normalize_barcode(body.barcode) if body.barcode else None
        except InvalidBarcode:
            code = None
        prod = None
        if code and per100 and "energy_kcal" in per100 and catalog.get_product(db, code) is None:
            prod = PackagedProduct(  # remember it so the next person who scans this barcode gets an answer
                barcode=code, brand="Unknown", name=(res.product_name or "Scanned product")[:160], category="packaged",
                serving_g=ln.serving_g, nutrients_per_100g=per100, ingredients_text=res.label_text or None, allergens=[],
                additives=[], nova=None, country="IN", source="user_label_scan", confidence="ai_read_label", verified=False)
            db.add(prod)
            db.commit()
            out = {**catalog.evaluate_product(prod, ctx), "kind": "product", "created_from_label": True,
                   "extracted_text": res.label_text, "label_nutrition": ln.to_dict(), "label_warnings": ln.warnings,
                   "prediction_id": pred.id}
        record_scan(db, user, "label", barcode=code, model=gw.vision.name, image=data, prediction_id=pred.id,
                    extracted={"text": res.label_text, "nutrition": res.label_nutrition, "parsed": ln.to_dict()},
                    outcome={"score": out["quality_score"].get("score"), "warnings": ln.warnings,
                             "saved_as_product": prod is not None})
        return out
    record_scan(db, user, "none", model=gw.vision.name, image=data, outcome={"recognised": False})
    raise HTTPException(422, {"code": "nothing_recognised",
                              "message": "We couldn't recognise this picture. Food photos, ingredient labels and barcode numbers work best, in good light."})


_status_cache: dict = {}


@router.get("/ai/status", tags=["scan"])
def ai_status(image: bool = False, gw: AIGateway = Depends(get_gateway)):
    """Open in a browser to see whether food-photo recognition works and which model/endpoint is in use. Add ?image=true to also test image input.
    Reveals no secrets. Cached for 60 s so it can't be used to burn quota."""
    import time
    now = time.time()
    hit = _status_cache.get(image)
    if hit is None or now - hit[0] > 60:
        hit = _status_cache[image] = (now, gw.status(image))
    return hit[1]
