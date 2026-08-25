"""Scanner de secrets — garde-fou anti-fuite (CI + pre-commit).

Usage :
    python scripts/check_secrets.py [chemins...]

Scanne les fichiers suivis par git (ou les chemins fournis) à la recherche
de motifs de secrets. Sortie non-zéro si un secret est détecté.

NOTE : conçu sans dépendance externe pour tourner en CI comme en local.
"""

import re
import subprocess
import sys
from pathlib import Path

# Fichiers dont la présence même est interdite dans l'index git.
BLOCKED_FILENAMES = re.compile(
    r"(^|/)(\.env|\.pii_key[^/]*|.*\.pem|.*\.key|.*\.jks|"
    r".*\.keystore|.*\.db|.*\.db-(journal|wal|shm)|flutter\.zip)$",
    re.IGNORECASE,
)

# Motifs de secrets dans le contenu (par ligne).
SECRET_PATTERNS = [
    ("URL avec credentials", re.compile(r"[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@", re.I)),
    ("Clé AWS AKIA", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Token GitHub", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("Clé API Google", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("Clé OpenAI", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("Clé Slack", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("Clé privée embarquée", re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----")),
    ("Mot de passe assigné", re.compile(r"""(?i)\b(pass(word|wd)?|pwd)\b\s*=\s*["'][^"']{4,}["']""")),
    ("Secret assigné", re.compile(r"""(?i)\b(secret|api[_-]?key)\b\s*=\s*["'][^"']{8,}["']""")),
]

# Dossiers exclus (générés / tiers / fixtures de test légitimes).
EXCLUDED_DIRS = {
    ".git", "build", ".dart_tool", "node_modules", "flutter",
    "graphify", "graphify-out", ".venv", "venv", "__pycache__",
    ".pytest_cache", "frontend/web",
}

# Les tests utilisent volontairement des jetons fictifs → whitelist ciblée.
WHITELIST_SUBSTRINGS = (
    "Bearer test-token",
    "postgresql://user:",
    "test.db",
    "Fernet.generate_key()",
)


def tracked_files() -> list[str]:
    """Liste les fichiers suivis par git."""
    out = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def scan_line(path: str, lineno: int, line: str, findings: list[str]) -> None:
    if any(w in line for w in WHITELIST_SUBSTRINGS):
        return
    for label, pattern in SECRET_PATTERNS:
        match = pattern.search(line)
        if match:
            # On masque la valeur détectée dans le rapport.
            masked = match.group(0)[:6] + "***MASKED***"
            findings.append(f"  {path}:{lineno}  [{label}]  {masked}")


def main(argv: list[str]) -> int:
    files = argv[1:] if len(argv) > 1 else tracked_files()
    findings: list[str] = []

    for raw in files:
        path = Path(raw)
        if BLOCKED_FILENAMES.search(raw.replace("\\", "/")):
            findings.append(f"  {raw}  [FICHIER INTERDIT dans l'index]")
            continue
        if is_excluded(path) or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            scan_line(raw, lineno, line, findings)

    if findings:
        print("SECRETS DETECTES — commit bloque :")
        print("\n".join(findings))
        print("\nSi un motif ci-dessus est un faux positif, ajoutez-le "
              "à WHITELIST_SUBSTRINGS dans scripts/check_secrets.py.")
        return 1

    print("check_secrets: OK — aucun secret détecté.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
