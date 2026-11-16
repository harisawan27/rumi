"""One bounded HTTPS request through the Windows client's normal TLS validation."""
from src.desktop.research import MAX_PAGE_BYTES, ResearchUnavailable, parse_results, search_url


def search_links(query, guard):
    url = search_url(query)
    guard()
    try:
        import clr
        clr.AddReference("System.Net.Http")
        from System import TimeSpan
        from System.Net.Http import HttpClient, HttpClientHandler
        from System.Security.Authentication import SslProtocols

        handler = HttpClientHandler()
        handler.SslProtocols = SslProtocols.Tls12
        handler.AllowAutoRedirect = False
        handler.UseCookies = False
        client = HttpClient(handler)
    except Exception as exc:
        raise ResearchUnavailable("The Windows web client is unavailable on this device.") from exc

    response = None
    try:
        client.MaxResponseContentBufferSize = MAX_PAGE_BYTES
        client.Timeout = TimeSpan.FromSeconds(8)
        client.DefaultRequestHeaders.UserAgent.ParseAdd("RumiDesktop/0.1 (user-initiated search)")
        client.DefaultRequestHeaders.Accept.ParseAdd("text/html")
        guard()
        try:
            response = client.GetAsync(url).GetAwaiter().GetResult()
            media_type = response.Content.Headers.ContentType
            if int(response.StatusCode) != 200 or not media_type or str(media_type.MediaType) != "text/html":
                raise ResearchUnavailable("DuckDuckGo did not return a results page. Try the search in your browser.")
            data = bytes(response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult())
        except ResearchUnavailable:
            raise
        except Exception as exc:
            raise ResearchUnavailable("I couldn't retrieve the search results. Check your connection and try again.") from exc
    finally:
        if response is not None:
            response.Dispose()
        client.Dispose()
    guard()
    return parse_results(data)
