"""
publish_merch.py — Printful API integration for Arion World merch automation.

Zero-investment print-on-demand: products are only manufactured when ordered.
Per episode, picks the 3 most visually striking scene images, composites
branding via generate_merch_designs, uploads to Printful, and creates/updates
a t-shirt, poster, and mug for that episode.

Requires:
  PRINTFUL_API_KEY  — Printful store API key (Bearer token)

Optional:
  PRINTFUL_STORE_ID — if you have multiple stores; otherwise uses default store
"""

import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Optional

import requests

from generate_merch_designs import generate_merch_designs

logger = logging.getLogger(__name__)

# Alternatively: Printify API at https://developers.printify.com/ — broader catalog, similar workflow
PRINTFUL_API = "https://api.printful.com"

# ---------------------------------------------------------------------------
# Printful product type IDs
# ---------------------------------------------------------------------------
PRODUCT_TYPES = {
    "tshirt": {
        "catalog_variant_id": 4011,   # Bella+Canvas 3001 Unisex — M, Black (common default)
        "catalog_product_id": 71,
        "placement": "front",
        "label": "T-Shirt",
        "design_key": "square",       # use square crop
        "position": {
            "area_width": 1800,
            "area_height": 2400,
            "width": 1800,
            "height": 1800,
            "top": 300,
            "left": 0,
        },
    },
    "poster": {
        "catalog_variant_id": 2,      # 18×24 poster (product 1, variant 2)
        "catalog_product_id": 1,
        "placement": "front",
        "label": "Poster 18×24",
        "design_key": "poster",       # use full/poster crop
        "position": {
            "area_width": 1800,
            "area_height": 2400,
            "width": 1800,
            "height": 2400,
            "top": 0,
            "left": 0,
        },
    },
    "mug": {
        "catalog_variant_id": 1320,   # 11oz mug (product 19, variant 1320)
        "catalog_product_id": 19,
        "placement": "front",
        "label": "Mug 11oz",
        "design_key": "square",       # use square crop
        "position": {
            "area_width": 2000,
            "area_height": 1000,
            "width": 2000,
            "height": 1000,
            "top": 0,
            "left": 0,
        },
    },
}


# ---------------------------------------------------------------------------
# Auth / session
# ---------------------------------------------------------------------------

def _get_headers() -> dict:
    api_key = os.environ.get("PRINTFUL_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError("PRINTFUL_API_KEY not set")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _api_get(path: str) -> dict:
    resp = requests.get(f"{PRINTFUL_API}{path}", headers=_get_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def _api_post(path: str, payload: dict) -> dict:
    resp = requests.post(
        f"{PRINTFUL_API}{path}",
        headers=_get_headers(),
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Public helper: store product listing
# ---------------------------------------------------------------------------

def get_store_products() -> list[dict]:
    """Return the list of products already in the Printful store."""
    data = _api_get("/store/products")
    return data.get("result", [])


# ---------------------------------------------------------------------------
# Upload design image to Printful Files API
# ---------------------------------------------------------------------------

def upload_design_image(image_path: Path) -> str:
    """
    Upload a local image to Printful and return the file ID.
    Uses the Printful Files API which accepts multipart or URL uploads.
    Here we do a two-step: post as base64 via the files endpoint.
    """
    import base64

    image_path = Path(image_path)
    with open(image_path, "rb") as f:
        data = f.read()

    encoded = base64.b64encode(data).decode()
    filename = image_path.name

    payload = {
        "type": "default",
        "filename": filename,
        "contents": encoded,
    }

    result = _api_post("/files", payload)
    file_id = result["result"]["id"]
    logger.info("Uploaded design to Printful: file_id=%s  filename=%s", file_id, filename)
    return str(file_id)


# ---------------------------------------------------------------------------
# Create or update a single Printful store product
# ---------------------------------------------------------------------------

def create_or_update_product(
    design_path: Path,
    product_name: str,
    episode_number: int,
    product_type_key: str = "tshirt",
) -> Optional[str]:
    """
    Create (or update if name already exists) a Printful store product.

    Returns the product URL on the Printful store, or None on failure.
    """
    ptype = PRODUCT_TYPES[product_type_key]

    # Check if a product with this name already exists
    existing = get_store_products()
    existing_id = None
    for p in existing:
        if p.get("name") == product_name:
            existing_id = p.get("id")
            break

    # Upload the design file
    file_id = upload_design_image(design_path)

    variant_payload = {
        "catalog_variant_id": ptype["catalog_variant_id"],
        "files": [
            {
                "placement": ptype["placement"],
                "id": file_id,
                "position": ptype["position"],
            }
        ],
    }

    if existing_id:
        # Update existing product variants
        logger.info("Updating existing Printful product id=%s  name=%s", existing_id, product_name)
        result = _api_post(
            f"/store/products/{existing_id}",
            {
                "sync_product": {"name": product_name},
                "sync_variants": [variant_payload],
            },
        )
    else:
        # Create new product
        logger.info("Creating new Printful product: %s", product_name)
        result = _api_post(
            "/store/products",
            {
                "sync_product": {
                    "name": product_name,
                    "thumbnail": str(file_id),
                },
                "sync_variants": [variant_payload],
            },
        )

    product_id = result.get("result", {}).get("id") or (existing_id)
    if product_id:
        store_id = os.environ.get("PRINTFUL_STORE_ID", "")
        url = f"https://www.printful.com/dashboard/products/{product_id}"
        logger.info("Product ready: %s", url)
        return url
    return None


# ---------------------------------------------------------------------------
# Scene image selection
# ---------------------------------------------------------------------------

def _pick_striking_images(image_files: list[Path], episode_data: dict, count: int = 3) -> list[Path]:
    """
    Pick the `count` most visually striking images for merch.

    Selection priority:
      1. Images whose scene metadata includes "action" in plot_significance
      2. Images associated with scenes that have a high character count
      3. Fall back to evenly-spaced selection across the list
    """
    scenes: list[dict] = episode_data.get("scenes", [])

    # Build a score map keyed by image index (approximating scene order)
    scores: list[tuple[int, Path]] = []
    for i, img_path in enumerate(image_files):
        score = 0
        # Try to correlate image index to a scene
        if i < len(scenes):
            scene = scenes[i]
            plot_sig = scene.get("plot_significance", "").lower()
            if "action" in plot_sig:
                score += 10
            if "climax" in plot_sig or "reveal" in plot_sig:
                score += 8
            if "battle" in plot_sig or "fight" in plot_sig:
                score += 6
            characters = scene.get("characters_in_scene", [])
            score += min(len(characters), 5)  # up to 5 points for character count
        scores.append((score, img_path))

    scores.sort(key=lambda x: x[0], reverse=True)
    selected = [p for _, p in scores[:count]]

    # If fewer images than requested, pad with what we have
    if len(selected) < count and image_files:
        for p in image_files:
            if p not in selected:
                selected.append(p)
            if len(selected) >= count:
                break

    return selected[:count]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def publish_merch_for_episode(episode_data: dict, image_files: list[Path]) -> list[str]:
    """
    Main entry point called from the episode pipeline.

    Picks 3 best scene images, generates branded designs, creates Printful
    products (t-shirt, poster, mug) for each, and returns a list of product URLs.

    If PRINTFUL_API_KEY is not set, logs a warning and returns [].
    """
    if not os.environ.get("PRINTFUL_API_KEY", "").strip():
        logger.warning(
            "PRINTFUL_API_KEY not set — skipping merch publishing. "
            "See MANUAL_ACTIONS_REQUIRED.md to set up Printful."
        )
        return []

    ep_num = episode_data.get("episode_number", 0)
    ep_title = episode_data.get("title", f"Episode {ep_num}")
    image_files = [Path(p) for p in image_files if Path(p).exists()]

    if not image_files:
        logger.warning("No valid image files provided for episode %s merch.", ep_num)
        return []

    logger.info("Selecting images for episode %s merch...", ep_num)
    selected = _pick_striking_images(image_files, episode_data, count=3)
    logger.info("Selected %d image(s) for merch: %s", len(selected), [str(p) for p in selected])

    product_urls: list[str] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        for img_index, scene_img in enumerate(selected, start=1):
            logger.info("Processing merch for image %d/%d: %s", img_index, len(selected), scene_img.name)

            # Generate branded designs
            try:
                designs = generate_merch_designs(
                    image_path=scene_img,
                    episode_number=ep_num,
                    episode_title=ep_title,
                    output_dir=tmp_path,
                )
            except Exception as e:
                logger.error("Design generation failed for %s: %s", scene_img, e)
                continue

            if not designs:
                continue

            # Create products for each type
            for ptype_key, ptype_info in PRODUCT_TYPES.items():
                design_key = ptype_info["design_key"]
                design_path = designs.get(design_key)
                if not design_path or not design_path.exists():
                    logger.warning("Design file missing for %s/%s — skipping.", ptype_key, design_key)
                    continue

                product_name = (
                    f"Arion World — Episode {ep_num} — {ptype_info['label']} (Scene {img_index})"
                )

                try:
                    url = create_or_update_product(
                        design_path=design_path,
                        product_name=product_name,
                        episode_number=ep_num,
                        product_type_key=ptype_key,
                    )
                    if url:
                        product_urls.append(url)
                        logger.info("Product published: %s → %s", product_name, url)
                except Exception as e:
                    logger.error("Failed to publish product '%s': %s", product_name, e)

    logger.info(
        "Merch publishing complete for episode %s. %d product(s) created/updated.",
        ep_num,
        len(product_urls),
    )
    return product_urls
