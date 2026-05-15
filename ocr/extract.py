from __future__ import annotations

import logging
import re
from inspect import signature
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import numpy as np
import pdfplumber
import pypdfium2 as pdfium
import pytesseract
from PIL import Image
from pytesseract import TesseractError, TesseractNotFoundError

from .detect_pdf_type import detect_pdf_type

logger = logging.getLogger(__name__)

try:
    import cv2
except ImportError:  # pragma: no cover - depends on runtime package availability
    cv2 = None

try:
    from paddleocr import PaddleOCR
except ImportError:  # pragma: no cover - depends on runtime package availability
    PaddleOCR = None

_MIN_DIRECT_TEXT_CHARS = 80
_PADDLE_OCR = None
_PADDLE_OCR_INIT_FAILED = False
_PADDLE_OCR_RUNNER = None
_PADDLE_OCR_RUNNER_NAME = "uninitialized"
_DEBUG_DIR = Path("uploads") / "debug"


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_text_pdfplumber(data: bytes) -> tuple[str, list[dict]]:
    parts: list[str] = []
    pages: list[dict] = []
    with pdfplumber.open(BytesIO(data)) as pdf:
        for index, page in enumerate(pdf.pages):
            try:
                raw_text = page.extract_text() or ""
                table_rows = page.extract_tables() or []
            except Exception as exc:
                logger.warning("pdfplumber page %d failed: %s", index, exc)
                raw_text = ""
                table_rows = []

            page_parts: list[str] = []
            if raw_text.strip():
                page_parts.append(raw_text.strip())

            for table in table_rows:
                normalized_rows = []
                for row in table:
                    cells = [cell.strip() for cell in row if cell and cell.strip()]
                    if cells:
                        normalized_rows.append(" | ".join(cells))
                if normalized_rows:
                    page_parts.append("\n".join(normalized_rows))

            page_text = "\n".join(page_parts).strip()
            pages.append(
                {
                    "page_number": index + 1,
                    "text": page_text,
                    "confidence": 1.0 if page_text else 0.0,
                    "engine": "pdfplumber",
                }
            )
            if page_text:
                parts.append(page_text)

    return _clean_text("\n\n".join(parts)), pages


def _get_paddle_ocr():
    global _PADDLE_OCR, _PADDLE_OCR_INIT_FAILED
    if PaddleOCR is None:
        logger.warning("PaddleOCR import unavailable; falling back to pytesseract OCR.")
        print("PaddleOCR import unavailable; falling back to pytesseract OCR.")
        return None
    if _PADDLE_OCR_INIT_FAILED:
        return None
    if _PADDLE_OCR is None:
        init_signature = signature(PaddleOCR.__init__)
        base_kwargs = {"lang": "en"}
        if "use_doc_orientation_classify" in init_signature.parameters:
            base_kwargs["use_doc_orientation_classify"] = False
        if "use_doc_unwarping" in init_signature.parameters:
            base_kwargs["use_doc_unwarping"] = False
        # NOTE: return_word_box is intentionally NOT set at init time.
        # Passing an unsupported kwarg at init permanently breaks the singleton
        # instance.  Word-level boxes are requested at call time inside
        # _run_paddle_ocr() where failures can be caught and retried safely.
        logger.info("[OCR-INIT] Initializing PaddleOCR (word-level boxes will be requested at call time)")

        init_attempts = []
        if "use_textline_orientation" in init_signature.parameters:
            init_attempts.append(("textline_orientation", {**base_kwargs, "use_textline_orientation": True}))
            init_attempts.append(("plain_predict", {**base_kwargs, "use_textline_orientation": False}))
        elif "use_angle_cls" in init_signature.parameters:
            init_attempts.append(("angle_cls", {**base_kwargs, "use_angle_cls": True}))
            init_attempts.append(("plain_predict", {**base_kwargs, "use_angle_cls": False}))
        else:
            init_attempts.append(("plain_predict", base_kwargs))

        last_exc = None
        for mode_name, init_kwargs in init_attempts:
            try:
                _PADDLE_OCR = PaddleOCR(**init_kwargs)
                logger.info("PaddleOCR initialized with mode=%s kwargs=%s", mode_name, list(init_kwargs.keys()))
                break
            except Exception as exc:
                last_exc = exc
                logger.warning("PaddleOCR initialization attempt failed for mode=%s: %s", mode_name, exc)

        if _PADDLE_OCR is None:
            _PADDLE_OCR_INIT_FAILED = True
            logger.error("PaddleOCR initialization failed after compatibility fallbacks: %s", last_exc)
            print(f"PaddleOCR initialization failed: {last_exc}")
            return None
    return _PADDLE_OCR


def _resolve_paddle_runner(ocr) -> tuple[object | None, str]:
    if hasattr(ocr, "predict") and callable(ocr.predict):
        return ocr.predict, "predict"
    if hasattr(ocr, "ocr") and callable(ocr.ocr):
        return ocr.ocr, "ocr"
    return None, "unavailable"


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_box_like(value) -> bool:
    if not isinstance(value, (list, tuple)) or not value:
        return False
    first = value[0]
    return isinstance(first, (list, tuple)) and len(first) >= 2


def _coerce_box(value):
    if not _is_box_like(value):
        return None

    points: list[list[float]] = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return None
        points.append([_safe_float(point[0]), _safe_float(point[1])])
    return points or None


def _append_normalized_entry(normalized: list[dict], text, score=0.0, box=None) -> bool:
    if not isinstance(text, str):
        return False

    cleaned_text = _clean_text(text)
    if not cleaned_text:
        return False
    normalized.append(
        {
            "text": cleaned_text,
            "confidence": _safe_float(score, 0.0),
            "box": _coerce_box(box),
        }
    )
    return True


def _append_from_structured_dict(normalized: list[dict], item) -> bool:
    """Extract OCR entries from a PaddleOCR structured-dict result item.

    When ``return_word_box=True`` is active PaddleOCR injects a ``word_result``
    list inside each line-level result.  Each entry of ``word_result`` has the
    shape ``{"word": str, "word_box": [[x,y],...], "word_score": float}``.
    We try to extract word-level entries first; if none are present we fall
    back to the standard line-level ``rec_texts`` / ``dt_polys`` fields.
    """
    if not hasattr(item, "get"):
        return False

    # ------------------------------------------------------------------
    # Priority 1: word_result (produced when return_word_box=True)
    # ------------------------------------------------------------------
    word_result = item.get("word_result")
    if isinstance(word_result, (list, tuple)) and word_result:
        parsed_any = False
        for widx, wentry in enumerate(word_result):
            if not hasattr(wentry, "get"):
                continue
            word_text = wentry.get("word") or wentry.get("text") or ""
            word_box  = wentry.get("word_box") or wentry.get("box")
            word_score = _safe_float(wentry.get("word_score") or wentry.get("score"), 0.0)
            if _append_normalized_entry(normalized, word_text, word_score, word_box):
                parsed_any = True
                logger.debug(
                    "[OCR-WORD] word[%d] text=%r score=%.4f box=%s",
                    widx, word_text, word_score, word_box,
                )
        if parsed_any:
            return True

    # ------------------------------------------------------------------
    # Priority 2: standard line-level fields (rec_texts / dt_polys)
    # ------------------------------------------------------------------
    boxes = item.get("dt_polys") or item.get("boxes") or item.get("polys")
    texts = item.get("rec_texts")
    if texts is None:
        texts = item.get("texts")
    scores = item.get("rec_scores")
    if scores is None:
        scores = item.get("scores")

    if texts is None:
        return False

    if not isinstance(texts, (list, tuple)):
        texts = [texts]
    if not isinstance(scores, (list, tuple)):
        scores = [scores] * len(texts)
    if not isinstance(boxes, (list, tuple)):
        boxes = [boxes] * len(texts)

    parsed_any = False
    for idx, text in enumerate(texts):
        score = scores[idx] if idx < len(scores) else 0.0
        box = boxes[idx] if idx < len(boxes) else None
        parsed_any = _append_normalized_entry(normalized, text, score, box) or parsed_any
    return parsed_any


def _extract_word_boxes_from_paddle(result) -> list[dict]:
    """Walk any PaddleOCR result shape and collect word-level bounding boxes.

    When PaddleOCR is run with ``return_word_box=True`` it may return results
    in several structures depending on the version:

    * PaddleOCR >= 2.7  (.ocr method)::

        [  # per page
          [  # per line
            (box4pt, ('text', score), [word_result_list])
          ]
        ]

      where ``word_result_list`` is a list of
      ``(word_box4pt, ('word', word_score))`` pairs.

    * PaddleOCR PP-OCRv4  (.ocr method)::

        [  # per page
          [  # per line
            {'transcription': str, 'points': box, 'score': float,
             'word_result': [{word, word_box, word_score}, ...]}
          ]
        ]

    Returns a flat list of ``{text, confidence, box}`` dicts at word
    granularity.  Falls back to an empty list if no word boxes are found,
    which causes the caller to fall back to line-level extraction.
    """
    words: list[dict] = []

    def _try_word_result_list(wlist):
        """Parse a word_result list from any known format."""
        found = False
        for wentry in wlist or []:
            # Dict format: {word, word_box, word_score}
            if hasattr(wentry, "get"):
                wtext  = wentry.get("word") or wentry.get("text") or ""
                wbox   = wentry.get("word_box") or wentry.get("box")
                wscore = _safe_float(wentry.get("word_score") or wentry.get("score"), 0.0)
                if _append_normalized_entry(words, wtext, wscore, wbox):
                    found = True
            # Tuple format: (word_box, ('word', score))
            elif isinstance(wentry, (list, tuple)) and len(wentry) == 2:
                wbox_raw, winfo = wentry
                if _is_box_like(wbox_raw) and isinstance(winfo, (list, tuple)) and winfo:
                    wtext  = winfo[0] if isinstance(winfo[0], str) else ""
                    wscore = _safe_float(winfo[1] if len(winfo) > 1 else 0.0, 0.0)
                    if _append_normalized_entry(words, wtext, wscore, wbox_raw):
                        found = True
        return found

    def walk_for_words(item) -> None:
        if item is None:
            return

        # Dict with word_result key
        if hasattr(item, "get"):
            wr = item.get("word_result")
            if isinstance(wr, (list, tuple)) and wr:
                _try_word_result_list(wr)
                return
            # Recurse into dict values
            if isinstance(item, dict):
                for v in item.values():
                    walk_for_words(v)
            return

        if isinstance(item, (list, tuple)):
            # Tuple format with 3 elements: (box, (text, score), word_result_list)
            if len(item) == 3:
                first, second, third = item
                if _is_box_like(first) and isinstance(third, (list, tuple)):
                    # third may be the word result list
                    if _try_word_result_list(third):
                        return
            for child in item:
                walk_for_words(child)

    walk_for_words(result)
    return words


def _normalize_paddle_result(result) -> list[dict]:
    """Normalize a raw PaddleOCR result into a flat list of dicts.

    Safe hybrid strategy
    --------------------
    1. Run word-level extraction (``return_word_box=True`` path).
    2. Run line-level extraction (original walk, always available).
    3. Log counts for both so failures are visible in logs.
    4. Return word-level entries if they are non-empty; otherwise return
       line-level entries.  **Never return empty when line-level has entries.**
       This guarantees that enabling word-level extraction cannot cause a
       regression on older PaddleOCR versions.
    """
    # --- Path 1: word-level extraction (return_word_box=True result shape) ---
    word_entries: list[dict] = []
    try:
        word_entries = _extract_word_boxes_from_paddle(result)
    except Exception as exc:
        logger.warning("[OCR-NORM] Word-level extraction raised %s: %s", type(exc).__name__, exc)

    # --- Path 2: line-level extraction (original logic, always runs) ---
    line_entries: list[dict] = []
    try:
        def walk(item) -> None:
            if item is None:
                return

            if isinstance(item, dict) or hasattr(item, "get"):
                try:
                    if _append_from_structured_dict(line_entries, item):
                        return
                except Exception as exc:
                    logger.warning("Failed to parse PaddleOCR dict payload: %s", exc)

                if isinstance(item, dict):
                    for value in item.values():
                        walk(value)
                return

            if isinstance(item, (list, tuple)):
                if len(item) == 2:
                    first, second = item
                    if _is_box_like(first) and isinstance(second, (list, tuple)) and second and isinstance(second[0], str):
                        score = second[1] if len(second) >= 2 else 0.0
                        if _append_normalized_entry(line_entries, second[0], score, first):
                            return
                    if isinstance(first, str):
                        if _append_normalized_entry(line_entries, first, second):
                            return
                    if isinstance(second, str):
                        if _append_normalized_entry(line_entries, second, 0.0, first):
                            return

                if len(item) == 3:
                    first, second, third = item
                    if _append_normalized_entry(line_entries, second, third, first):
                        return
                    if _append_normalized_entry(line_entries, first, third, second):
                        return

                for child in item:
                    walk(child)

        walk(result)
    except Exception as exc:
        logger.warning("[OCR-NORM] Line-level extraction raised %s: %s", type(exc).__name__, exc)

    # --- Selection and diagnostics ---
    word_level_count = len(word_entries)
    line_level_count = len(line_entries)

    if word_level_count > 0:
        selected_mode = "word_level"
        chosen = word_entries
    elif line_level_count > 0:
        selected_mode = "line_level_fallback"
        chosen = line_entries
    else:
        selected_mode = "empty"
        chosen = []

    logger.info(
        "[OCR-NORM] word_level_entries_count=%d line_level_entries_count=%d "
        "selected_reconstruction_mode=%s",
        word_level_count,
        line_level_count,
        selected_mode,
    )

    if selected_mode == "empty":
        logger.warning(
            "[OCR-NORM] Both word-level and line-level extraction returned 0 entries. "
            "PaddleOCR may have returned an empty or unrecognised result structure."
        )

    return chosen


def _preview_value(value, limit: int = 300) -> str:
    preview = repr(value)
    return preview[:limit]


def _ensure_debug_dir() -> Path:
    _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    return _DEBUG_DIR


def _save_debug_image(image, batch_id: str, page_number: int, stage: str) -> None:
    try:
        debug_dir = _ensure_debug_dir()
        output_path = debug_dir / f"{batch_id}_page_{page_number:02d}_{stage}.png"
        if isinstance(image, Image.Image):
            image.save(output_path)
            return
        if cv2 is not None and isinstance(image, np.ndarray):
            cv2.imwrite(str(output_path), image)
            return
    except Exception as exc:  # pragma: no cover - best effort diagnostics
        logger.warning("Failed to save debug image for stage=%s page=%d: %s", stage, page_number, exc)


def _resize_long_edge(image: np.ndarray, max_long_edge: int = 2400) -> np.ndarray:
    height, width = image.shape[:2]
    long_edge = max(height, width)
    if long_edge <= max_long_edge:
        return image

    scale = max_long_edge / float(long_edge)
    new_size = (max(int(round(width * scale)), 1), max(int(round(height * scale)), 1))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def _crop_main_document_region(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    edges = cv2.dilate(edges, kernel, iterations=2)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = height * width * 0.25
    best_rect = None
    best_area = 0

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        if area < min_area or area <= best_area:
            continue
        best_rect = (x, y, w, h)
        best_area = area

    if best_rect is None:
        return image

    x, y, w, h = best_rect
    pad_x = max(int(w * 0.02), 10)
    pad_y = max(int(h * 0.02), 10)
    x0 = max(x - pad_x, 0)
    y0 = max(y - pad_y, 0)
    x1 = min(x + w + pad_x, width)
    y1 = min(y + h + pad_y, height)
    return image[y0:y1, x0:x1]


def _crop_text_region(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    inverted = cv2.bitwise_not(gray)
    thresholded = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 5))
    merged = cv2.morphologyEx(thresholded, cv2.MORPH_CLOSE, kernel, iterations=2)

    coords = cv2.findNonZero(merged)
    if coords is None:
        return image

    x, y, w, h = cv2.boundingRect(coords)
    if w * h < image.shape[0] * image.shape[1] * 0.05:
        return image

    pad_x = max(int(w * 0.02), 8)
    pad_y = max(int(h * 0.03), 8)
    x0 = max(x - pad_x, 0)
    y0 = max(y - pad_y, 0)
    x1 = min(x + w + pad_x, image.shape[1])
    y1 = min(y + h + pad_y, image.shape[0])
    return image[y0:y1, x0:x1]


def _deskew_image(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    inverted = cv2.bitwise_not(gray)
    thresholded = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = cv2.findNonZero(thresholded)
    if coords is None or len(coords) < 10:
        return image

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    elif angle > 45:
        angle = angle - 90

    if abs(angle) < 0.3:
        return image

    height, width = image.shape[:2]
    center = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _preprocess_for_ocr(image: Image.Image, page_number: int, batch_id: str) -> Image.Image:
    _save_debug_image(image, batch_id, page_number, "original")

    if cv2 is None:
        working = image.convert("L")
        resized = working.resize(
            (max(working.width * 2, 1), max(working.height * 2, 1)),
            Image.Resampling.LANCZOS,
        )
        _save_debug_image(resized, batch_id, page_number, "cropped")
        _save_debug_image(resized, batch_id, page_number, "thresholded")
        _save_debug_image(resized, batch_id, page_number, "final_preprocessed")
        return resized

    cv_image = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    cv_image = _resize_long_edge(cv_image)
    cv_image = _crop_main_document_region(cv_image)
    cv_image = _crop_text_region(cv_image)
    cv_image = _deskew_image(cv_image)
    _save_debug_image(cv_image, batch_id, page_number, "cropped")

    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    thresholded = cv2.adaptiveThreshold(
        enhanced,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        15,
    )
    _save_debug_image(thresholded, batch_id, page_number, "thresholded")

    denoised = cv2.fastNlMeansDenoising(thresholded, None, 15, 7, 21)
    sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    sharpened = cv2.filter2D(denoised, -1, sharpen_kernel)
    final_image = cv2.resize(sharpened, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
    _save_debug_image(final_image, batch_id, page_number, "final_preprocessed")
    return Image.fromarray(final_image)


def _looks_like_coordinate_text(text: str) -> bool:
    compact = re.sub(r"\s+", "", str(text or ""))
    if not compact:
        return False

    coordinate_pairs = len(re.findall(r"\[\d+(?:\.\d+)?,\d+(?:\.\d+)?\]", compact))
    numeric_tokens = len(re.findall(r"-?\d+(?:\.\d+)?", compact))
    alphabetic_tokens = len(re.findall(r"[A-Za-z]{2,}", compact))

    return coordinate_pairs >= 2 and alphabetic_tokens == 0 and numeric_tokens >= coordinate_pairs * 2


def _split_ocr_token(token: str) -> list[str]:
    """Split a merged OCR token at alpha-digit and digit-alpha boundaries.

    PaddleOCR sometimes merges tokens that should be separate words, e.g.
    ``"table6"`` or ``"qty5000"``.  This function inserts splits at every
    transition between a letter character and a digit character (in either
    direction) so that downstream numeric parsing sees clean, separated tokens.

    Examples::

        "table6"   -> ["table", "6"]
        "6table"   -> ["6", "table"]
        "qty5000"  -> ["qty", "5000"]
        "cpu2"     -> ["cpu", "2"]
        "2cpu"     -> ["2", "cpu"]
        "table"    -> ["table"]   (no change)
        "5000"     -> ["5000"]    (no change)
    """
    if not token:
        return []
    # Insert a split marker between [alpha][digit] and [digit][alpha]
    marked = re.sub(r"([A-Za-z])([0-9])", r"\1 \2", token)
    marked = re.sub(r"([0-9])([A-Za-z])", r"\1 \2", marked)
    parts = marked.split()
    return parts if parts else [token]


def _compute_adaptive_y_threshold(positioned_rows: list[tuple[float, float, float, float, str, float]]) -> float:
    """Estimate a per-document Y-grouping threshold from the distribution of
    box heights so that it adapts to fonts and scan resolutions.

    Each entry in *positioned_rows* is
    ``(y_center, x_left, box_height, x_right, text, confidence)``.

    The threshold is set to ``0.6 × median_box_height`` clamped between 8 px
    and 40 px.  For typical invoice scans at 300 DPI this yields roughly the
    correct line-gap tolerance without being too loose (which would merge
    adjacent rows).
    """
    heights = sorted(entry[2] for entry in positioned_rows if entry[2] > 0)
    if not heights:
        return 15.0
    median_h = heights[len(heights) // 2]
    return max(8.0, min(40.0, median_h * 0.6))


def _group_paddle_lines(result: list[dict]) -> tuple[list[str], list[float], float]:
    """Reconstruct spatial OCR lines from PaddleOCR bounding-box entries.

    Algorithm
    ---------
    1. Collect each OCR entry with its bounding box; compute y-center,
       x-left, box-height, and x-right so we can sort and gap-detect.
    2. Compute an *adaptive* Y-threshold from the median box height so the
       grouping tolerates different font sizes and scan resolutions.
    3. Sort entries by (y_bucket, x_left) and cluster into logical rows using
       the adaptive threshold.
    4. Within each row, sort by x_left and reconstruct the text by inserting
       whitespace proportional to the pixel gap between adjacent boxes.
    5. Apply OCR-safe token splitting at alpha/digit boundaries to every
       individual OCR token *before* joining.
    6. Emit detailed diagnostics at DEBUG level for every box and every
       reconstructed row so the corruption site can be pinpointed.
    """
    # ------------------------------------------------------------------
    # Phase 1 – collect entries with full spatial info
    # ------------------------------------------------------------------
    # Each tuple: (y_center, x_left, box_height, x_right, text, confidence)
    positioned_rows: list[tuple[float, float, float, float, str, float]] = []
    fallback_lines: list[str] = []
    confidences: list[float] = []

    logger.debug("[OCR-RECON] === Starting OCR spatial reconstruction ===")
    logger.debug("[OCR-RECON] Total normalized entries: %d", len(result or []))

    for idx, entry in enumerate(result or []):
        raw_text = entry.get("text", "")
        text = _clean_text(raw_text)
        confidence = _safe_float(entry.get("confidence"), 0.0)
        box = entry.get("box")

        logger.debug(
            "[OCR-RECON] Box[%d] raw_text=%r confidence=%.4f box=%s",
            idx,
            raw_text,
            confidence,
            box,
        )

        if not text:
            logger.debug("[OCR-RECON] Box[%d] skipped (empty text after clean)", idx)
            continue

        confidences.append(confidence)

        if box:
            xs = [point[0] for point in box]
            ys = [point[1] for point in box]
            x_left = min(xs)
            x_right = max(xs)
            y_center = sum(ys) / len(ys)
            box_height = max(ys) - min(ys)
            logger.debug(
                "[OCR-RECON] Box[%d] y_center=%.1f x_left=%.1f x_right=%.1f "
                "box_height=%.1f text=%r conf=%.4f",
                idx,
                y_center,
                x_left,
                x_right,
                box_height,
                text,
                confidence,
            )
            positioned_rows.append((y_center, x_left, box_height, x_right, text, confidence))
        else:
            logger.debug(
                "[OCR-RECON] Box[%d] has no bounding box; treating as fallback line: %r",
                idx,
                text,
            )
            fallback_lines.append(text)

    # ------------------------------------------------------------------
    # Phase 2 – adaptive Y-threshold
    # ------------------------------------------------------------------
    y_threshold = _compute_adaptive_y_threshold(positioned_rows)
    logger.debug(
        "[OCR-RECON] Adaptive Y-threshold=%.1f px (from %d positioned boxes)",
        y_threshold,
        len(positioned_rows),
    )

    # ------------------------------------------------------------------
    # Phase 3 – sort and cluster into logical rows
    # ------------------------------------------------------------------
    lines: list[str] = []
    if positioned_rows:
        # Coarse bucket by y (rounded to threshold granularity) then fine x
        positioned_rows.sort(key=lambda e: (round(e[0] / y_threshold), e[1]))

        grouped: list[list[tuple[float, float, float, float, str, float]]] = []
        for row in positioned_rows:
            y_center = row[0]
            if not grouped or abs(grouped[-1][-1][0] - y_center) > y_threshold:
                grouped.append([row])
            else:
                grouped[-1].append(row)

        logger.debug("[OCR-RECON] Logical row groups: %d", len(grouped))

        # ------------------------------------------------------------------
        # Phase 4 – per-row reconstruction with gap-aware whitespace
        # ------------------------------------------------------------------
        for row_idx, group in enumerate(grouped):
            # Sort within the row by x_left
            group.sort(key=lambda e: e[1])

            tokens_in_row: list[str] = []
            for token_idx, entry in enumerate(group):
                y_center, x_left, box_height, x_right, text, confidence = entry

                # Phase 5 – OCR-safe token splitting at alpha/digit boundaries
                raw_sub_tokens = _split_ocr_token(text)
                tokens_in_row.append((x_left, x_right, raw_sub_tokens))

            # Build the reconstructed line text with heuristic spacing
            # Rule: if the pixel gap between adjacent boxes exceeds 0.5× the
            # average char width (estimated as box_width / len(text)),
            # insert a space.  We always insert at least one space between
            # tokens to preserve word boundaries.
            reconstructed_parts: list[str] = []
            for token_idx, (x_left, x_right, sub_tokens) in enumerate(tokens_in_row):
                token_str = " ".join(sub_tokens)
                if token_idx == 0:
                    reconstructed_parts.append(token_str)
                else:
                    # Gap between previous box's right edge and this box's left
                    prev_x_right = tokens_in_row[token_idx - 1][1]
                    gap_px = x_left - prev_x_right
                    # Estimate average char width from current token
                    box_width = x_right - x_left
                    text_len = max(len(sub_tokens[-1]), 1) if sub_tokens else 1
                    avg_char_w = box_width / text_len if box_width > 0 else 10.0
                    # Always at least one space; extra space for large gaps
                    if gap_px > avg_char_w * 1.5:
                        reconstructed_parts.append("  ")  # double-space → visible gap
                    else:
                        reconstructed_parts.append(" ")
                    reconstructed_parts.append(token_str)

            line_text = "".join(reconstructed_parts).strip()
            # Collapse multiple spaces to single space
            line_text = re.sub(r"  +", " ", line_text)

            logger.debug(
                "[OCR-RECON] Row[%d] boxes=%d reconstructed=%r",
                row_idx,
                len(group),
                line_text,
            )
            logger.info(
                "[OCR-ROW] row_index=%d token_count=%d reconstructed_text=%r",
                row_idx,
                len(tokens_in_row),
                line_text,
            )

            if line_text:
                lines.append(line_text)

    lines.extend(fallback_lines)
    average_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    logger.info(
        "[OCR-RECON] Reconstruction complete: %d rows produced (%d fallback), avg_conf=%.4f",
        len(lines),
        len(fallback_lines),
        average_confidence,
    )
    logger.info("[OCR-RECON] All reconstructed rows BEFORE parser: %s", lines)

    return lines, confidences, round(average_confidence, 4)


def _describe_paddle_first_item(result):
    if result is None:
        return "EMPTY"
    if isinstance(result, dict):
        first_key = next(iter(result), None)
        return result[first_key] if first_key is not None else "EMPTY"
    if isinstance(result, (list, tuple)):
        return result[0] if result else "EMPTY"
    return result


def _run_paddle_ocr(image: Image.Image):
    """Run PaddleOCR on *image*, attempting word-level boxes first.

    Strategy
    --------
    1. Try calling the OCR runner with ``return_word_box=True`` (if the
       runner's signature accepts it).  This produces per-word spatial
       entries and is the preferred mode.
    2. If the call raises ``TypeError`` (unsupported kwarg) or any other
       exception, immediately retry WITHOUT ``return_word_box``.  This
       preserves full compatibility with older PaddleOCR versions.
    3. Always log which mode was actually used so failures are visible.
    """
    global _PADDLE_OCR_RUNNER, _PADDLE_OCR_RUNNER_NAME
    ocr = _get_paddle_ocr()
    if ocr is None:
        return None, "unavailable"

    if _PADDLE_OCR_RUNNER is None:
        _PADDLE_OCR_RUNNER, _PADDLE_OCR_RUNNER_NAME = _resolve_paddle_runner(ocr)
        logger.info("PaddleOCR method selected: %s", _PADDLE_OCR_RUNNER_NAME)

    if _PADDLE_OCR_RUNNER is None:
        logger.warning("No compatible PaddleOCR inference method found on OCR instance.")
        return None, "unavailable"

    runner_signature = signature(_PADDLE_OCR_RUNNER)
    base_kwargs: dict = {}
    if "use_textline_orientation" in runner_signature.parameters:
        base_kwargs["use_textline_orientation"] = True

    logger.info("PaddleOCR input image type before conversion: %s", type(image).__name__)
    paddle_image = np.array(image)
    logger.info("PaddleOCR numpy image shape=%s dtype=%s", paddle_image.shape, paddle_image.dtype)

    # ------------------------------------------------------------------
    # Attempt 1: with return_word_box=True (word-level segmentation)
    # ------------------------------------------------------------------
    word_box_supported = "return_word_box" in runner_signature.parameters
    if word_box_supported:
        word_kwargs = {**base_kwargs, "return_word_box": True}
        try:
            result = _PADDLE_OCR_RUNNER(paddle_image, **word_kwargs)
            logger.info("[OCR-RUN] selected_reconstruction_mode=word_level (return_word_box=True succeeded)")
            return result, _PADDLE_OCR_RUNNER_NAME
        except TypeError as exc:
            logger.warning(
                "[OCR-RUN] return_word_box=True raised TypeError; falling back to line-level. error=%s",
                exc,
            )
        except Exception as exc:
            logger.warning(
                "[OCR-RUN] return_word_box=True call failed (%s: %s); falling back to line-level.",
                type(exc).__name__,
                exc,
            )
    else:
        logger.info("[OCR-RUN] return_word_box not in runner signature; using line-level mode directly")

    # ------------------------------------------------------------------
    # Attempt 2: without return_word_box (guaranteed-compatible fallback)
    # ------------------------------------------------------------------
    try:
        result = _PADDLE_OCR_RUNNER(paddle_image, **base_kwargs)
        logger.info("[OCR-RUN] selected_reconstruction_mode=line_level (return_word_box not used)")
        return result, _PADDLE_OCR_RUNNER_NAME
    except Exception as exc:
        logger.error("[OCR-RUN] Line-level OCR call also failed: %s", exc)
        return None, _PADDLE_OCR_RUNNER_NAME


def _ocr_page_with_paddle(image: Image.Image) -> tuple[str, float]:
    result, method_name = _run_paddle_ocr(image)

    # ------------------------------------------------------------------
    # Diagnostics: raw PaddleOCR output BEFORE normalization
    # ------------------------------------------------------------------
    logger.info("[OCR-DIAG] === Raw PaddleOCR output ===")
    logger.info("[OCR-DIAG] method=%s result_type=%s", method_name, type(result).__name__)
    logger.info("[OCR-DIAG] result_sample: %s", _preview_value(_describe_paddle_first_item(result)))

    # Log each raw box if the result is iterable in the standard PaddleOCR
    # [[box, [text, conf]], ...] or [[[x,y],...], [text, conf]] format so
    # developers can see raw coordinates / text / confidence before any
    # normalization or spatial reconstruction happens.
    try:
        raw_items = result if isinstance(result, (list, tuple)) else []
        # PaddleOCR v2 wraps in an extra list per page
        if raw_items and isinstance(raw_items[0], list) and raw_items[0] and isinstance(raw_items[0][0], list):
            raw_items = raw_items[0]
        for raw_idx, raw_item in enumerate(raw_items or []):
            logger.debug("[OCR-DIAG] raw_box[%d]: %s", raw_idx, _preview_value(raw_item))
    except Exception as _diag_exc:  # pragma: no cover – best-effort diagnostics
        logger.debug("[OCR-DIAG] Could not iterate raw boxes: %s", _diag_exc)

    # ------------------------------------------------------------------
    # Normalize and reconstruct
    # ------------------------------------------------------------------
    normalized_result = _normalize_paddle_result(result)

    logger.info(
        "[OCR-DIAG] Normalized entries: %d",
        len(normalized_result),
    )
    for norm_idx, norm_entry in enumerate(normalized_result):
        logger.info(
            "[OCR-DIAG] norm_entry[%d] text=%r confidence=%.4f box=%s",
            norm_idx,
            norm_entry.get("text"),
            _safe_float(norm_entry.get("confidence"), 0.0),
            norm_entry.get("box"),
        )

    extracted_lines, confidences, confidence = _group_paddle_lines(normalized_result)

    # ------------------------------------------------------------------
    # Diagnostics: reconstructed rows BEFORE parser entry
    # ------------------------------------------------------------------
    logger.info("[OCR-DIAG] === Reconstructed rows BEFORE parser ===")
    for line_idx, line in enumerate(extracted_lines):
        logger.info("[OCR-DIAG] reconstructed_row[%d]: %r", line_idx, line)

    page_text = _clean_text("\n".join(extracted_lines))

    logger.info(
        "[OCR-DIAG] avg_confidence=%.4f line_count=%d text_preview=%r",
        confidence,
        len(extracted_lines),
        page_text[:300],
    )

    if _looks_like_coordinate_text(page_text):
        logger.warning(
            "[OCR-DIAG] Flattened text looks like coordinate arrays; rejecting before parser. preview=%s",
            _preview_value(page_text),
        )
        return "", 0.0

    logger.info(
        "[OCR-DIAG] method=%s normalized_entries=%d reconstructed_rows=%d "
        "output_chars=%d preview=%r",
        method_name,
        len(normalized_result),
        len(extracted_lines),
        len(page_text),
        page_text[:300],
    )

    if not page_text:
        return "", 0.0
    return page_text, confidence


def _ocr_page_with_tesseract(image: Image.Image) -> tuple[str, float]:
    data = pytesseract.image_to_data(
        image,
        config="--oem 3 --psm 6",
        output_type=pytesseract.Output.DICT,
    )
    tokens: list[str] = []
    confidences: list[float] = []
    for index, token in enumerate(data.get("text", [])):
        text = (token or "").strip()
        if not text:
            continue
        confidence_raw = data.get("conf", [])[index]
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = -1.0
        if confidence >= 0:
            confidences.append(confidence / 100.0)
        tokens.append(text)

    text = _clean_text(" ".join(tokens))
    average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return text, round(average_confidence, 4)


def _extract_text_ocr(data: bytes) -> tuple[str, list[dict], str]:
    pages: list[dict] = []
    text_parts: list[str] = []
    engine_used = "pytesseract"
    batch_id = uuid4().hex[:12]
    pdf = pdfium.PdfDocument(BytesIO(data), autoclose=True)
    scale = 300 / 72

    try:
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                bitmap = page.render(scale=scale)
                pil_image = bitmap.to_pil()
                processed = _preprocess_for_ocr(pil_image, index + 1, batch_id)

                page_text, confidence = _ocr_page_with_paddle(processed)
                if page_text:
                    engine = "paddleocr"
                    engine_used = "paddleocr"
                else:
                    page_text, confidence = _ocr_page_with_tesseract(processed)
                    engine = "pytesseract"

                pages.append(
                    {
                        "page_number": index + 1,
                        "text": page_text,
                        "confidence": confidence,
                        "engine": engine,
                        "uncertain": confidence < 0.6 if confidence else True,
                    }
                )
                if page_text:
                    text_parts.append(page_text)
            except Exception as exc:
                logger.warning("OCR page %d failed: %s", index, exc)
                pages.append(
                    {
                        "page_number": index + 1,
                        "text": "",
                        "confidence": 0.0,
                        "engine": engine_used,
                        "uncertain": True,
                        "error": str(exc),
                    }
                )
            finally:
                page.close()
    finally:
        pdf.close()

    extracted_text = _clean_text("\n\n".join(text_parts))
    logger.info(
        "OCR engine=%s output_len=%d preview=%r",
        engine_used,
        len(extracted_text),
        extracted_text[:200],
    )
    return extracted_text, pages, engine_used


def extract_pdf_content(file_bytes: bytes) -> dict:
    """Return text plus OCR metadata while avoiding OCR for text PDFs."""
    logger.info("CALL CHAIN OCR entrypoint=extract_pdf_content bytes=%d", len(file_bytes or b""))
    if not file_bytes:
        return {
            "text": "",
            "pages": [],
            "pdf_type": "unknown",
            "engine": "none",
            "confidence": 0.0,
        }

    data = bytes(file_bytes)
    detection = detect_pdf_type(data)
    logger.info("CALL CHAIN OCR detect_pdf_type -> pdf_type=%s", detection.get("pdf_type"))

    direct_text = ""
    direct_pages: list[dict] = []
    if detection["pdf_type"] == "text":
        try:
            logger.info("CALL CHAIN OCR -> _extract_text_pdfplumber")
            direct_text, direct_pages = _extract_text_pdfplumber(data)
        except Exception as exc:
            logger.warning("Direct text extraction failed, falling back to OCR: %s", exc)

    if detection["pdf_type"] == "text" and len(direct_text) >= _MIN_DIRECT_TEXT_CHARS:
        return {
            "text": direct_text,
            "pages": direct_pages,
            "pdf_type": detection["pdf_type"],
            "engine": "pdfplumber",
            "confidence": 1.0 if direct_text else 0.0,
            "detection": detection,
        }

    try:
        logger.info("CALL CHAIN OCR -> _extract_text_ocr")
        ocr_text, ocr_pages, engine = _extract_text_ocr(data)
    except (TesseractNotFoundError, TesseractError, OSError, RuntimeError) as exc:
        logger.error("OCR unavailable: %s", exc)
        return {
            "text": direct_text,
            "pages": direct_pages,
            "pdf_type": detection["pdf_type"],
            "engine": "pdfplumber" if direct_text else "none",
            "confidence": 1.0 if direct_text else 0.0,
            "detection": detection,
            "error": str(exc),
        }

    overall_confidence = 0.0
    confidences = [page["confidence"] for page in ocr_pages if page.get("confidence") is not None]
    if confidences:
        overall_confidence = round(sum(confidences) / len(confidences), 4)

    return {
        "text": ocr_text or direct_text,
        "pages": ocr_pages if ocr_text else direct_pages,
        "pdf_type": "scanned" if ocr_text else detection["pdf_type"],
        "engine": engine if ocr_text else "pdfplumber",
        "confidence": overall_confidence if ocr_text else (1.0 if direct_text else 0.0),
        "detection": detection,
    }


def extract_text_from_pdf(file_bytes: bytes) -> str:
    logger.info("CALL CHAIN OCR public entrypoint=extract_text_from_pdf")
    return extract_pdf_content(file_bytes).get("text", "")
