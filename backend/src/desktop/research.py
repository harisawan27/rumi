"""Read a bounded set of public result links from DuckDuckGo's HTML search."""
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urlsplit


SEARCH_URL = "https://html.duckduckgo.com/html/"
MAX_PAGE_BYTES = 512 * 1024


class ResearchUnavailable(Exception):
    pass


@dataclass(frozen=True)
class SearchLink:
    title: str
    url: str


def result_url(href):
    try:
        url = urlsplit(href)
        if url.path == "/l/" and url.hostname in (None, "duckduckgo.com", "www.duckduckgo.com"):
            href = parse_qs(url.query, max_num_fields=20).get("uddg", [""])[0]
            url = urlsplit(href)
        if (url.scheme != "https" or not url.hostname or url.username is not None
                or url.password is not None or url.port not in (None, 443)
                or url.hostname in {"duckduckgo.com", "www.duckduckgo.com", "html.duckduckgo.com"}
                or len(href) > 1200 or any(char.isspace() or ord(char) < 32 or char == "\\" for char in href)):
            return None
        return href
    except ValueError:
        return None


class ResultLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.href = None
        self.parts = []

    def handle_starttag(self, tag, attributes):
        if tag != "a":
            return
        attrs = dict(attributes)
        self.href = None
        self.parts.clear()
        if "result__a" in (attrs.get("class") or "").split() and "result__a--ad" not in (attrs.get("class") or "").split():
            self.href = result_url(attrs.get("href") or "")

    def handle_data(self, data):
        if self.href:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag != "a" or not self.href:
            return
        title = " ".join("".join(self.parts).split())[:180]
        title = "".join(char for char in title if char.isprintable())
        if title and len(self.results) < 3 and all(link.url != self.href for link in self.results):
            self.results.append(SearchLink(title, self.href))
        self.href = None
        self.parts.clear()


def search_url(query):
    if query.startswith("\\") or any(word.startswith("!") for word in query.split()):
        raise ResearchUnavailable("Use a plain web search without redirect shortcuts.")
    return SEARCH_URL + "?" + urlencode({"q": query})


def parse_results(data):
    results = ResultLinks()
    results.feed(data.decode("utf-8", errors="replace"))
    results.close()
    if not results.results:
        raise ResearchUnavailable("I couldn't read any result links from DuckDuckGo. Try the search in your browser.")
    return tuple(results.results)
