"""Automatic checks on what families contribute to the community catalog.

Each check is a small rule that raises a flag with a plain-words reason, at
one of two levels:

- ``review``: an admin decides (a child's name, an uploaded cover, an ISBN
  that belongs to another book, a link that isn't on the known list).
- ``note``: context for the admin (a first-time contributor, a 6% page
  mismatch, three other families entered exactly the same thing).

The third level, "fix before saving", is the family's own readiness check
(``app.services.library_rules``): an item isn't contributed until it's ready
to schedule, so keyboard mashing and broken chapter pages never reach the
queue.

These functions only look at what they're given; ``app.services.community``
gathers the facts (the family's children's names, the cached book, earlier
contributions) and stores the flags. See docs/6-planning/product-spine.md
("Automatic checks").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageStat, UnidentifiedImageError

from app.services.text_checks import keyboard_mash_reason
from app.utils.isbn import is_valid_isbn

REVIEW, NOTE = "review", "note"


@dataclass(frozen=True)
class Flag:
    code: str
    group: str
    level: str
    where: str
    message: str


# --- What text a contribution carries -----------------------------------------

def text_fields(data: dict) -> list[tuple[str, str]]:
    """Every piece of free text in a contribution, with where it is."""
    found: list[tuple[str, str]] = []
    for name, label in (("title", "Title"), ("author", "Author"), ("publisher", "Publisher"),
                        ("series", "Series"), ("edition", "Edition"), ("name", "Name")):
        if data.get(name):
            found.append((label, str(data[name])))
    for index, chapter in enumerate(data.get("chapters") or [], start=1):
        if chapter.get("name"):
            found.append((f"Chapter {index}", chapter["name"]))
    for lesson in data.get("lessons") or []:
        label = f"Lesson {lesson.get('number')}" if lesson.get("number") is not None else "A lesson"
        for name in ("name", "unit"):
            if lesson.get(name):
                found.append((label, lesson[name]))
    return found


# --- Privacy ------------------------------------------------------------------

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<![\d-])(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?![\d-])")
_STREET = re.compile(
    r"\b\d{2,6}\s+(?:[A-Z][a-z]+\s+){1,3}"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Court|Ct|Boulevard|Blvd|Circle|Cir|Way|"
    r"Place|Pl|Terrace|Parkway|Pkwy)\b"
)


def first_names(names: list[str]) -> list[str]:
    """The family's children's first names worth looking for (3 letters or more)."""
    found = set()
    for name in names:
        parts = name.split()
        if parts and len(parts[0]) >= 3:
            found.add(parts[0].lower())
    return sorted(found)


def privacy_flags(fields: list[tuple[str, str]], child_first_names: list[str]) -> list[Flag]:
    flags: list[Flag] = []
    patterns = [re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE) for name in child_first_names]
    for where, text in fields:
        if any(pattern.search(text) for pattern in patterns):
            # The name itself isn't repeated in the flag.
            flags.append(Flag("child_name", "privacy", REVIEW, where,
                              "Contains the first name of a child in the contributing family."))
        if _EMAIL.search(text):
            flags.append(Flag("email", "privacy", REVIEW, where, "Contains an email address."))
        if _PHONE.search(text):
            flags.append(Flag("phone", "privacy", REVIEW, where, "Contains what looks like a phone number."))
        if _STREET.search(text):
            flags.append(Flag("address", "privacy", REVIEW, where, "Contains what looks like a street address."))
    return flags


# --- Spam and junk ------------------------------------------------------------

# A short list; reviewers catch the rest.
_PROFANITY = re.compile(r"\b(?:fuck\w*|shit\w*|bitch\w*|cunt\w*|asshole\w*|slut\w*|whore\w*)\b", re.IGNORECASE)
_LINK_IN_TEXT = re.compile(r"https?://|\bwww\.", re.IGNORECASE)


def spam_flags(fields: list[tuple[str, str]]) -> list[Flag]:
    flags: list[Flag] = []
    for where, text in fields:
        reason = keyboard_mash_reason(text)
        if reason:
            flags.append(Flag("keyboard_mash", "spam", REVIEW, where, f"Doesn't look like real words ({reason})."))
        if _PROFANITY.search(text):
            flags.append(Flag("profanity", "spam", REVIEW, where, "Contains a swear word."))
        if _LINK_IN_TEXT.search(text):
            flags.append(Flag("link_in_text", "spam", REVIEW, where, "Contains a link where a name belongs."))
    for where, text in fields:
        if where == "Title":
            letters = [char for char in text if char.isalpha()]
            if len(letters) >= 8 and all(char.isupper() for char in letters):
                flags.append(Flag("all_caps", "spam", NOTE, where, "Written in all capitals; tidy it when approving."))
    return flags


# --- Copying ------------------------------------------------------------------

LONG_LESSON_NAME = 120


def copying_flags(data: dict) -> list[Flag]:
    lessons = data.get("lessons") or []
    long_ones = [lesson for lesson in lessons if len(lesson.get("name") or "") > LONG_LESSON_NAME]
    if not long_ones:
        return []
    first = long_ones[0]
    where = f"Lesson {first.get('number')}" if first.get("number") is not None else "A lesson"
    count = f"{len(long_ones)} lesson names are" if len(long_ones) > 1 else "A lesson name is"
    return [Flag("long_text", "copying", REVIEW, where,
                 f"{count} longer than {LONG_LESSON_NAME} characters: could be text copied from a "
                 "teacher's guide (a copyright risk). Lesson names should be short.")]


# --- Online links -------------------------------------------------------------

_SHORTENERS = frozenset({
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "rebrand.ly",
    "cutt.ly", "shorturl.at", "tiny.cc", "rb.gy", "t.ly",
})
# Education sites families commonly schedule. A link elsewhere isn't wrong,
# just worth a look before every family sees it.
EDUCATION_SITES = frozenset({
    "abcmouse.com", "abeka.com", "acellus.com", "adaptedmind.com", "allaboutlearningpress.com",
    "allinonehomeschool.com", "aop.com", "artofproblemsolving.com", "beastacademy.com", "bjupress.com",
    "bjupresshomeschool.com", "brainpop.com", "code.org", "commonlit.org", "ctcmath.com",
    "demmelearning.com", "duolingo.com", "edpuzzle.com", "education.com", "epic.com", "getepic.com",
    "generationgenius.com", "iew.com", "ixl.com", "khanacademy.org", "khanacademykids.org", "lexialearning.com",
    "masterbooks.com", "mathmammoth.com", "mathletics.com", "mathseeds.com", "mathusee.com", "memoriapress.com",
    "mysteryscience.com", "newsela.com", "outschool.com", "pbskids.org", "prodigygame.com", "quizlet.com",
    "readingeggs.com", "readtheory.org", "readworks.org", "rightstartmath.com", "rosettastone.com",
    "schoolhouseteachers.com", "scratch.mit.edu", "singaporemath.com", "sonlight.com", "splashlearn.com",
    "starfall.com", "teachingtextbooks.com", "thegoodandthebeautiful.com", "time4learning.com",
    "typing.com", "typingclub.com", "vocabularyspellingcity.com", "zearn.org",
})


def _known_site(host: str) -> bool:
    host = host.lower().removeprefix("www.")
    if host.endswith((".edu", ".gov")) or ".k12." in host:
        return True
    return any(host == site or host.endswith("." + site) for site in EDUCATION_SITES)


_PERSONAL_PATH = re.compile(r"sign-?in|log-?in|join|invite|class(room)?|/u/|/users?/|code", re.IGNORECASE)


def link_flags(data: dict) -> list[Flag]:
    url = data.get("website_url")
    if not url:
        return []
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https":
        return [Flag("not_https", "link", REVIEW, "Website link", "The link isn't https.")]
    if host.removeprefix("www.") in _SHORTENERS:
        return [Flag("shortener", "link", REVIEW, "Website link",
                     "A link shortener hides where the link goes. Use the program's own address.")]
    flags = []
    if not _known_site(host):
        flags.append(Flag("unknown_site", "link", REVIEW, "Website link",
                          f"{host} isn't on the list of known education sites. Check it's a real program."))
    if parts.query or _PERSONAL_PATH.search(parts.path):
        # A class sign-in page or a join code can identify the family.
        flags.append(Flag("personal_link", "privacy", REVIEW, "Website link",
                          "The link may be the family's own (a sign-in page, a class or a code). "
                          "Share the program's main address instead."))
    return flags


# --- Identity -----------------------------------------------------------------

@dataclass(frozen=True)
class CachedBook:
    """What the book lookup (Open Library or Google Books) knows about an ISBN."""

    title: str
    authors: list[str]
    page_count: int | None


_WORDS = re.compile(r"[a-z0-9]+")


def _words(text: str | None) -> set[str]:
    return {word for word in _WORDS.findall((text or "").lower()) if len(word) > 1}


def identity_flags(data: dict, cached: CachedBook | None) -> list[Flag]:
    flags: list[Flag] = []
    isbn = data.get("isbn")
    if isbn and not is_valid_isbn(isbn):
        flags.append(Flag("isbn_checksum", "identity", REVIEW, "ISBN",
                          f"{isbn} isn't a valid ISBN (its check digit is wrong)."))
    if cached is None:
        return flags
    mine, theirs = _words(data.get("title")), _words(cached.title)
    if mine and theirs and not (mine & theirs):
        flags.append(Flag("isbn_title", "identity", REVIEW, "ISBN",
                          f'The book lookup says this ISBN is "{cached.title}".'))
    author = data.get("author")
    if author and cached.authors and not (_words(author) & _words(" ".join(cached.authors))):
        flags.append(Flag("isbn_author", "identity", NOTE, "Author",
                          f"The book lookup lists {', '.join(cached.authors)}."))
    pages = data.get("total_pages")
    if pages and cached.page_count:
        off = abs(pages - cached.page_count) / cached.page_count
        if off > 0.10:
            flags.append(Flag("pages_off", "identity", REVIEW, "Total pages",
                              f"{pages} pages; the book lookup says {cached.page_count}."))
        elif off > 0.05:
            flags.append(Flag("pages_off", "identity", NOTE, "Total pages",
                              f"{pages} pages; the book lookup says {cached.page_count}."))
    return flags


# Spellings of the same publisher, saved one way in the catalog.
PUBLISHER_NAMES = {
    "bju press": "BJU Press",
    "bob jones university press": "BJU Press",
    "bob jones": "BJU Press",
    "bju": "BJU Press",
    "abeka": "Abeka",
    "a beka": "Abeka",
    "a beka book": "Abeka",
    "abeka book": "Abeka",
    "saxon": "Saxon Publishers",
    "saxon publishers": "Saxon Publishers",
    "saxon homeschool": "Saxon Publishers",
    "master books": "Master Books",
    "masterbooks": "Master Books",
    "apologia": "Apologia",
    "apologia educational ministries": "Apologia",
    "christian light": "Christian Light Publications",
    "christian light publications": "Christian Light Publications",
    "the good and the beautiful": "The Good and the Beautiful",
    "good and the beautiful": "The Good and the Beautiful",
    "evan-moor": "Evan-Moor",
    "evan moor": "Evan-Moor",
    "carson dellosa": "Carson Dellosa",
    "carson-dellosa": "Carson Dellosa",
    "carson dellosa education": "Carson Dellosa",
}


def normalize_publisher(name: str | None) -> str | None:
    if not name:
        return name
    key = " ".join(name.lower().replace(",", " ").replace(".", " ").split())
    key = key.removesuffix(" inc").removesuffix(" llc")
    return PUBLISHER_NAMES.get(key, name)


def publisher_flags(data: dict) -> list[Flag]:
    given = data.get("publisher")
    canonical = normalize_publisher(given)
    if given and canonical != given:
        return [Flag("publisher_name", "identity", NOTE, "Publisher", f'Will be saved as "{canonical}".')]
    return []


# --- Structure ----------------------------------------------------------------

def structure_flags(problems: list[tuple[str, str]]) -> list[Flag]:
    """The family's own "worth a look" checks (gaps in lesson numbers, pages going back)."""
    return [Flag("structure", "structure", NOTE, where, message) for where, message in problems]


# --- Covers -------------------------------------------------------------------

@dataclass(frozen=True)
class CoverFacts:
    width: int
    height: int
    spread: float  # how much the shades vary; near 0 is one flat color
    image_hash: str  # 16 hex characters; the same picture gives the same hash


def cover_facts(path: Path) -> CoverFacts | None:
    try:
        with Image.open(path) as image:
            gray = image.convert("L")
            spread = ImageStat.Stat(gray).stddev[0]
            small = gray.resize((8, 8))
            pixels = list(small.getdata())
            mean = sum(pixels) / len(pixels)
            bits = "".join("1" if pixel >= mean else "0" for pixel in pixels)
            return CoverFacts(image.width, image.height, spread, f"{int(bits, 2):016x}")
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def cover_flags(facts: CoverFacts | None, reused_from: str | None) -> list[Flag]:
    flags = [Flag("cover_uploaded", "cover", REVIEW, "Cover",
                  "A new cover image: check it's the published cover (not a photo of the book), "
                  "and that it shows no one's face or home.")]
    if facts is None:
        flags.append(Flag("cover_unreadable", "cover", REVIEW, "Cover", "The image couldn't be opened."))
        return flags
    if facts.width < 200 or facts.height < 250:
        flags.append(Flag("cover_small", "cover", REVIEW, "Cover", f"Small ({facts.width}×{facts.height})."))
    ratio = facts.height / facts.width if facts.width else 0
    if not 0.9 <= ratio <= 1.8:
        flags.append(Flag("cover_shape", "cover", NOTE, "Cover",
                          f"An unusual shape for a cover ({facts.width}×{facts.height})."))
    if facts.spread < 10:
        flags.append(Flag("cover_blank", "cover", REVIEW, "Cover", "Mostly one color."))
    if reused_from:
        flags.append(Flag("cover_reused", "cover", REVIEW, "Cover", f'The same image as the cover of "{reused_from}".'))
    return flags


# --- Behavior (context, not a verdict) ----------------------------------------

@dataclass(frozen=True)
class ContributorFacts:
    accepted: int  # earlier contributions approved or merged
    rejected: int
    last_hour: int  # contributions in the last hour, this one included
    seconds_to_enter: float | None  # from adding the item to now
    lessons: int


def behavior_flags(facts: ContributorFacts) -> list[Flag]:
    flags: list[Flag] = []
    if facts.accepted == 0:
        flags.append(Flag("first_time", "behavior", NOTE, "Contributor", "A first-time contributor."))
    if facts.rejected >= 2:
        flags.append(Flag("rejections", "behavior", NOTE, "Contributor",
                          f"{facts.rejected} earlier contributions were rejected."))
    if facts.last_hour >= 10:
        flags.append(Flag("many_entries", "behavior", NOTE, "Contributor",
                          f"{facts.last_hour} entries from this family in the last hour."))
    if facts.lessons >= 50 and facts.seconds_to_enter is not None and facts.seconds_to_enter < 120:
        flags.append(Flag("fast_entry", "behavior", NOTE, "Lesson list",
                          f"{facts.lessons} lessons entered within two minutes (pasted or imported?)."))
    return flags


# --- Agreement and duplicates -------------------------------------------------

@dataclass(frozen=True)
class AgreementFacts:
    same_as_others: int  # other families' contributions with exactly the same details
    others_agreeing: int  # other families who agree with each other but not with this one
    duplicate_of: tuple[int, str] | None  # a published entry this repeats (id, title)
    correction_of: tuple[int, int, str] | None  # (entry id, version, what changed)
    same_correction: int  # other families who made the same change


def agreement_flags(facts: AgreementFacts) -> list[Flag]:
    flags: list[Flag] = []
    if facts.correction_of:
        entry_id, version, changed = facts.correction_of
        flags.append(Flag("correction", "agreement", REVIEW, "Catalog entry",
                          f"Changes catalog entry #{entry_id} (version {version}): {changed}."))
    if facts.same_correction:
        families = "family" if facts.same_correction == 1 else "families"
        flags.append(Flag("same_correction", "agreement", NOTE, "Catalog entry",
                          f"{facts.same_correction} other {families} made the same change."))
    if facts.duplicate_of:
        entry_id, title = facts.duplicate_of
        flags.append(Flag("duplicate", "identity", REVIEW, "Catalog entry",
                          f'Already in the catalog as "{title}" (#{entry_id}). Merge into it?'))
    if facts.same_as_others:
        families = "family" if facts.same_as_others == 1 else "families"
        flags.append(Flag("agrees", "agreement", NOTE, "Details",
                          f"{facts.same_as_others} other {families} entered exactly the same details."))
    elif facts.others_agreeing >= 2:
        flags.append(Flag("disagrees", "agreement", REVIEW, "Details",
                          f"Differs from what {facts.others_agreeing} other families entered for the same book."))
    return flags
