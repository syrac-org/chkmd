import asyncio
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from chkmd.checker import check_links, extract_links


def find_md_files(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix == ".md" else []

    search = path.rglob if recursive else path.glob
    return [p for p in search("*.md") if p.is_file()]


def get_args() -> Namespace:
    parser = ArgumentParser(description="Check links in Markdown files")
    parser.add_argument("paths", nargs="+", help="Files or directories to check")
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recurse into directories",
    )
    return parser.parse_args()


async def main_async() -> int:
    args = get_args()
    files_to_check = [
        p for path in args.paths for p in find_md_files(Path(path), args.recursive)
    ]

    if not files_to_check:
        print("No Markdown files found")
        return 0

    links = await extract_links(files_to_check)
    results = await check_links(links)

    n_broken = len([r for r in results if not r.is_ok])
    if n_broken > 0:
        print(f"{n_broken} broken links found")
        for result in results:
            if not result.is_ok:
                print(f"{result.original}: {result.reason}")
        return 1
    else:
        print("All links are good")
        return 0


def main() -> None:
    sys.exit(asyncio.run(main_async()))
