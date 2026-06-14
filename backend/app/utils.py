import httpx


def httpx_client(proxy: str | None, timeout: int = 30) -> httpx.Client:
    if not proxy:
        return httpx.Client(timeout=timeout)
    try:
        return httpx.Client(proxy=proxy, timeout=timeout)
    except TypeError:
        return httpx.Client(proxies=proxy, timeout=timeout)
