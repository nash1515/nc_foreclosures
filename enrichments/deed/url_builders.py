"""County-specific deed URL builders."""


def build_wake_url(deed_book: str, deed_page: str) -> str:
    """Wake County - Direct link via new CRPI system."""
    return (
        f"https://rodrecords.wake.gov/web/web/integration/search"
        f"?field_BookPageID_DOT_Volume={deed_book}"
        f"&field_BookPageID_DOT_Page={deed_page}"
    )


def build_durham_url() -> str:
    """Durham County - Search page only (requires Playwright for direct link)."""
    return "https://rodweb.dconc.gov/web/search/DOCSEARCH5S1"


def build_harnett_url(deed_book: str, deed_page: str) -> str:
    """Harnett County - Direct link via Courthouse Computer Systems."""
    return (
        f"https://us6.courthousecomputersystems.com/HarnettNC/Image/ShowDocImage"
        f"?booktype=Deed&tif2pdf=true&BookNum={deed_book}&PageNum={deed_page}"
    )


def build_orange_url(deed_book: str, deed_page: str) -> str:
    """Orange County - Direct link via Courthouse Computer Systems."""
    return (
        f"https://rod.orangecountync.gov/orangenc/Image/ShowDocImage"
        f"?booktype=Deed&tif2pdf=true&BookNum={deed_book}&PageNum={deed_page}"
    )


def build_lee_url() -> str:
    """Lee County - Search page only (Logan Systems, user clicks Book/Page tab)."""
    return "https://www.leencrod.org/search.wgx"


def build_chatham_url() -> str:
    """Chatham County - Search page only (Logan Systems, user clicks Book/Page tab)."""
    return "https://www.chathamncrod.org/search.wgx"
