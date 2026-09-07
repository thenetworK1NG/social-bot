import subprocess
import re
import os
import shutil
import json

MODEL = "opencode/big-pickle"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Anchors for the strict output contract. Presence of these lets us pull
# exactly the model's content out, ignoring anything it narrates around it.
_START = "{{{START}}}"
_END = "{{{END}}}"


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


def _output_contract():
    return (
        "\n\nSTRICT OUTPUT CONTRACT:\n"
        "- Reply with the requested text and absolutely nothing else.\n"
        f"- Begin with the exact line {_START}\n"
        f"- End with the exact line {_END}\n"
        "- No commentary, labels, quotes around it, or explanation of any kind."
    )


_JSON_CONTRACT = (
    "\n\nSTRICT OUTPUT CONTRACT:\n"
    "- Reply with ONLY a valid JSON value (object or array) and nothing else.\n"
    f"- Begin with the exact line {_START}\n"
    f"- End with the exact line {_END}\n"
    "- No markdown fences, no commentary, no trailing prose."
)

_DETOX_NOTE = (
    "\n\nIMPORTANT: Previously you leaked reasoning or instructions into your"
    " output. Now output ONLY the in-character text itself — the words a real"
    " person would say or type. Never narrate your task, never describe who you"
    " are or what you are doing, never say 'here is my response', never mention"
    " characters, prompts, bots, 'output', 'reply:', 'you are', or 'write a'."
)


def generate_text(prompt: str, timeout: int = 180, retry: bool = True) -> str:
    """Generate a single piece of in-character text. Returns '' if it leaks."""
    raw = _run(prompt + _output_contract(), timeout)
    text = clean_text(_extract_marked(raw))
    if not _leak_score(text) or not retry:
        return text
    # One smarter retry: explicitly forbid the contamination instead of guessing.
    text = clean_text(_extract_marked(_run(prompt + _DETOX_NOTE + _output_contract(), timeout)))
    return "" if _leak_score(text) else text


def generate_json(prompt: str, timeout: int = 180):
    """Ask for structured data; returns parsed JSON (or None)."""
    raw = _run(prompt + _JSON_CONTRACT, timeout)
    text = _extract_marked(raw)
    return _parse_json(text)


def _run(prompt: str, timeout: int) -> str:
    """Run opencode once and return scrubbed raw output."""
    cmd = [OPCODE, "run", "--pure", "-m", MODEL, prompt]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=REPO,
        )
        output = result.stdout or ""
        if not output.strip():
            output = result.stderr or ""
        return _scrub_output(output)
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return ""


def _scrub_output(output: str) -> str:
    """Strip ANSI codes and opencode UI decoration, drop empty lines."""
    if not output:
        return ""
    output = re.sub(r"\x1b\[[0-9;]*m", "", output)
    out = []
    for line in output.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith(">") and "build" in s:
            continue
        if any(x in s for x in ["█", "▀", "⣿", "⠀"]):
            continue
        if re.match(r"^[•·\-=*#]+$", s):
            continue
        out.append(s)
    return "\n".join(out)


def _extract_marked(raw: str) -> str:
    """Pull out the text between the contract anchors when present."""
    if not raw:
        return ""
    if _START in raw:
        start = raw.index(_START) + len(_START)
        end = raw.index(_END) if _END in raw else len(raw)
        return raw[start:end].strip()
    # No markers (model ignored contract) — drop the contract text if echoed.
    low = raw.lower()
    i = low.find("strict output contract")
    if i != -1:
        raw = raw[:i]
        raw = raw.replace(_START, "").replace(_END, "")
    return raw.strip()


# Lines that are the model narrating instead of writing content.
# Each alternative must end on a word boundary (space or end of line) so we
# use (?:\s|$) rather than a bare literal space, since lines arrive stripped.
_NARR_LINE = re.compile(
    r"^(?:"
    r"output (?:only|just|the|a)(?:\s|$)"
    r"|zero preamble(?:\s|$)"
    r"|no (?:quotes|labels|explanation|preamble|commentary)(?:\s|$)"
    r"|you are [\w ']{0,60}(?:user|bot|assistant|persona)(?:\s|$)"
    r"|(?:i am|i'?m) [\w.&]+, (?:a|an|the|just)[^\n]{0,40}(?:\s|$)"
    r"|as (?:an ai|a language model|your assistant|[\w]+.*?(?:user|bot|assistant))(?:\s|$)"
    r"|the (?:prompt|task|user|system|notes skill)(?:[^\n]{0,40})(?:\s|$)"
    r"|here(?:'s| is) (?:a|my|the) (?:response|reply|comment|answer)(?::|(?:\s|$))"
    r"|let me (?:write|draft|compose|think|give|provide|start)(?:\s|$)"
    r"|i'?ll (?:respond|reply|write|give|draft)(?:\s|$)"
    r"|i'?m being asked(?:\s|$)"
    r"|i (?:should|need to) (?:write|respond|say)(?:\s|$)"
    r"|stay in character(?:\s|$)"
    r"|(?:final|my) (?:response|answer|thought)(?: as|:)(?:\s|$)"
    r"|\*\*\s?.+?:\*\*(?:\s|$)"
    r"|^> ?(?:[\w.'@-]+ )?(?:wrote|said|posted|replied|commented|writes|says):"
    r"|[\w.'@-]+'s (?:response|reply|comment|answer):(?:\s|$)"
    r"|(?:since|because) (?:this|i am|i'?m)(?:\s|$)"
    r"|write a (?:short|natural|single|casual|quick|real)(?:\s|$)"
    r")",
    re.IGNORECASE,
)

# Signals buried inside otherwise-fine text (mid-sentence narration).
_LEAK_RE = re.compile(
    r"you are [\w ']+?(?:user|bot|assistant|persona)|"
    r"i'?m [\w.]+?,? a (?:user|bot|persona|participant)|"
    r"i am [\w.]+?,? a (?:user|bot|persona)|"
    r"as (?:an ai|a language model|your assistant)|"
    r"the prompt (?:asks|is|wants|says)|"
    r"output only|zero preamble|no labels[ ,]no quotes|stay in character|"
    r"here(?:'s| is) (?:a|my|the) (?:response|reply|comment|answer)|"
    r"(?:response|reply|comment) as [A-Za-z0-9]+:|"
    r"write a (?:short|natural|single|casual|quick)|"
    r"i (?:can|will|'ll|should) (?:write|respond|reply|give|draft)",
    re.IGNORECASE,
)


def clean_text(text: str) -> str:
    """Remove empty lines and narration lines from generated text."""
    if not text:
        return ""
    kept = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if _is_narration_line(s):
            continue
        kept.append(s)
    return "\n".join(kept).strip(" \n")


def _is_narration_line(line: str) -> bool:
    return bool(_NARR_LINE.match(line))


def _leak_score(text: str) -> int:
    return len(_LEAK_RE.findall(text or ""))


def _parse_json(text: str):
    if not text:
        return None
    # Strip markdown fences and surrounding prose.
    text = re.sub(r"```(?:json)?", "", text)
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if ch not in "{[":
            i += 1
            continue
        # Walk from candidate start, tracking depth and strings, to find its
        # matching close so we grab the outermost value (not an inner one).
        d = 0
        in_str = False
        esc = False
        j = i
        while j < n:
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c in "{[":
                    d += 1
                elif c in "}]":
                    d -= 1
                    if d == 0:
                        try:
                            return json.loads(text[i : j + 1])
                        except (ValueError, TypeError):
                            break
            j += 1
        i += 1
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None