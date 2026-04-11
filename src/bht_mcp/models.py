"""BHt MCP Server — Data models, constants, and type contracts.

All other modules depend on this file. It defines:
- Response envelope (ToolResponse, Quota, ErrorInfo)
- Per-tool data contracts (BookInfo, SearchResult, TokenDetail, ...)
- Static constants (BOOKS_DATA, VALID_FIELDS, RESPONSE_FIELDS)
- Operational constants (DAILY_HTML_LIMIT, MIN_REQUEST_INTERVAL)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------


class ErrorCode(StrEnum):
    """Error codes returned in ToolResponse.error.code."""

    DAILY_LIMIT_REACHED = "daily_limit_reached"
    BHT_UNAVAILABLE = "bht_unavailable"
    PARSE_ERROR = "parse_error"
    INVALID_BOOK = "invalid_book"
    INVALID_FIELD = "invalid_field"


# ---------------------------------------------------------------------------
# Response envelope — wraps every tool's output
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Quota:
    daily_html_used: int
    daily_html_limit: int
    daily_html_remaining: int


@dataclass(slots=True)
class ErrorInfo:
    code: ErrorCode
    message: str
    suggestion: str


@dataclass(slots=True)
class ToolResponse:
    """Uniform envelope for all MCP tool responses.

    - On success: data is populated, error is None.
    - On error:   data is None, error is populated.
    - Quota is always present (even on error).
    - truncated/total_available only appear when results were cut by limit.
    """

    data: Any
    quota: Quota
    error: ErrorInfo | None = None
    truncated: bool = False
    total_available: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "data": _serialize(self.data),
            "quota": asdict(self.quota),
            "error": asdict(self.error) if self.error else None,
        }
        if self.truncated:
            result["truncated"] = True
            result["total_available"] = self.total_available
        return result


# ---------------------------------------------------------------------------
# Tool 1: bht_list_books
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class BookInfo:
    """A single book in the BHt database.

    For standard Hebrew Bible books, chapter_list is None — chapters are
    contiguous from 1 to `chapters`.  For Sirach manuscript fragments,
    chapter_list contains the explicit (non-contiguous) chapter numbers.
    """

    code: str
    name: str
    chapters: int
    chapter_list: tuple[int, ...] | None = None


# ---------------------------------------------------------------------------
# Tool 2: bht_field_info
# ---------------------------------------------------------------------------


class FieldGroup(StrEnum):
    BUECHER = "Bücher"
    WORT = "Wort"


@dataclass(slots=True, frozen=True)
class FieldInfo:
    name: str
    group: FieldGroup
    description: str


# ---------------------------------------------------------------------------
# Tool 3: bht_search
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SearchResult:
    """One row from flex_search API (postID=201), 10 fixed fields + cached flag."""

    buch: str
    beleg_nr: int
    token: str
    kapitel: int
    text: str
    vers: int
    satz: str
    bezug: str
    frag: int
    pos: int
    cached: bool


# ---------------------------------------------------------------------------
# Tool 4: bht_token_detail — nested structure matching beleg HTML §5.5
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class LocationInfo:
    buch: str
    kapitel: int
    vers: int
    satz: str
    pos: int
    beleg_nr: int


@dataclass(slots=True)
class TokenInfo:
    text: str
    betacode: str


@dataclass(slots=True)
class MorphologyInfo:
    person: str
    genus: str
    numerus: str
    stamm: str


@dataclass(slots=True)
class WortartInfo:
    full: str  # e.g. '112 Praefixkonjugation [ PK ] | 11 VERB | 1 Hauptwortart'
    wa_code: str  # e.g. '112'
    wa: str  # e.g. '11'
    wa2: str
    wa3: str


@dataclass(slots=True)
class FunktionenInfo:
    code: str  # e.g. '000000'
    wa_fun: str
    ps_fun: str
    gen_fun: str
    num_fun: str
    sem_fun: str


@dataclass(slots=True)
class BautypInfo:
    type: str  # e.g. 'ya12i3'
    bau_fun: str
    bau_el: str
    bau_el_fun: str
    bau_opp: str
    bau_var: str
    bau_ab: str
    alt: str


@dataclass(slots=True)
class EndungInfo:
    value: str  # e.g. '%y:0'
    erweiterung: str
    funktion: str


@dataclass(slots=True)
class BasisInfo:
    text: str  # e.g. 'ʾmr 1'
    betacode: str  # e.g. '%@%m%r 1'
    homonym: str
    bas_el: str
    bas_var: str
    bas_ab: str


@dataclass(slots=True)
class WurzelInfo:
    text: str  # e.g. 'ʾMR'
    betacode: str  # e.g. '%@%M%R'


@dataclass(slots=True)
class LexemInfo:
    text: str  # e.g. 'yaʾmir l+'
    betacode: str  # e.g. '%y%a%@%m%i%r l+'
    homonym: str


@dataclass(slots=True)
class NavigationInfo:
    """Internal parameters needed to fetch syntax tree / sentence analysis."""

    bm_nr: int
    s_nr: int


@dataclass(slots=True)
class TokenDetail:
    """Full morphological analysis of a single Hebrew Bible token.

    Structure mirrors PLAN.md Tool 4 return type and beleg HTML §5.5.
    """

    location: LocationInfo
    token: TokenInfo
    morphology: MorphologyInfo
    wortart: WortartInfo
    kernseme: str
    funktionen: FunktionenInfo
    bautyp: BautypInfo
    endung: EndungInfo
    basis: BasisInfo
    wurzel: WurzelInfo
    lexem: LexemInfo
    sprache: str
    navigation: NavigationInfo


# ---------------------------------------------------------------------------
# Tool 5: bht_syntax_tree — recursive node
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SyntaxNode:
    """Recursive syntax tree node (Wortfügungsebene).

    Leaf nodes have an empty children list.
    """

    value: str  # e.g. 'PV', 'NV', 'SUB'
    children: list[SyntaxNode]


# ---------------------------------------------------------------------------
# Tool 7: bht_text_annotations
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TextAnnotation:
    stellenangabe: str
    token: str
    type: str
    annotation: str


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _serialize(obj: Any) -> Any:
    """Recursively convert dataclasses/lists to plain dicts for JSON output."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    if isinstance(obj, tuple):
        return [_serialize(item) for item in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# Operational constants
# ---------------------------------------------------------------------------

DAILY_HTML_LIMIT: int = 150
"""Max HTML requests per day (beleg + tree + satz + text_anm combined)."""

MIN_REQUEST_INTERVAL: float = 1.0
"""Minimum seconds between consecutive BHt HTTP requests."""

BHT_BASE_URL: str = "https://www.bht.gwi.uni-muenchen.de"
BHT_AJAX_URL: str = f"{BHT_BASE_URL}/wp-admin/admin-ajax.php"
BHT_VIEWS_URL: str = f"{BHT_BASE_URL}/db_views"

SEARCH_POST_ID: int = 201
"""postID for beleg (full Bible token) flex_search endpoint."""

DEFAULT_SEARCH_LIMIT: int = 100
MAX_SEARCH_LIMIT: int = 1000


# ---------------------------------------------------------------------------
# Response fields — flex_search API returns exactly these 10 fields
# ---------------------------------------------------------------------------

RESPONSE_FIELDS: tuple[str, ...] = (
    "buch",
    "belegNr",
    "token",
    "kapitel",
    "text",
    "vers",
    "satz",
    "bezug",
    "frag",
    "pos",
)


# ---------------------------------------------------------------------------
# BOOKS_DATA — 47 books (39 Hebrew Bible + 8 Sirach fragments)
# ---------------------------------------------------------------------------

BOOKS_DATA: dict[str, BookInfo] = {b.code: b for b in (
    # Torah
    BookInfo("Gen", "Genesis", 50),
    BookInfo("Ex", "Exodus", 40),
    BookInfo("Lev", "Leviticus", 27),
    BookInfo("Num", "Numeri", 36),
    BookInfo("Dt", "Deuteronomium", 34),
    # Former Prophets
    BookInfo("Jos", "Josua", 24),
    BookInfo("Ri", "Richter", 21),
    BookInfo("1Sam", "1. Samuel", 31),
    BookInfo("2Sam", "2. Samuel", 24),
    BookInfo("1Koen", "1. Könige", 22),
    BookInfo("2Koen", "2. Könige", 25),
    # Latter Prophets
    BookInfo("Jes", "Jesaja", 66),
    BookInfo("Jer", "Jeremia", 52),
    BookInfo("Ez", "Ezechiel", 48),
    # Minor Prophets (the Twelve)
    BookInfo("Hos", "Hosea", 14),
    BookInfo("Joel", "Joel", 4),
    BookInfo("Am", "Amos", 9),
    BookInfo("Ob", "Obadja", 1),
    BookInfo("Jon", "Jona", 4),
    BookInfo("Mich", "Micha", 7),
    BookInfo("Nah", "Nahum", 3),
    BookInfo("Hab", "Habakuk", 3),
    BookInfo("Zef", "Zefanja", 3),
    BookInfo("Hag", "Haggai", 2),
    BookInfo("Sach", "Sacharja", 14),
    BookInfo("Mal", "Maleachi", 3),
    # Writings
    BookInfo("Ps", "Psalmen", 150),
    BookInfo("Ij", "Ijob", 42),
    BookInfo("Spr", "Sprüche", 31),
    BookInfo("Rut", "Rut", 4),
    BookInfo("Hl", "Hoheslied", 8),
    BookInfo("Koh", "Kohelet", 12),
    BookInfo("Klgl", "Klagelieder", 5),
    BookInfo("Est", "Ester", 10),
    BookInfo("Dan", "Daniel", 12),
    BookInfo("Esr", "Esra", 10),
    BookInfo("Neh", "Nehemia", 13),
    BookInfo("1Chr", "1. Chronik", 29),
    BookInfo("2Chr", "2. Chronik", 36),
    # Sirach manuscript fragments (non-contiguous chapters)
    BookInfo("ASir", "Sirach Quelle A", 17,
             (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 23, 27)),
    BookInfo("BSir", "Sirach Quelle B", 26,
             (10, 11, 15, 16, 20, 30, 32, 33, 34, 35, 36, 37, 38, 39,
              40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51)),
    BookInfo("CSir", "Sirach Quelle C", 13,
             (3, 4, 5, 6, 7, 18, 19, 20, 25, 26, 36, 37, 41)),
    BookInfo("DSir", "Sirach Quelle D", 3, (36, 37, 38)),
    BookInfo("ESir", "Sirach Quelle E", 4, (30, 31, 35, 36)),
    BookInfo("MSir", "Sirach Quelle M", 6, (39, 40, 41, 42, 43, 44)),
    BookInfo("QSir", "Sirach Quelle Q", 1, (6,)),
    BookInfo("TSir", "Sirach Quelle T", 1, (51,)),
)}

assert len(BOOKS_DATA) == 47, f"Expected 47 books, got {len(BOOKS_DATA)}"


# ---------------------------------------------------------------------------
# VALID_FIELDS — 42 search fields for flex_search (postID=201)
# ---------------------------------------------------------------------------

VALID_FIELDS: dict[str, FieldInfo] = {f.name: f for f in (
    # Bücher group
    FieldInfo("buchkat", FieldGroup.BUECHER, "Buchgruppe (book category)"),
    FieldInfo("buch", FieldGroup.BUECHER, "Buch (book code, e.g. 'Gen')"),
    # Wort group
    FieldInfo("stueck", FieldGroup.WORT, "Token (free text search)"),
    FieldInfo("ps", FieldGroup.WORT, "Person/Status (1, 2, 3, 0=n/a)"),
    FieldInfo("gen", FieldGroup.WORT, "Genus (M, F, 0=n/a)"),
    FieldInfo("num", FieldGroup.WORT, "Numerus (S=singular, P=plural, D=dual, 0=n/a)"),
    FieldInfo("endg", FieldGroup.WORT, "Endung (ending)"),
    FieldInfo("erw", FieldGroup.WORT, "Erweiterung (extension)"),
    FieldInfo("erwfun", FieldGroup.WORT, "Funktion der Erweiterung"),
    FieldInfo("stamm", FieldGroup.WORT, "Stamm (verbal stem: G=Qal, D=Piel, H=Hiphil, N=Niphal)"),
    FieldInfo("bautyp", FieldGroup.WORT, "Bautyp (construction type)"),
    FieldInfo("baufun", FieldGroup.WORT, "Baufunktion (construction function)"),
    FieldInfo("bauel", FieldGroup.WORT, "Bauelement (construction element)"),
    FieldInfo("bauelfun", FieldGroup.WORT, "Bauelement Funktion"),
    FieldInfo("bauopp", FieldGroup.WORT, "Bauopposition"),
    FieldInfo("bauvariante", FieldGroup.WORT, "Bauvariante"),
    FieldInfo("bauab", FieldGroup.WORT, "Bauableitung (construction derivation)"),
    FieldInfo("alt", FieldGroup.WORT, "Alternative"),
    FieldInfo("basis", FieldGroup.WORT, "Basis (base form)"),
    FieldInfo("basis2", FieldGroup.WORT, "Basis 2"),
    FieldInfo("bashom", FieldGroup.WORT, "Basis Homonym"),
    FieldInfo("basel", FieldGroup.WORT, "Basiselement"),
    FieldInfo("baselfun", FieldGroup.WORT, "Basiselement Funktion"),
    FieldInfo("basvar", FieldGroup.WORT, "Basis Variante"),
    FieldInfo("basab", FieldGroup.WORT, "Basis Ableitung (derivation)"),
    FieldInfo("Wurzel", FieldGroup.WORT, "Wurzel (root, e.g. 'BRʾ', 'ʾMR')"),
    FieldInfo("lexem", FieldGroup.WORT, "Lexem (lexeme)"),
    FieldInfo("lexhom", FieldGroup.WORT, "Lexem Homonym"),
    FieldInfo("komb", FieldGroup.WORT, "Kombination (combination)"),
    FieldInfo("wa", FieldGroup.WORT, "Wortart (part of speech, e.g. '11 VERB', '12 SUBSTANTIV')"),
    FieldInfo("wa2", FieldGroup.WORT, "Wortart 2"),
    FieldInfo("wa3", FieldGroup.WORT, "Wortart 3"),
    FieldInfo("funebene", FieldGroup.WORT, "Funktionsebene (function level)"),
    FieldInfo("wafun", FieldGroup.WORT, "Wortart Funktion"),
    FieldInfo("psfun", FieldGroup.WORT, "Personen Funktion"),
    FieldInfo("genfun", FieldGroup.WORT, "Genus Funktion"),
    FieldInfo("numfun", FieldGroup.WORT, "Numerus Funktion"),
    FieldInfo("semfun", FieldGroup.WORT, "semantische Funktion"),
    FieldInfo("ksem", FieldGroup.WORT, "Kernsem (core semantics)"),
    FieldInfo("msem", FieldGroup.WORT, "Merkmalsem (feature semantics)"),
    FieldInfo("semebene", FieldGroup.WORT, "Semebene (semantic level)"),
    FieldInfo("sprache", FieldGroup.WORT, "Sprache (language)"),
)}

assert len(VALID_FIELDS) == 42, f"Expected 42 fields, got {len(VALID_FIELDS)}"


# ---------------------------------------------------------------------------
# Book name → code lookups (for fuzzy resolution)
# ---------------------------------------------------------------------------

# German names from BOOKS_DATA (lowercased → BookInfo)
_NAME_TO_CODE: dict[str, BookInfo] = {
    b.name.lower(): b for b in BOOKS_DATA.values()
}

# English names that differ from German BHt names
_ENGLISH_ALIASES: dict[str, str] = {
    "genesis": "Gen",
    "exodus": "Ex",
    "leviticus": "Lev",
    "numbers": "Num",
    "deuteronomy": "Dt",
    "joshua": "Jos",
    "judges": "Ri",
    "1 samuel": "1Sam",
    "2 samuel": "2Sam",
    "1 kings": "1Koen",
    "2 kings": "2Koen",
    "isaiah": "Jes",
    "jeremiah": "Jer",
    "ezekiel": "Ez",
    "hosea": "Hos",
    "joel": "Joel",
    "amos": "Am",
    "obadiah": "Ob",
    "jonah": "Jon",
    "micah": "Mich",
    "nahum": "Nah",
    "habakkuk": "Hab",
    "zephaniah": "Zef",
    "haggai": "Hag",
    "zechariah": "Sach",
    "malachi": "Mal",
    "psalms": "Ps",
    "job": "Ij",
    "proverbs": "Spr",
    "ruth": "Rut",
    "song of solomon": "Hl",
    "song of songs": "Hl",
    "ecclesiastes": "Koh",
    "lamentations": "Klgl",
    "esther": "Est",
    "daniel": "Dan",
    "ezra": "Esr",
    "nehemiah": "Neh",
    "1 chronicles": "1Chr",
    "2 chronicles": "2Chr",
}


# ---------------------------------------------------------------------------
# Helpers — book/field validation
# ---------------------------------------------------------------------------


def validate_book(code: str) -> BookInfo:
    """Resolve a book identifier to BookInfo.

    Accepts: exact code ('Gen'), case-insensitive code ('gen'),
    German name ('Genesis', 'Psalmen'), or English name ('Exodus', 'Psalms').
    """
    # 1. Exact code match
    if code in BOOKS_DATA:
        return BOOKS_DATA[code]
    code_lower = code.lower()
    # 2. Case-insensitive code match
    for key, info in BOOKS_DATA.items():
        if key.lower() == code_lower:
            return info
    # 3. German name match (from BOOKS_DATA.name)
    if code_lower in _NAME_TO_CODE:
        return _NAME_TO_CODE[code_lower]
    # 4. English alias match
    if code_lower in _ENGLISH_ALIASES:
        return BOOKS_DATA[_ENGLISH_ALIASES[code_lower]]
    # 5. Not found
    raise ValueError(
        f"Book '{code}' not found. Use bht_list_books to see all valid codes."
    )


def validate_field(name: str) -> FieldInfo:
    """Return FieldInfo or raise ValueError with suggestion."""
    if name in VALID_FIELDS:
        return VALID_FIELDS[name]
    # Case-insensitive fallback
    for key, info in VALID_FIELDS.items():
        if key.lower() == name.lower():
            raise ValueError(
                f"Field '{name}' not found. Did you mean '{key}'?"
            )
    raise ValueError(
        f"Field '{name}' not found. Use bht_field_info to see all valid fields."
    )


# ---------------------------------------------------------------------------
# Betacode decoding — BHt uses betacode internally for text fields
# ---------------------------------------------------------------------------

# Betacode sequence → transcription character (observed from beleg HTML)
BETACODE_MAP: dict[str, str] = {
    # Uppercase consonants
    "%B": "B", "%G": "G", "%D": "D", "%H": "H", "%W": "W",
    "%Z": "Z", "%K": "K", "%L": "L", "%M": "M", "%N": "N",
    "%S": "S", "%P": "P", "%Q": "Q", "%R": "R", "%T": "T",
    "%Y": "Y",
    # Lowercase consonants + vowels
    "%a": "a", "%b": "b", "%g": "g", "%d": "d", "%e": "e",
    "%h": "h", "%i": "i", "%o": "o", "%u": "u", "%w": "w",
    "%z": "z", "%k": "k", "%l": "l", "%m": "m", "%n": "n",
    "%s": "s", "%p": "p", "%q": "q", "%r": "r", "%t": "t",
    "%y": "y",
    # Special characters
    "%@": "ʾ",  # aleph
    "%-": "-",
    "%(": "(",
    "%)": ")",
    "%[": "[",
    "%]": "]",
    "%.": "˙",
    "%*": "*",
    # Vowels with diacritics ($ prefix)
    "$a": "ā", "$i": "ī", "$o": "ō", "$e": "ē", "$u": "ū",
    "$A": "Ā", "$I": "Ī", "$O": "Ō", "$E": "Ē", "$U": "Ū",
    # Emphatic/special consonants ($ prefix)
    "$C": "Ṯ", "$D": "Ḏ", "$G": "Ġ", "$H": "Ḥ", "$K": "Ḫ",
    "$L": "Ḷ", "$M": "Ṯ", "$R": "Ṛ", "$S": "Ṣ", "$T": "Ṭ",
    "$U": "Ū", "$V": "Ḍ", "$Z": "Ẓ",
}


def decode_betacode(beta: str) -> str:
    """Decode a BHt betacode string to transcription.

    Example: '%B%R%@' → 'BRʾ', '%@%M%R' → 'ʾMR'
    Non-betacode characters (spaces, digits, '+') pass through unchanged.
    """
    result: list[str] = []
    i = 0
    while i < len(beta):
        if i + 1 < len(beta) and beta[i] in ("%", "$"):
            seq = beta[i : i + 2]
            if seq in BETACODE_MAP:
                result.append(BETACODE_MAP[seq])
                i += 2
                continue
        result.append(beta[i])
        i += 1
    return "".join(result)


def normalize_for_comparison(text: str) -> str:
    """Strip non-ASCII characters and lowercase for fuzzy betacode matching.

    'BRʾ' → 'br', 'ʾMR' → 'mr', '%B%R%@' → '%b%r%@'
    """
    return "".join(c.lower() for c in text if ord(c) < 128)


def is_valid_chapter(book: BookInfo, chapter: int) -> bool:
    """Check if a chapter number is valid for the given book."""
    if book.chapter_list is not None:
        return chapter in book.chapter_list
    return 1 <= chapter <= book.chapters
