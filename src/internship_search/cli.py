"""Command line entry point for the internship search tool."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="internship-search",
        description="Find and review internship opportunities.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show the current project version.",
    )
    subparsers = parser.add_subparsers(dest="command")

    show_inputs = subparsers.add_parser(
        "show-inputs",
        help="Show a safe summary of parsed private inputs.",
    )
    show_inputs.add_argument(
        "--private-dir",
        type=Path,
        default=Path("private"),
        help="Path to the private input directory.",
    )

    build_registry = subparsers.add_parser(
        "build-source-registry",
        help="Build the local company source registry from seed companies.",
    )
    build_registry.add_argument(
        "--private-dir",
        type=Path,
        default=Path("private"),
        help="Path to the private input directory.",
    )
    build_registry.add_argument(
        "--output",
        type=Path,
        default=Path("data/source_registry.json"),
        help="Path where the source registry JSON should be written.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        from internship_search import __version__

        print(__version__)
        return 0

    if args.command == "show-inputs":
        from internship_search.private_inputs import (
            load_private_inputs,
            summarize_private_inputs,
        )

        inputs = load_private_inputs(args.private_dir)
        print(summarize_private_inputs(inputs))
        return 0

    if args.command == "build-source-registry":
        from internship_search.source_registry import (
            load_seed_source_registry,
            summarize_source_registry,
            write_source_registry,
        )

        sources = load_seed_source_registry(args.private_dir)
        output_path = write_source_registry(sources, args.output)
        print(summarize_source_registry(sources))
        print("")
        print(f"Wrote registry to: {output_path}")
        return 0

    parser.print_help()
    return 0
