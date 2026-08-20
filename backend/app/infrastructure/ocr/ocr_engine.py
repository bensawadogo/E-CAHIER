"""
Ecahier - OCR Engine
Moteur de reconnaissance optique de caractères pour les reçus et documents.

Stratégie pour le contexte Burkina Faso :
  - Mode offline : Tesseract (gratuit, local, pas de connexion requise)
  - Mode online : API cloud (optionnel, meilleure précision)
  - Fallback automatique : si l'API cloud échoue, utilise Tesseract local
"""

import logging
import os
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class OCREngine:
    """Moteur OCR avec fallback offline/online."""

    def __init__(self, tesseract_path: Optional[str] = None, lang: str = "fra"):
        self.tesseract_path = tesseract_path or os.getenv("TESSERACT_PATH", "tesseract")
        self.lang = lang
        self._available = self._check_tesseract()

    def _check_tesseract(self) -> bool:
        """Vérifie si Tesseract est disponible sur le système."""
        try:
            result = subprocess.run(
                [self.tesseract_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                logger.info("Tesseract OCR disponible: %s", result.stdout.split("\n")[0])
                return True
        except FileNotFoundError:
            logger.warning(
                "Tesseract non trouvé. Installez-le: apt install tesseract-ocr tesseract-ocr-fra"
            )
        except Exception as e:
            logger.warning("Erreur lors de la vérification de Tesseract: %s", e)
        return False

    @property
    def is_available(self) -> bool:
        """Indique si l'OCR est disponible."""
        return self._available

    def extract_text(self, image_path: str) -> str:
        """
        Extrait le texte d'une image via Tesseract.

        Args:
            image_path: Chemin vers l'image à analyser.

        Returns:
            str: Texte extrait de l'image.

        Raises:
            RuntimeError: Si Tesseract n'est pas disponible.
            FileNotFoundError: Si l'image n'existe pas.
        """
        if not self._available:
            raise RuntimeError(
                "Tesseract OCR n'est pas disponible. "
                "Installez-le avec: apt install tesseract-ocr tesseract-ocr-fra"
            )
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image introuvable: {image_path}")

        try:
            result = subprocess.run(
                [self.tesseract_path, image_path, "-", "-l", self.lang],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                text = result.stdout.strip()
                logger.info("OCR réussi: %d caractères extraits de %s", len(text), image_path)
                return text
            else:
                logger.error("Erreur OCR Tesseract: %s", result.stderr)
                return ""
        except subprocess.TimeoutExpired:
            logger.error("Timeout OCR sur l'image: %s", image_path)
            return ""
        except Exception as e:
            logger.error("Erreur inattendue lors de l'OCR: %s", e)
            return ""

    def extract_amount(self, image_path: str) -> Optional[str]:
        """
        Tente d'extraire un montant (FCFA) d'un reçu.

        Args:
            image_path: Chemin vers l'image du reçu.

        Returns:
            str: Montant extrait ou None si non trouvé.
        """
        import re

        text = self.extract_text(image_path)
        if not text:
            return None

        # Patterns courants pour les montants en FCFA
        patterns = [
            r"(\d[\d\s.,]*)\s*FCFA",
            r"(\d[\d\s.,]*)\s*CFA",
            r"montant[:\s]+(\d[\d\s.,]*)",
            r"total[:\s]+(\d[\d\s.,]*)",
            r"(\d[\d\s.,]*)\s*F\s*$",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                amount = match.group(1).replace(" ", "").replace(",", ".").strip()
                logger.info("Montant extrait: %s FCFA", amount)
                return amount

        logger.warning("Aucun montant trouvé dans l'image: %s", image_path)
        return None