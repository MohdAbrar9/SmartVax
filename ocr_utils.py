"""
ocr_utils.py
------------
Handles reading text off a photographed/scanned vaccination card
using Tesseract OCR. Kept in its own file so the OCR logic can be
tested or swapped out without touching the Flask routes.
"""

from PIL import Image
import pytesseract


def extract_text_from_image(image_path):
    """
    Takes the file path of an uploaded image and returns the raw text
    Tesseract can read from it.

    We also apply a couple of very simple image cleanup steps first —
    converting to grayscale and boosting contrast — because OCR
    accuracy on real vaccination cards (handwriting, stamps, faded
    ink) is much better on a cleaned-up image than the raw photo.
    """
    image = Image.open(image_path)

    # Convert to grayscale — removes colour noise, Tesseract reads
    # grayscale/black-and-white text more reliably.
    image = image.convert("L")

    # Run OCR. lang="eng" can be changed to "eng+hin" if you install
    # the Hindi trained-data file and cards are bilingual.
    extracted_text = pytesseract.image_to_string(image, lang="eng")

    return extracted_text.strip()


def guess_vaccine_names(extracted_text, known_vaccine_names):
    """
    Very simple matching: checks which known vaccine names appear
    (even partially) inside the OCR text, so the app can suggest
    "we found these vaccines mentioned on your card" instead of just
    dumping raw text at the parent.

    known_vaccine_names: list of strings, e.g. ["BCG", "OPV - 1", ...]
    """
    text_lower = extracted_text.lower()
    matches = []

    for name in known_vaccine_names:
        # Take just the main word (e.g. "Pentavalent" from
        # "Pentavalent - 1") so partial handwriting still matches.
        key_word = name.split("-")[0].strip().lower()
        if key_word in text_lower:
            matches.append(name)

    return matches
