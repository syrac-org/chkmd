import asyncio
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from aiofiles import open as aio_open
from aiohttp import (
    ClientConnectorDNSError,
    ClientError,
    ClientSession,
    ClientTimeout,
    TCPConnector,
)
from lxml import etree
from markdown_it import MarkdownIt


@dataclass
class LinkCheckResult:
    original: str
    is_ok: bool
    reason: str


async def extract_links(files: list[Path]) -> dict[str, list[Path]]:
    links = {}
    tasks = [extract_links_from_file(file) for file in files]
    results = await asyncio.gather(*tasks)
    for file, file_links in results:
        for link in file_links:
            if link not in links:
                links[link] = []
            links[link].append(file)
    return links


async def extract_links_from_file(file: Path) -> tuple[Path, set[str]]:
    async with aio_open(file, "r", encoding="utf-8") as f:
        text = await f.read()
    contents = MarkdownIt().render(text)
    document = etree.fromstring(contents, etree.HTMLParser())
    links: set[str] = set()
    for a in document.findall(".//a[@href]"):
        links.add(a.attrib["href"])
    for img in document.findall(".//img[@src]"):
        links.add(img.attrib["src"].text)
    return file, links


async def check_links(links: dict[str, list[Path]]) -> list[LinkCheckResult]:
    async with ClientSession(
        headers={"User-Agent": "chkmd/0.1.0"},
        timeout=ClientTimeout(total=10),
        connector=TCPConnector(limit=50),
    ) as session:
        tasks = [
            check_single_link(link, session, sources) for link, sources in links.items()
        ]
        results = await asyncio.gather(*tasks)
        return results


async def check_single_link(
    link: str, session: ClientSession, sources: list[Path]
) -> LinkCheckResult:
    parsed = urlparse(link)
    if parsed.scheme in ("http", "https"):
        return await check_http_link(link, session)
    elif parsed.scheme == "" or parsed.scheme == "file":
        return await check_local_link(link, sources)
    else:
        return LinkCheckResult(link, False, f"Unsupported scheme: {parsed.scheme}")


async def check_http_link(
    url: str,
    session: ClientSession,
) -> LinkCheckResult:
    try:
        async with session.get(
            url, raise_for_status=True, allow_redirects=True
        ) as response:
            return LinkCheckResult(url, True, f"Status: {response.status}")
    except (ClientError, ClientConnectorDNSError) as e:
        return LinkCheckResult(url, False, f"Error: {e}")


async def check_local_link(url: str, sources: list[Path]) -> LinkCheckResult:
    if url.startswith("file://"):
        url = url[len("file://") :]

    for source in sources:
        complete_url = source.parent.joinpath(url).resolve()
        if not complete_url.exists():
            return LinkCheckResult(url, False, f"File not found: {complete_url}")
    return LinkCheckResult(url, True, "File exists")
