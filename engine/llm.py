import subprocess
import re
import os
import shutil

MODEL = "opencode/big-pickle"


def _find_opencode():
    """Locate the opencode executable, handling .cmd shims on Windows."""
    candidates = []
    which = shutil.which("opencode")
    if which:
        candidates.append(which)
    # npm global shims on Windows
    npm_root = os.path.expandvars(r"%APPDATA%\npm\opencode.cmd")
    if os.path.exists(npm_root):
        candidates.append(npm_root)
    # fall back to plain name (PATH lookup, works if real exe)
    candidates.append("opencode")
    return candidates[0]


OPCODE = _find_opencode()


def generate_text(prompt: str, timeout: int = 180) -> str:
    """Call opencode run with big-pickle to generate text."""
    # --pure avoids loading plugins/project skills that leak noise into output
    cmd = [OPCODE, "run", "--pure", "-m", MODEL, prompt]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        output = result.stdout or ""
        text = _clean_output(output)
        if not text and result.stderr:
            text = _clean_output(result.stderr)
        text = text.strip()
        # Reject meta/out-of-character output so callers can retry with a fallback
        if _is_meta_noise(text):
            return ""
        return text
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return ""


_META_NOISE_PHRASES = [
    "this is a social media simulation",
    "the user is asking me",
    "you are", "you're", "as your assistant",
    "isn't relevant to this task",
    "not relevant to the task",
    "i'm here to help",
    "as an ai",
    "as an ai language model",
    "i don't have the ability",
    "i cannot",
    "let me explain",
    "the prompt asks",
    "the notes skill",
]


def _is_meta_noise(text: str) -> bool:
    if not text:
        return True
    low = text.lower()
    hits = sum(1 for p in _META_NOISE_PHRASES if p in low)
    return hits >= 2


def _clean_output(output: str) -> str:
    """Strip ANSI escape codes, opencode UI decorations, and keep the response."""
    if not output:
        return ""
    # strip ANSI escape sequences
    output = re.sub(r"\x1b\[[0-9;]*m", "", output)
    lines = output.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip banner/decoration lines
        if stripped.startswith(">") and "build" in stripped:
            continue
        if not stripped:
            continue
        if any(x in stripped for x in ["█", "▀", "⣿", "⠀"]):
            continue
        if re.match(r"^[•·\-=*#]+$", stripped):
            continue
        cleaned.append(stripped)
    if not cleaned:
        return ""
    if cleaned and cleaned[0].startswith(">"):
        cleaned = cleaned[1:]
    # Strip model thinking-out-loud / meta preamble
    cleaned = _strip_meta(cleaned)
    return "\n".join(cleaned).strip()


_META_PATTERNS = [
    r"^here'?s (a |my |the )?(response|a response|reply|comment)",
    r"^as .*?, (here|i|let)",
    r"^i'?m being asked",
    r"^let me (understand|check|look|cra(ft|sh)|see)",
    r"^the (user|persona)",
    r"^this is (a|an|me)",
    r"^\*\*.*?:\*\*",
    r"^here's a response",
]


def _strip_meta(lines):
    """Remove lines where the model narrates its own reasoning instead of the content."""
    kept = []
    for line in lines:
        low = line.lower().lstrip('#*').lstrip()
        if any(re.match(p, low) for p in _META_PATTERNS):
            continue
        kept.append(line)
    return kept
