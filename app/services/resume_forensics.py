"""Resume forensics: automated checks for how a resume survives the trip from a polished
document into whatever a recruiter or ATS actually consumes (plain text, parsed fields,
clicked links). These are heuristics, not guarantees -- each result says what it checked and
why, never a fake pass/fail "ATS score"."""
import re, unicodedata
from pathlib import Path

URL_RE = re.compile(r'https?://[^\s<>"\')\]]+', re.I)
EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE_RE = re.compile(r'(?:\+\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}')
SECTION_HEADERS = ["experience", "work experience", "education", "skills", "technical skills",
    "projects", "certifications", "summary", "professional summary", "leadership",
    "publications", "awards", "languages"]

# Private-use-area and similar codepoints are the classic signature of a broken icon-font
# glyph (a bullet/arrow/icon rendered via a custom font that an extractor cannot map to any
# real character) -- exactly the "glyph massacre" failure mode.
def _is_suspect_char(ch):
    if ch in ('�',):  # replacement character: extraction already failed here
        return True
    cp = ord(ch)
    if 0xE000 <= cp <= 0xF8FF:  # Private Use Area
        return True
    cat = unicodedata.category(ch)
    if cat == 'Cc' and ch not in ('\n', '\t', '\r'):  # stray control characters
        return True
    return False


def plain_text_check(text):
    """RF01: what a plain-text renderer (or any system reading extracted text) would see."""
    lines = text.splitlines()
    non_empty = [l for l in lines if l.strip()]
    warnings = []
    if not non_empty:
        warnings.append("No extractable text at all -- likely an image-only/scanned PDF.")
    if non_empty and len(non_empty[0].strip()) < 3:
        warnings.append("First non-empty line is very short -- the candidate's name may not be the first thing extracted.")
    avg_len = sum(len(l) for l in non_empty) / len(non_empty) if non_empty else 0
    if avg_len < 8:
        warnings.append("Average line length is unusually short -- may indicate a multi-column layout flattened into single words per line.")
    return {"text": text, "char_count": len(text), "line_count": len(lines),
            "non_empty_line_count": len(non_empty), "warnings": warnings}


def glyph_scan(text):
    """RF04: flags characters that commonly break during PDF/DOCX text extraction."""
    found = {}
    for i, ch in enumerate(text):
        if _is_suspect_char(ch):
            key = f"U+{ord(ch):04X}"
            if key not in found:
                start = max(0, i - 15); end = min(len(text), i + 15)
                found[key] = {"codepoint": key, "count": 0,
                    "context": text[start:end].replace("\n", " ")}
            found[key]["count"] += 1
    return sorted(found.values(), key=lambda x: -x["count"])


def filename_check(filename, candidate_name="", role_hint=""):
    """RF05: filename discipline -- clean, identifiable, not a version-junk drawer."""
    name = Path(filename).stem
    ext = Path(filename).suffix.lower()
    issues = []
    lowered = name.lower()
    junk_tokens = ["final", "finalfinal", "copy", "new", "updated", "latest", "v1", "v2", "draft", "untitled"]
    if any(t in lowered for t in junk_tokens):
        issues.append("filename contains version/junk words (final, copy, v2, etc.) instead of a clean identity-based name")
    if re.search(r'\s', name):
        issues.append("filename contains spaces -- some upload systems mangle these into %20 or strip them")
    if lowered in {"resume", "cv", "document"}:
        issues.append("filename is a generic placeholder with no identifying information")
    if ext not in {".pdf", ".docx"}:
        issues.append(f"unusual resume file extension: {ext or '(none)'}")
    suggested = None
    if candidate_name:
        slug = re.sub(r'[^A-Za-z0-9]+', '_', candidate_name).strip('_')
        suggested = f"{slug}_{re.sub(r'[^A-Za-z0-9]+','_',role_hint).strip('_') or 'Resume'}{ext or '.pdf'}"
    return {"filename": filename, "issues": issues, "suggested_filename": suggested, "clean": not issues}


def ats_extraction_mirror(text):
    """RF02: a best-effort normalized candidate record -- exactly the shape of what a naive
    ATS parser would be able to pull from extracted text, so you can see what's actually
    machine-legible versus only visually present."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    name_guess = lines[0] if lines else None
    emails = sorted(set(EMAIL_RE.findall(text)))
    phones = sorted(set(PHONE_RE.findall(text)))
    links = sorted(set(URL_RE.findall(text)))
    lower = text.lower()
    headers_found = [h for h in SECTION_HEADERS if re.search(r'(?:^|\n)\s*' + re.escape(h) + r'\s*(?:\n|$)', lower)]
    return {"name_guess": name_guess, "emails": emails, "phones": phones, "links": links,
        "section_headers_detected": headers_found,
        "missing_core_sections": [s for s in ["experience", "education", "skills"]
            if not any(s in h for h in headers_found)]}


def link_survivability(text, timeout=6, max_links=20):
    """RF11: click every link so a dead/login-walled proof path doesn't fail silently later."""
    import requests
    urls = sorted(set(URL_RE.findall(text)))[:max_links]
    results = []
    for u in urls:
        clean = u.rstrip('.,);')
        entry = {"url": clean, "status": "unknown", "detail": ""}
        try:
            r = requests.head(clean, timeout=timeout, allow_redirects=True)
            if r.status_code == 405:  # some servers reject HEAD; fall back to GET
                r = requests.get(clean, timeout=timeout, allow_redirects=True, stream=True)
            if r.status_code < 300:
                entry["status"] = "ok"
            elif r.status_code < 400:
                entry["status"] = "redirect"
            elif r.status_code in (401, 403):
                entry["status"] = "login_or_blocked"
            elif r.status_code == 404:
                entry["status"] = "dead"
            else:
                entry["status"] = "error"
            entry["detail"] = f"HTTP {r.status_code}" + (f" -> {r.url}" if r.url != clean else "")
        except Exception as e:
            entry["status"] = "unreachable"
            entry["detail"] = str(e)[:200]
        results.append(entry)
    return results


def consistency_checksum(text, profile):
    """RF13: compares employer names, titles and dates in the profile (source of truth) against
    what actually appears in the resume text, so contradictions get caught before an interviewer
    finds them."""
    lower = text.lower()
    rows = []
    for section, entries in [("experience", profile.get("experience", [])), ("education", profile.get("education", []))]:
        for e in entries:
            label = e.get("company") or e.get("institution") or ""
            title = e.get("title") or e.get("degree") or ""
            if not label:
                continue
            present = label.lower() in lower
            title_present = (title.lower() in lower) if title else True
            row = {"section": section, "entity": label, "title": title,
                "entity_found_in_resume": present, "title_found_in_resume": title_present}
            if not present:
                row["flag"] = f"'{label}' is in your profile but not found in this resume's extracted text"
            elif title and not title_present:
                row["flag"] = f"'{label}' found, but the title '{title}' was not found nearby/at all"
            else:
                row["flag"] = None
            rows.append(row)
    return rows


def run_all(resume_path, candidate_name="", role_hint="", profile=None, check_links=False):
    from .resume_ingest import extract_text
    text = extract_text(resume_path)
    result = {
        "plain_text": plain_text_check(text),
        "glyphs": glyph_scan(text),
        "filename": filename_check(Path(resume_path).name, candidate_name, role_hint),
        "ats_mirror": ats_extraction_mirror(text),
        "consistency": consistency_checksum(text, profile) if profile else [],
        "links": link_survivability(text) if check_links else None,
    }
    return result
