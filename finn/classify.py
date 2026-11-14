"""Rule-based triage of exchange filings. No model calls.

Every filing gets: category (ENAM's taxonomy), kind (finer), tier (1 material,
2 notable, 3 routine) and `ask_llm` — True only when rules cannot tell whether
it matters (vague text, or a type whose materiality depends on what's inside).
Rules settle ~85% of filings; the cheap model only ever sees the rest."""
import re

_BOILER = re.compile(
    r"^.{0,90}?\bhas\s+(?:informed|submitted|intimated)\s*(?:to)?\s*the\s+exchange\s*"
    r"(?:about|regarding|that|a copy of|,)?\s*", re.I | re.S)
_TOP_ROLE = re.compile(
    r"\b(CEO|CFO|COO|Chief Executive|Chief Financial|Chief Operating|Managing Director|\bMD\b|Chairman|Chairperson|"
    r"Whole[- ]?time Director|Executive Director|Joint Managing|Company Secretary|President)\b", re.I)
_LOW_ROLE = re.compile(r"\b(SMP|Senior Management|Senior Vice President|Vice President|Independent Director|"
                       r"Non[- ]? ?Executive)\b", re.I)


def clean_text(desc: str, text: str | None) -> str:
    t = _BOILER.sub("", (text or "").strip()).strip(" '\".")
    return t[:1].upper() + t[1:] if t else ""


def is_vague(desc: str, cleaned: str) -> bool:
    c = cleaned.lower()
    return (len(c) < 25 or c == desc.lower() or c.startswith(("general updates", "updates", "disclosure under regulation 30",
            "intimation under regulation 30", "please find", "announcement under regulation 30")))


def classify(desc: str, text: str | None) -> dict:
    d = (desc or "").strip()
    t = clean_text(d, text)
    tl = t.lower()
    vague = is_vague(d, t)

    def out(cat, kind, tier, ask=False):
        return {"category": cat, "kind": kind, "tier": tier, "ask_llm": ask, "text": t, "vague": vague}

    def has(*words):
        return any(w in tl for w in words)

    # --- pure paperwork -----------------------------------------------------------------
    if d in ("ESOP/ESOS/ESPS", "Trading Window", "Monitoring Agency Report", "Committee Meeting Updates",
             "Address Change", "Amendment to AOA/MOA", "Change in Auditors", "Corrigendum",
             "Statement of deviation(s) or variation(s) under Reg. 32",
             "Giving guarantees/indemnity/ becoming a surety for third party") or d.startswith("Certificate under SEBI"):
        return out("unclassified", "compliance", 3)
    if d == "Copy of Newspaper Publication":
        return out("unclassified", "newspaper", 3)

    # --- results & calls ----------------------------------------------------------------
    if d == "Outcome of Board Meeting":
        if has("financial result"):
            return out("results", "results_filing", 1)
        if has("dividend"):
            return out("dividend", "declared", 2)
        if has("director", "appoint", "resign"):
            return out("management_change", "board", 2, ask=True)
        return out("unclassified", "board_outcome", 2, ask=True)
    if d == "Investor Presentation":
        return out("results", "presentation", 3)
    if d.startswith("Analysts/Institutional Investor Meet"):
        if has("transcript"):
            return out("earnings_call", "transcript", 2)
        if has("audio", "recording", "video"):
            return out("earnings_call", "recording", 3)
        if has("presentation"):
            return out("results", "presentation", 3)
        if has("earnings", "conference call", "financial results", "results for"):
            return out("earnings_call", "notice", 3)
        return out("investor_meetings", "meeting", 3)

    # --- people -------------------------------------------------------------------------
    if d in ("Change in Management", "Appointment", "Change in Director(s)", "Resignation", "Cessation", "Retirement",
             "Demise", "Resignation of Director/KMP/SMP", "Resignation of Independent director"):
        if vague:
            return out("management_change", "unknown", 2, ask=True)
        if _TOP_ROLE.search(t) and not re.search(r"Independent Director|Non[- ]? ?Executive Director", t, re.I):
            return out("management_change", "top", 1, ask=True)
        if _LOW_ROLE.search(t):
            return out("management_change", "senior", 3)
        return out("management_change", "other", 2, ask=True)

    # --- capital ------------------------------------------------------------------------
    if d == "Allotment of Securities":
        if has("esop", "esps", "stock option", "employee"):
            return out("unclassified", "esop_allotment", 3)
        if has("non convertible", "non-convertible", "ncd", "debenture", "commercial paper"):
            return out("fund_raise", "debt", 3)
        return out("fund_raise", "allotment", 2, ask=True)
    if d in ("Qualified Institutional Placement", "Preferential issue", "Buyback", "Rights Issue"):
        return out("fund_raise", d.lower(), 1, ask=True)
    if d in ("Issue of Securities", "Post Buyback Public Announcement", "Options to purchase securities"):
        if has("non convertible", "non-convertible", "ncd", "debenture", "commercial paper"):
            return out("fund_raise", "debt", 3)
        return out("fund_raise", "issue", 2, ask=True)
    if d == "Dividend":
        return out("dividend", "declared", 2)
    if d == "Record Date":
        return out("bonus_split" if has("bonus", "split", "sub-division") else "dividend", "record_date", 3)
    if d in ("Bonus", "Stock Split", "Sub-division"):
        return out("bonus_split", "declared", 1)
    if d.startswith("Credit Rating"):
        if "Revision" in d or has("upgrad", "downgrad", "revis"):
            return out("credit_rating", "revision", 1, ask=True)
        return out("credit_rating", "reaffirmed" if has("reaffirm") else "rating", 3)

    # --- ownership ----------------------------------------------------------------------
    if d == "Disclosure under SEBI Takeover Regulations":
        if "31(4)" in t:   # yearly "no encumbrance" declaration
            return out("pledging", "annual_declaration", 3)
        if has("pledge", "encumb", "31(1)", "31(2)"):
            return out("pledging", "pledge_change", 1, ask=True)
        return out("insider_trading", "sast", 2, ask=True)
    if d == "Trading Plan under PIT" or has("regulation 7(2)", "prohibition of insider trading"):
        return out("insider_trading", "pit", 2)

    # --- deals, disputes, operations ----------------------------------------------------
    if d in ("Acquisition", "Amalgamation/Merger", "Scheme of Arrangement", "Sale or disposal", "Other Restructuring",
             "Agreements", "Memorandum of Understanding/Agreements"):
        if has("incorporat", "dissol", "struck off", "step-down", "liquidat") and not has("acqui"):
            return out("M&A", "subsidiary_housekeeping", 3)
        return out("M&A", "deal", 2, ask=True)
    if d in ("Action(s) taken or orders passed", "Action(s) initiated or orders passed", "Suspension of Trading",
             "Corporate Insolvency Resolution Process") or d.startswith("Pendency of Litigation"):
        return out("litigation", "order", 2, ask=True)
    if d in ("Capacity addition", "Commencement of commercial production/operations"):
        return out("capex", "capacity", 2, ask=True)
    if d == "Bagging/Receiving of orders/contracts":
        return out("press_release", "order_win", 2, ask=True)
    if d in ("News Verification", "Rumour Verification - Regulation 30(11)"):
        return out("press_release", "rumour", 2)
    if d == "Disclosure of material issue":
        return out("press_release", "material", 1, ask=True)
    if d == "Shareholders meeting":
        if has("postal ballot"):
            return out("postal_ballot", "postal_ballot", 3)
        return out("agm_egm", "meeting", 3)

    # --- the three catch-all buckets ("Press Release", "Updates", "General Updates") -----
    if has("financial results", "results for the quarter", "quarter ended", "quarter and"):
        return out("results", "press", 3)
    if has("stock option", "esop", "trading window", "designated officer", "duplicate share", "loss of share",
           "newspaper", "investor grievance", "kmp authoris", "authorised to determine"):
        return out("unclassified", "compliance", 3)
    if has("analyst", "investor meet", "investor conference"):
        return out("investor_meetings", "meeting", 3)
    if has("postal ballot"):
        return out("postal_ballot", "postal_ballot", 3)
    if has("annual general meeting", "agm", "extraordinary general"):
        return out("agm_egm", "meeting", 3)
    if has("dividend"):
        return out("dividend", "declared", 2)
    if has("acqui", "merger", "demerger", "joint venture", "stake"):
        return out("M&A", "deal", 2, ask=True)
    if has("penalty", "order", "demand", "tax", "gst", "court", "tribunal", "sebi", "show cause", "litigation"):
        return out("litigation", "order", 2, ask=True)
    if has("capacity", "plant", "capex", "commission"):
        return out("capex", "capacity", 2, ask=True)
    if d == "Press Release" or has("release", "launch", "partner", "collaborat"):
        return out("press_release", "release", 3, ask=True)   # most are marketing; the model spots the rare real one
    return out("unclassified", "general", 3, ask=True)


CATEGORY_LABEL = {
    "results": "Results", "M&A": "M&A", "fund_raise": "Fund raise", "management_change": "Management change",
    "litigation": "Legal / regulatory", "insider_trading": "Insider trading", "earnings_call": "Earnings call",
    "investor_meetings": "Investor meetings", "credit_rating": "Credit rating", "dividend": "Dividend",
    "bonus_split": "Bonus / split", "capex": "Capex", "press_release": "Company news", "postal_ballot": "Postal ballot",
    "agm_egm": "AGM / EGM", "pledging": "Pledging", "unclassified": "Routine paperwork",
}
