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
    build_registry.add_argument(
        "--enrich-from-search",
        type=Path,
        default=None,
        help="Optional internet search results JSONL used to improve careers URLs.",
    )

    collect = subparsers.add_parser(
        "collect",
        help="Collect job posting candidates from the source registry.",
    )
    collect.add_argument(
        "--registry",
        type=Path,
        default=Path("data/source_registry.json"),
        help="Path to the source registry JSON file.",
    )
    collect.add_argument(
        "--output",
        type=Path,
        default=Path("data/postings.jsonl"),
        help="Path where collected postings should be written.",
    )
    collect.add_argument(
        "--private-dir",
        type=Path,
        default=Path("private"),
        help="Path to private inputs, used only if the registry is missing.",
    )

    collect.add_argument(
        "--enrich-from-search",
        type=Path,
        default=None,
        help="Optional internet search results JSONL used to improve careers URLs before collection.",
    )
    collect.add_argument(
        "--include-job-boards",
        action="store_true",
        help="Also search external job boards and merge results into postings.jsonl.",
    )
    collect.add_argument(
        "--target-year",
        default="2027",
        help="Internship year used for job-board search queries.",
    )

    search_job_boards = subparsers.add_parser(
        "search-job-boards",
        help="Search external job boards for internship posting candidates.",
    )
    search_job_boards.add_argument(
        "--query",
        help="Optional custom job-board search query.",
    )
    search_job_boards.add_argument(
        "--target-year",
        default="2027",
        help="Internship year used when --query is not provided.",
    )
    search_job_boards.add_argument(
        "--max-results",
        type=int,
        default=20,
        help="Maximum number of posting candidates to return.",
    )
    search_job_boards.add_argument(
        "--output",
        type=Path,
        default=Path("data/job_board_postings.jsonl"),
        help="Path where job-board posting candidates should be written.",
    )

    filter_postings = subparsers.add_parser(
        "filter-postings",
        help="Filter posting candidates for likely Summer 2027 internship relevance. Also writes a monitored-companies list for seed companies with no specific openings.",
    )
    filter_postings.add_argument(
        "--input",
        type=Path,
        default=Path("data/postings.jsonl"),
        help="Path to collected posting candidates.",
    )
    filter_postings.add_argument(
        "--included-output",
        type=Path,
        default=Path("data/filtered_postings.jsonl"),
        help="Path where included postings should be written.",
    )
    filter_postings.add_argument(
        "--excluded-output",
        type=Path,
        default=Path("data/excluded_postings.jsonl"),
        help="Path where excluded postings should be written.",
    )
    filter_postings.add_argument(
        "--registry",
        type=Path,
        default=Path("data/source_registry.json"),
        help="Path to the source registry used to build the monitored-no-openings list.",
    )
    filter_postings.add_argument(
        "--monitored-output",
        type=Path,
        default=Path("data/monitored_no_openings.jsonl"),
        help="Path where monitored companies with no openings should be written.",
    )
    filter_postings.add_argument(
        "--collection-errors",
        type=Path,
        default=Path("data/collection_errors.jsonl"),
        help="Path to collection errors from the latest collect run.",
    )

    report = subparsers.add_parser(
        "report",
        help="Generate a local Markdown review report from filtered postings.",
    )
    report.add_argument(
        "--included",
        type=Path,
        default=Path("data/filtered_postings.jsonl"),
        help="Path to included filtered postings.",
    )
    report.add_argument(
        "--excluded",
        type=Path,
        default=Path("data/excluded_postings.jsonl"),
        help="Path to excluded filtered postings.",
    )
    report.add_argument(
        "--registry",
        type=Path,
        default=Path("data/source_registry.json"),
        help="Path to the source registry JSON file.",
    )
    report.add_argument(
        "--output",
        type=Path,
        default=Path("data/latest_report.md"),
        help="Path where the Markdown report should be written.",
    )
    report.add_argument(
        "--monitored",
        type=Path,
        default=Path("data/monitored_no_openings.jsonl"),
        help="Path to monitored companies with no specific openings.",
    )

    score_postings = subparsers.add_parser(
        "score-postings",
        help="Score filtered postings against private profile inputs.",
    )
    score_postings.add_argument(
        "--postings",
        type=Path,
        default=Path("data/filtered_postings.jsonl"),
        help="Path to included filtered postings.",
    )
    score_postings.add_argument(
        "--private-dir",
        type=Path,
        default=Path("private"),
        help="Path to the private input directory.",
    )
    score_postings.add_argument(
        "--registry",
        type=Path,
        default=Path("data/source_registry.json"),
        help="Path to the source registry JSON file.",
    )
    score_postings.add_argument(
        "--output",
        type=Path,
        default=Path("data/scored_postings.jsonl"),
        help="Path where scored postings should be written.",
    )
    score_postings.add_argument(
        "--provider",
        choices=["auto", "local", "gemini"],
        default="auto",
        help="Scoring provider. auto uses Gemini when AI_PROVIDER_API_KEY is set.",
    )
    score_postings.add_argument(
        "--resume-aware",
        action="store_true",
        help="Include private/resume_summary.md in Gemini scoring prompts for this run.",
    )

    detect_new = subparsers.add_parser(
        "detect-new-postings",
        help="Update posting history and detect new, changed, seen, or missing postings.",
    )
    detect_new.add_argument(
        "--postings",
        type=Path,
        default=Path("data/postings.jsonl"),
        help="Path to current collected postings.",
    )
    detect_new.add_argument(
        "--history",
        type=Path,
        default=Path("data/posting_history.json"),
        help="Path to local posting history.",
    )
    detect_new.add_argument(
        "--changes-output",
        type=Path,
        default=Path("data/posting_changes.jsonl"),
        help="Path where per-run posting changes should be written.",
    )
    detect_new.add_argument(
        "--new-output",
        type=Path,
        default=Path("data/new_postings.jsonl"),
        help="Path where newly discovered postings should be written.",
    )

    weekly_email = subparsers.add_parser(
        "weekly-email-summary",
        help="Generate a local weekly email summary draft and optionally send it.",
    )
    weekly_email.add_argument(
        "--scored",
        type=Path,
        default=Path("data/scored_postings.jsonl"),
        help="Path to scored postings.",
    )
    weekly_email.add_argument(
        "--new-postings",
        type=Path,
        default=Path("data/new_postings.jsonl"),
        help="Path to newly discovered postings.",
    )
    weekly_email.add_argument(
        "--registry",
        type=Path,
        default=Path("data/source_registry.json"),
        help="Path to the source registry JSON file.",
    )
    weekly_email.add_argument(
        "--output",
        type=Path,
        default=Path("data/weekly_email_summary.md"),
        help="Path where the local email summary draft should be written.",
    )
    weekly_email.add_argument(
        "--sent-history",
        type=Path,
        default=Path("data/email_sent_history.json"),
        help="Path to the record of postings already included in email summaries.",
    )
    weekly_email.add_argument(
        "--collection-errors",
        type=Path,
        default=Path("data/collection_errors.jsonl"),
        help="Path to latest company job-site access errors to include in the email.",
    )
    weekly_email.add_argument(
        "--recipient",
        default=None,
        help="Optional email recipient. Defaults to EMAIL_TO from the private .env file.",
    )
    weekly_email.add_argument(
        "--send",
        action="store_true",
        help="Send the weekly summary by SMTP when EMAIL_FROM and EMAIL_SMTP_PASSWORD are configured.",
    )

    scheduled_collection = subparsers.add_parser(
        "run-scheduled-collection",
        help="Run the full local collection workflow and write a run log.",
    )
    scheduled_collection.add_argument(
        "--private-dir",
        type=Path,
        default=Path("private"),
        help="Path to the private input directory.",
    )
    scheduled_collection.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Path where generated workflow outputs and logs should be written.",
    )
    scheduled_collection.add_argument(
        "--skip-email",
        action="store_true",
        help="Skip generating the weekly email summary draft.",
    )
    scheduled_collection.add_argument(
        "--send-email",
        action="store_true",
        help="Send the weekly email summary after generating the draft.",
    )
    scheduled_collection.add_argument(
        "--resume-aware",
        action="store_true",
        help="Include private/resume_summary.md in Gemini scoring prompts for this run.",
    )
    scheduled_collection.add_argument(
        "--include-job-boards",
        action="store_true",
        help="Also search external job boards and merge results into postings.jsonl.",
    )
    scheduled_collection.add_argument(
        "--target-year",
        default="2027",
        help="Internship year used for job-board search queries.",
    )

    discover_companies = subparsers.add_parser(
        "discover-companies",
        help="Suggest similar companies for review before adding to collection.",
    )
    discover_companies.add_argument(
        "--private-dir",
        type=Path,
        default=Path("private"),
        help="Path to the private input directory.",
    )
    discover_companies.add_argument(
        "--registry",
        type=Path,
        default=Path("data/source_registry.json"),
        help="Path to the source registry JSON file.",
    )
    discover_companies.add_argument(
        "--output",
        type=Path,
        default=Path("data/discovered_companies.json"),
        help="Path where discovered companies JSON should be written.",
    )
    discover_companies.add_argument(
        "--report",
        type=Path,
        default=Path("data/discovered_companies.md"),
        help="Path where the discovery review report should be written.",
    )
    discover_companies.add_argument(
        "--update-registry",
        action="store_true",
        help="Merge suggested companies into the source registry.",
    )
    discover_companies.add_argument(
        "--no-internet",
        action="store_true",
        help="Use only the local curated discovery list without internet search.",
    )

    review_ui = subparsers.add_parser(
        "review-ui",
        help="Start a local web UI for reviewing postings and preferences.",
    )
    review_ui.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address for the local review UI.",
    )
    review_ui.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for the local review UI.",
    )
    review_ui.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Path to generated data files used by the review UI.",
    )
    review_ui.add_argument(
        "--private-dir",
        type=Path,
        default=Path("private"),
        help="Path to private input files used for default preferences.",
    )
    review_ui.add_argument(
        "--no-open-browser",
        action="store_true",
        help="Do not open the review UI in your default browser automatically.",
    )

    internet_search = subparsers.add_parser(
        "internet-search",
        help="Search the internet for company careers pages and related links.",
    )
    internet_search.add_argument(
        "--query",
        help="Search query, for example 'BlackRock summer 2027 internship careers'.",
    )
    internet_search.add_argument(
        "--company",
        help="Seed company name. Builds a careers-focused query automatically.",
    )
    internet_search.add_argument(
        "--target-year",
        default="2027",
        help="Internship year used when --company is provided.",
    )
    internet_search.add_argument(
        "--provider",
        choices=["auto", "duckduckgo_html", "google_custom_search", "tavily"],
        default="auto",
        help=(
            "Search provider. auto tries DuckDuckGo first, then Google Custom Search "
            "when GOOGLE_CUSTOM_SEARCH_API_KEY and GOOGLE_CSE_ID are set."
        ),
    )
    internet_search.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Maximum number of search results to return.",
    )
    internet_search.add_argument(
        "--output",
        type=Path,
        default=Path("data/internet_search_results.jsonl"),
        help="Path where structured search results should be written.",
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
        from internship_search.registry_enrichment import enrich_sources_from_search_results
        from internship_search.source_registry import (
            load_seed_source_registry,
            summarize_source_registry,
            write_source_registry,
        )

        sources = load_seed_source_registry(args.private_dir)
        enrichment_notes: list[str] = []
        if args.enrich_from_search is not None:
            sources, enrichment_notes = enrich_sources_from_search_results(
                sources,
                args.enrich_from_search,
            )
        output_path = write_source_registry(sources, args.output)
        print(summarize_source_registry(sources))
        if enrichment_notes:
            print("")
            print("Registry enrichment:")
            for note in enrichment_notes:
                print(f"- {note}")
        print("")
        print(f"Wrote registry to: {output_path}")
        return 0

    if args.command == "collect":
        from internship_search.job_collector import (
            collect_from_registry_file,
            summarize_collection,
        )
        from internship_search.registry_enrichment import enrich_sources_from_search_results
        from internship_search.source_registry import (
            load_seed_source_registry,
            read_source_registry,
            write_source_registry,
        )

        if not args.registry.exists():
            sources = load_seed_source_registry(args.private_dir)
            write_source_registry(sources, args.registry)
        elif args.enrich_from_search is not None:
            sources = read_source_registry(args.registry)
            sources, enrichment_notes = enrich_sources_from_search_results(
                sources,
                args.enrich_from_search,
            )
            write_source_registry(sources, args.registry)
            print("Registry enrichment:")
            for note in enrichment_notes:
                print(f"- {note}")
            print("")

        result = collect_from_registry_file(
            registry_path=args.registry,
            output_path=args.output,
            include_job_boards=args.include_job_boards,
            target_year=args.target_year,
        )
        print(summarize_collection(result))
        from internship_search.review_state import append_activity_log
        append_activity_log(
            action="collection",
            subject="internship postings",
            details={
                "postings_collected": len(result.postings),
                "source_errors": len(result.errors),
                "api_invoked": False,
                "cost": {"status": "unavailable"}
            }
        )
        return 0

    if args.command == "search-job-boards":
        from internship_search.job_board_search import (
            get_job_board_provider,
            search_job_boards,
            summarize_job_board_search,
        )

        response = search_job_boards(
            query=args.query,
            target_year=args.target_year,
            provider=get_job_board_provider(),
            max_results=args.max_results,
            output_path=args.output,
        )
        print(summarize_job_board_search(response))
        return 0 if response.postings or not response.errors else 1

    if args.command == "filter-postings":
        from internship_search.posting_filter import (
            filter_postings_file,
            summarize_filter_result,
        )

        result = filter_postings_file(
            input_path=args.input,
            included_output_path=args.included_output,
            excluded_output_path=args.excluded_output,
            registry_path=args.registry,
            monitored_output_path=args.monitored_output,
            collection_errors_path=args.collection_errors,
        )
        print(summarize_filter_result(result))
        return 0

    if args.command == "report":
        from internship_search.review_report import (
            generate_review_report_file,
            summarize_review_report,
        )

        report = generate_review_report_file(
            included_path=args.included,
            excluded_path=args.excluded,
            registry_path=args.registry,
            output_path=args.output,
            monitored_path=args.monitored,
        )
        print(summarize_review_report(report))
        return 0

    if args.command == "score-postings":
        from internship_search.fit_scoring import (
            score_postings_file,
            summarize_score_result,
        )

        result = score_postings_file(
            postings_path=args.postings,
            private_dir=args.private_dir,
            registry_path=args.registry,
            output_path=args.output,
            provider_name=args.provider,
            resume_aware=args.resume_aware or None,
        )
        print(summarize_score_result(result))
        
        from internship_search.review_state import append_activity_log
        is_gemini = (result.provider == "gemini")
        cost_info = {}
        if is_gemini and result.usage:
            cost_info = {
                "amount": 0.0,
                "currency": "USD",
                "basis": f"Gemini API free tier ({result.usage.total_tokens} tokens)"
            }
        else:
            cost_info = {
                "status": "unavailable"
            }
            
        append_activity_log(
            action="scoring",
            subject="internship scoring",
            details={
                "scored_postings": len(result.scored_postings),
                "provider": result.provider,
                "api_invoked": is_gemini,
                "prompt_tokens": result.usage.prompt_tokens if (is_gemini and result.usage) else 0,
                "output_tokens": result.usage.output_tokens if (is_gemini and result.usage) else 0,
                "cost": cost_info
            }
        )
        return 0

    if args.command == "detect-new-postings":
        from internship_search.posting_history import (
            detect_new_postings_file,
            summarize_detection_result,
        )

        result = detect_new_postings_file(
            postings_path=args.postings,
            history_path=args.history,
            changes_output_path=args.changes_output,
            new_output_path=args.new_output,
        )
        print(summarize_detection_result(result))
        return 0

    if args.command == "weekly-email-summary":
        from internship_search.email_summary import (
            generate_weekly_email_summary_file,
            summarize_email_summary,
        )

        result = generate_weekly_email_summary_file(
            scored_path=args.scored,
            new_postings_path=args.new_postings,
            registry_path=args.registry,
            output_path=args.output,
            sent_history_path=args.sent_history,
            collection_errors_path=args.collection_errors,
            recipient=args.recipient,
            send=args.send,
        )
        print(summarize_email_summary(result))
        
        from internship_search.review_state import append_activity_log
        append_activity_log(
            action="email",
            subject="weekly summary email",
            details={
                "recipient": args.recipient,
                "sent": result.email_sent,
                "api_invoked": result.email_sent,
                "cost": {
                    "amount": 0.0 if result.email_sent else None,
                    "currency": "USD" if result.email_sent else None,
                    "basis": "Gmail SMTP (free tier)" if result.email_sent else None,
                    "status": "unavailable" if not result.email_sent else None
                }
            }
        )
        if args.send and not result.email_sent:
            return 1
        return 0

    if args.command == "run-scheduled-collection":
        from internship_search.scheduled_collection import (
            is_scheduled_run_operationally_successful,
            run_scheduled_collection,
            summarize_scheduled_collection,
        )

        result = run_scheduled_collection(
            private_dir=args.private_dir,
            data_dir=args.data_dir,
            generate_email=not args.skip_email,
            send_email=args.send_email,
            resume_aware=args.resume_aware or None,
            include_job_boards=args.include_job_boards,
            target_year=args.target_year,
        )
        print(summarize_scheduled_collection(result))
        return 0 if is_scheduled_run_operationally_successful(result) else 1

    if args.command == "discover-companies":
        from internship_search.company_discovery import (
            discover_companies_file,
            summarize_company_discovery,
        )

        result = discover_companies_file(
            private_dir=args.private_dir,
            registry_path=args.registry,
            output_path=args.output,
            report_path=args.report,
            update_registry=args.update_registry,
            use_internet=not args.no_internet,
        )
        print(summarize_company_discovery(result))
        return 0

    if args.command == "review-ui":
        from internship_search.review_ui import start_review_ui

        start_review_ui(
            host=args.host,
            port=args.port,
            data_dir=args.data_dir,
            private_dir=args.private_dir,
            open_browser=not args.no_open_browser,
        )
        return 0

    if args.command == "internet-search":
        from internship_search.internet_search import (
            get_search_provider,
            search_company_careers,
            search_internet,
            summarize_search_response,
        )

        if not args.query and not args.company:
            parser.error("internet-search requires --query or --company.")

        provider = get_search_provider(args.provider)
        if args.company:
            response = search_company_careers(
                company=args.company,
                target_year=args.target_year,
                provider=provider,
                max_results=args.max_results,
                output_path=args.output,
            )
        else:
            response = search_internet(
                query=args.query,
                provider=provider,
                company="",
                max_results=args.max_results,
                output_path=args.output,
            )
        print(summarize_search_response(response))
        return 0 if response.results else 1

    parser.print_help()
    return 0
