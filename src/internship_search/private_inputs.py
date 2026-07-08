"""Load local private inputs used to guide internship searches."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class PrivateInputError(ValueError):
    """Raised when a required private input file cannot be parsed."""


@dataclass(frozen=True)
class Company:
    name: str
    website: str
    has_connection: bool


@dataclass(frozen=True)
class Preferences:
    likes: list[str]
    dislikes: list[str]


@dataclass(frozen=True)
class Course:
    code: str
    title: str
    category: str


@dataclass(frozen=True)
class ProgramInfo:
    faculty: str | None
    major: str | None
    minor_or_concentration: str | None


@dataclass(frozen=True)
class PrivateInputs:
    companies: list[Company]
    industries: list[str]
    preferences: Preferences
    program: ProgramInfo
    courses: list[Course]
    connections_notes: str
    resume_path: Path | None


def load_private_inputs(private_dir: Path | str = "private") -> PrivateInputs:
    """Load all current private inputs from the local private directory."""

    private_path = Path(private_dir)
    companies, industries = parse_companies_file(
        _read_required_file(private_path / "list_of_companies.md")
    )
    preferences = parse_preferences_file(
        _read_required_file(private_path / "preferences.md")
    )
    program, courses = parse_course_file(
        _read_required_file(private_path / "mcgill_class_list.md")
    )
    connections_notes = _read_optional_file(private_path / "connections.md").strip()
    resume_path = private_path / "Resume - Gabrielle Dar.pdf"

    return PrivateInputs(
        companies=companies,
        industries=industries,
        preferences=preferences,
        program=program,
        courses=courses,
        connections_notes=connections_notes,
        resume_path=resume_path if resume_path.exists() else None,
    )


def parse_companies_file(content: str) -> tuple[list[Company], list[str]]:
    companies: list[Company] = []
    industries: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()

        if _is_markdown_table_row(stripped):
            cells = _split_markdown_table_row(stripped)
            if _is_table_header_or_separator(cells):
                continue
            if len(cells) != 3:
                raise PrivateInputError(
                    "Expected companies table rows to have 3 columns: "
                    "Name, Website, and connection status."
                )
            companies.append(
                Company(
                    name=cells[0],
                    website=cells[1],
                    has_connection=_parse_yes_no(cells[2]),
                )
            )
            continue

        if stripped.startswith("-"):
            industry = stripped.lstrip("-").strip()
            if industry:
                industries.append(industry)

    if not companies:
        raise PrivateInputError("No companies found in private/list_of_companies.md.")

    return companies, industries


def parse_preferences_file(content: str) -> Preferences:
    sections = _parse_markdown_sections(content)
    likes = _parse_list_items(sections.get("things i like", []))
    dislikes = _parse_list_items(sections.get("things i don't like", []))

    if not likes:
        raise PrivateInputError("No likes found in private/preferences.md.")

    return Preferences(likes=likes, dislikes=dislikes)


def parse_course_file(content: str) -> tuple[ProgramInfo, list[Course]]:
    sections = _parse_markdown_sections(content)
    program_lines = sections.get("program", [])

    program = ProgramInfo(
        faculty=_parse_program_field(program_lines, "Faculty/School"),
        major=_parse_program_field(program_lines, "Major"),
        minor_or_concentration=_parse_program_field(
            program_lines,
            "Minor/Concentration",
        ),
    )

    courses: list[Course] = []
    for section, lines in sections.items():
        if section == "program":
            continue
        category = section.title()
        for item in _parse_list_items(lines):
            if ":" not in item:
                continue
            code, title = item.split(":", maxsplit=1)
            courses.append(Course(code=code.strip(), title=title.strip(), category=category))

    if not courses:
        raise PrivateInputError("No courses found in private/mcgill_class_list.md.")

    return program, courses


def summarize_private_inputs(inputs: PrivateInputs) -> str:
    connected_companies = [
        company.name for company in inputs.companies if company.has_connection
    ]

    lines = [
        "Private input summary",
        "=====================",
        f"Companies: {len(inputs.companies)}",
        f"Companies with connections: {len(connected_companies)}",
        f"Industries of interest: {len(inputs.industries)}",
        f"Preference likes: {len(inputs.preferences.likes)}",
        f"Preference dislikes: {len(inputs.preferences.dislikes)}",
        f"Courses: {len(inputs.courses)}",
        f"Connections notes present: {'yes' if inputs.connections_notes else 'no'}",
        f"Resume found: {'yes' if inputs.resume_path else 'no'}",
        "",
        "Companies:",
    ]
    lines.extend(
        f"- {company.name} ({'connection' if company.has_connection else 'no connection'})"
        for company in inputs.companies
    )

    if inputs.industries:
        lines.append("")
        lines.append("Industries:")
        lines.extend(f"- {industry}" for industry in inputs.industries)

    return "\n".join(lines)


def _read_required_file(path: Path) -> str:
    if not path.exists():
        raise PrivateInputError(f"Required private input file is missing: {path}")
    return path.read_text(encoding="utf-8")


def _read_optional_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _parse_markdown_sections(content: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_section: str | None = None

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current_section = stripped.removeprefix("## ").strip().lower()
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(stripped)

    return sections


def _parse_list_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("-"):
            item = stripped.lstrip("-").strip()
        elif "." in stripped and stripped.split(".", maxsplit=1)[0].isdigit():
            item = stripped.split(".", maxsplit=1)[1].strip()
        else:
            continue
        item = item.replace("**", "").strip()
        if item:
            items.append(item)
    return items


def _parse_program_field(lines: list[str], field_name: str) -> str | None:
    prefix = f"{field_name}:"
    for item in _parse_list_items(lines):
        if item.startswith(prefix):
            return item.removeprefix(prefix).strip()
    return None


def _is_markdown_table_row(line: str) -> bool:
    return line.startswith("|") and line.endswith("|")


def _split_markdown_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip("|").split("|")]


def _is_table_header_or_separator(cells: list[str]) -> bool:
    lowered = [cell.lower() for cell in cells]
    return "name" in lowered or all(set(cell) <= {"-"} for cell in cells)


def _parse_yes_no(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "yes":
        return True
    if normalized in {"no", ""}:
        return False
    raise PrivateInputError(f"Expected yes/no connection value, got: {value}")
