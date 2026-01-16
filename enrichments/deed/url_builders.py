"""County-specific deed URL builders."""

from urllib.parse import quote_plus


def build_wake_url(deed_book: str, deed_page: str) -> str:
    """Wake County - Direct link via new CRPI system."""
    return (
        f"https://rodrecords.wake.gov/web/web/integration/search"
        f"?field_BookPageID_DOT_Volume={quote_plus(deed_book)}"
        f"&field_BookPageID_DOT_Page={quote_plus(deed_page)}"
    )


def build_durham_url() -> str:
    """Durham County - Search page only (requires Playwright for direct link)."""
    return "https://rodweb.dconc.gov/web/search/DOCSEARCH5S1"


def build_harnett_url(deed_book: str, deed_page: str) -> str:
    """Harnett County - Direct link via Courthouse Computer Systems."""
    return (
        f"https://us6.courthousecomputersystems.com/HarnettNC/Image/ShowDocImage"
        f"?booktype=Deed&tif2pdf=true&BookNum={quote_plus(deed_book)}&PageNum={quote_plus(deed_page)}"
    )


def build_orange_url(deed_book: str, deed_page: str) -> str:
    """Orange County - Direct link via Courthouse Computer Systems."""
    return (
        f"https://rod.orangecountync.gov/orangenc/Image/ShowDocImage"
        f"?booktype=Deed&tif2pdf=true&BookNum={quote_plus(deed_book)}&PageNum={quote_plus(deed_page)}"
    )


def build_lee_url() -> str:
    """Lee County - Opens disclaimer page first (Logan Systems requires acknowledgment)."""
    return "https://www.leencrod.org/Opening.asp"


def build_chatham_url() -> str:
    """Chatham County - Base URL (Logan Systems generates session on entry)."""
    return "https://www.chathamncrod.org/"
