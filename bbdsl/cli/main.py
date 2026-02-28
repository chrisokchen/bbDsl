"""CLI entry point for BBDSL."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click


@click.group()
@click.version_option(package_name="bbdsl")
def cli() -> None:
    """BBDSL — Bridge Bidding Description Specification Language."""


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def load(path: Path) -> None:
    """Load and validate a BBDSL YAML file."""
    from bbdsl.core.loader import load_document, print_summary

    try:
        doc = load_document(path)
        print_summary(doc)
    except Exception as e:
        raise click.ClickException(str(e)) from e


@cli.command()
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default="schema/bbdsl-v0.3-generated.json",
    help="Output path for the generated JSON Schema.",
)
def schema(output: Path) -> None:
    """Generate JSON Schema from Pydantic models."""
    from bbdsl.core.loader import generate_json_schema

    generate_json_schema(output)
    click.echo(f"JSON Schema written to {output}")


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output expanded JSON.")
def expand(path: Path, output: Path | None) -> None:
    """Expand foreach_suit directives in a BBDSL YAML file."""
    from bbdsl.core.expander import count_expanded, expand_document
    from bbdsl.core.loader import load_document

    try:
        doc = load_document(path)
        expanded = expand_document(doc)
        n = count_expanded(expanded)
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(expanded, f, indent=2, ensure_ascii=False)
            click.echo(f"Expanded {n} node(s) → {output}")
        else:
            click.echo(f"Expanded {n} node(s) from foreach_suit.")
    except Exception as e:
        raise click.ClickException(str(e)) from e


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--rules", "-r", default=None, help="Comma-separated rule IDs to run.")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output JSON report.")
def validate(path: Path, rules: str | None, output: Path | None) -> None:
    """Validate a BBDSL document against semantic rules."""
    from bbdsl.core.loader import load_document
    from bbdsl.core.validator import Validator

    try:
        doc = load_document(path)
    except Exception as e:
        raise click.ClickException(str(e)) from e

    rule_ids = [r.strip() for r in rules.split(",")] if rules else None
    validator = Validator(doc)
    report = validator.validate_all(rule_ids)

    for result in report.results:
        if not result.passed and result.severity == "error":
            click.secho(f"  {result.rule_id} {result.rule_name}: {result.message}", fg="red")
            for d in result.details:
                click.secho(f"    {d}", fg="red")
        elif not result.passed and result.severity == "warning":
            click.secho(f"  {result.rule_id} {result.rule_name}: {result.message}", fg="yellow")
            for d in result.details:
                click.secho(f"    {d}", fg="yellow")
        else:
            click.secho(f"  {result.rule_id} {result.rule_name}: PASSED", fg="green")

    passed = sum(1 for r in report.results if r.passed)
    total = len(report.results)
    click.echo(f"\nSummary: {passed}/{total} passed, "
               f"{report.warning_count} warning(s), {report.error_count} error(s)")

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, indent=2, ensure_ascii=False)

    if report.has_errors():
        sys.exit(2)
    elif report.warning_count > 0:
        sys.exit(1)


@cli.group("export")
def export_group() -> None:
    """Export a BBDSL document to another format."""


@export_group.command("bboalert")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output .bboalert file.")
@click.option("--locale", "-l", default="en", show_default=True,
              help="Language for descriptions (en or zh-TW).")
@click.option("--no-comments", is_flag=True, default=False,
              help="Omit header comments from output.")
def export_bboalert(path: Path, output: Path | None, locale: str, no_comments: bool) -> None:
    """Export a BBDSL YAML file to BBOalert CSV format."""
    from bbdsl.core.loader import load_document
    from bbdsl.exporters.bboalert_exporter import export_bboalert as _export

    try:
        doc = load_document(path)
        rows = _export(doc, output_path=output, locale=locale,
                       include_comments=not no_comments)
    except Exception as e:
        raise click.ClickException(str(e)) from e

    if output:
        click.secho(f"Exported {len(rows)} row(s) → {output}", fg="green")
    else:
        # Print to stdout
        import csv
        import io
        buf = io.StringIO()
        writer = csv.writer(buf)
        for row in rows:
            writer.writerow(list(row))
        click.echo(buf.getvalue(), nl=False)


@export_group.command("bml")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output .bml file.")
@click.option("--locale", "-l", default="en", show_default=True,
              help="Language for descriptions (en or zh-TW).")
@click.option("--suit-symbols", is_flag=True, default=False,
              help="Use ♠♥♦♣ symbols instead of suit names.")
@click.option("--no-comments", is_flag=True, default=False,
              help="Omit header comments from output.")
def export_bml_cmd(
    path: Path, output: Path | None, locale: str,
    suit_symbols: bool, no_comments: bool,
) -> None:
    """Export a BBDSL YAML file to BML (Bridge Markup Language) format."""
    from bbdsl.core.loader import load_document
    from bbdsl.exporters.bml_exporter import export_bml as _export

    try:
        doc = load_document(path)
        text = _export(
            doc,
            output_path=output,
            locale=locale,
            suit_symbols=suit_symbols,
            include_comments=not no_comments,
        )
    except Exception as e:
        raise click.ClickException(str(e)) from e

    if output:
        click.secho(f"Exported BML → {output}", fg="green")
    else:
        click.echo(text, nl=False)


@export_group.command("html")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output .html file.")
@click.option("--locale", "-l", default="en", show_default=True,
              help="Language for descriptions (en or zh-TW).")
@click.option("--suit-symbols", is_flag=True, default=False,
              help="Use ♠♥♦♣ symbols instead of suit names.")
@click.option("--title", default=None, help="Override page title.")
def export_html_cmd(
    path: Path, output: Path | None, locale: str,
    suit_symbols: bool, title: str | None,
) -> None:
    """Export a BBDSL YAML file to interactive HTML viewer."""
    from bbdsl.core.loader import load_document
    from bbdsl.exporters.html_exporter import export_html as _export

    try:
        doc = load_document(path)
        html = _export(
            doc,
            output_path=output,
            locale=locale,
            suit_symbols=suit_symbols,
            title=title,
        )
    except Exception as e:
        raise click.ClickException(str(e)) from e

    if output:
        click.secho(f"Exported HTML viewer → {output}", fg="green")
    else:
        click.echo(html, nl=False)


@export_group.command("convcard")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output .html file.")
@click.option("--locale", "-l", default="en", show_default=True,
              help="Language for descriptions (en or zh-TW).")
@click.option("--style", default="wbf", show_default=True,
              type=click.Choice(["wbf", "acbl"]),
              help="Convention card style (wbf or acbl).")
@click.option("--title", default=None, help="Override page title.")
def export_convcard_cmd(
    path: Path, output: Path | None, locale: str,
    style: str, title: str | None,
) -> None:
    """Export a BBDSL YAML file to printable Convention Card HTML."""
    from bbdsl.core.loader import load_document
    from bbdsl.exporters.convcard_exporter import export_convcard as _export

    try:
        doc = load_document(path)
        html = _export(
            doc,
            output_path=output,
            locale=locale,
            style=style,
            title=title,
        )
    except Exception as e:
        raise click.ClickException(str(e)) from e

    if output:
        click.secho(f"Exported Convention Card → {output}", fg="green")
    else:
        click.echo(html, nl=False)


@export_group.command("svg")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output .svg file.")
@click.option("--locale", "-l", default="en", show_default=True,
              help="Language for descriptions (en or zh-TW).")
@click.option("--suit-symbols", is_flag=True, default=False,
              help="Use ♠♥♦♣ symbols in node descriptions.")
@click.option("--max-depth", default=2, show_default=True, type=int,
              help="Maximum tree depth (0=openings only, 1=+responses).")
def export_svg_cmd(
    path: Path, output: Path | None, locale: str,
    suit_symbols: bool, max_depth: int,
) -> None:
    """Export a BBDSL YAML file to SVG bidding tree diagram."""
    from bbdsl.core.loader import load_document
    from bbdsl.exporters.svg_tree import export_svg as _export

    try:
        doc = load_document(path)
        svg = _export(
            doc,
            output_path=output,
            locale=locale,
            suit_symbols=suit_symbols,
            max_depth=max_depth,
        )
    except Exception as e:
        raise click.ClickException(str(e)) from e

    if output:
        click.secho(f"Exported SVG tree → {output}", fg="green")
    else:
        click.echo(svg, nl=False)


@export_group.command("ai-kb")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output .json or .jsonl file.")
@click.option("--format", "-f", "fmt", default="jsonl", show_default=True,
              type=click.Choice(["json", "jsonl"]),
              help="Output format: jsonl (one record per line) or json (array).")
@click.option("--locale", "-l", default="en", show_default=True,
              help="Language for descriptions (en or zh-TW).")
@click.option("--suit-symbols", is_flag=True, default=False,
              help="Use ♠♥♦♣ symbols in descriptions.")
@click.option("--no-conventions", is_flag=True, default=False,
              help="Exclude convention rules from output.")
def export_ai_kb_cmd(
    path: Path, output: Path | None, fmt: str, locale: str,
    suit_symbols: bool, no_conventions: bool,
) -> None:
    """Export a BBDSL YAML file to AI knowledge base (JSON/JSONL for RAG)."""
    from bbdsl.core.loader import load_document
    from bbdsl.exporters.ai_kb_exporter import export_ai_kb as _export, _to_json, _to_jsonl, _system_name

    try:
        doc = load_document(path)
        rules = _export(
            doc,
            output_path=output,
            fmt=fmt,
            locale=locale,
            suit_symbols=suit_symbols,
            include_conventions=not no_conventions,
        )
    except Exception as e:
        raise click.ClickException(str(e)) from e

    if output:
        click.secho(f"Exported {len(rules)} rule(s) → {output}", fg="green")
    else:
        sname = _system_name(doc, locale)
        if fmt == "jsonl":
            click.echo(_to_jsonl(rules), nl=False)
        else:
            click.echo(_to_json(rules, sname, locale), nl=False)


@export_group.command("dealer")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output .dds Dealer script file.")
@click.option("--seat", default="south", show_default=True,
              help="Dealer seat name for conditions.")
@click.option("--locale", "-l", default="en", show_default=True,
              help="Language for comments (en or zh-TW).")
def export_dealer_cmd(
    path: Path, output: Path | None, seat: str, locale: str,
) -> None:
    """Export opening constraints as a Dealer script (.dds)."""
    from bbdsl.core.loader import load_document
    from bbdsl.core.dealer_bridge import openings_to_dealer_script

    try:
        doc = load_document(path)
        script = openings_to_dealer_script(doc, seat=seat, locale=locale)
    except Exception as e:
        raise click.ClickException(str(e)) from e

    if output:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(script, encoding="utf-8")
        openings_count = len(doc.openings or [])
        click.secho(f"Exported {openings_count} opening(s) as Dealer script → {output}", fg="green")
    else:
        click.echo(script, nl=False)


@export_group.command("pbn")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output .pbn file.")
@click.option("--deals", "-n", default=10, show_default=True, type=int,
              help="Number of deals to simulate.")
@click.option("--seed", default=None, type=int, help="Random seed.")
@click.option("--dealer", default="N", show_default=True,
              type=click.Choice(["N", "E", "S", "W"]),
              help="Starting dealer seat.")
@click.option("--locale", "-l", default="en", show_default=True,
              help="Language for system name.")
def export_pbn_cmd(
    path: Path,
    output: Path | None,
    deals: int,
    seed: int | None,
    dealer: str,
    locale: str,
) -> None:
    """Export simulated deals as PBN (Portable Bridge Notation)."""
    from bbdsl.core.loader import load_document
    from bbdsl.exporters.pbn_exporter import export_pbn as _export

    try:
        doc = load_document(path)
        pbn_text = _export(
            doc,
            output_path=output,
            n_deals=deals,
            seed=seed,
            dealer=dealer,
            locale=locale,
        )
    except Exception as e:
        raise click.ClickException(str(e)) from e

    if output:
        click.secho(f"Exported {deals} deal(s) as PBN → {output}", fg="green")
    else:
        click.echo(pbn_text, nl=False)


@cli.command("quiz")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output .html file.")
@click.option("--locale", "-l", default="en", show_default=True,
              help="Language (en or zh-TW).")
@click.option("--n", "-n", "n_questions", default=20, show_default=True, type=int,
              help="Number of quiz questions.")
@click.option("--types", default="opening,response", show_default=True,
              help="Question types: comma-separated 'opening' and/or 'response'.")
@click.option("--seed", default=None, type=int, help="Random seed for reproducibility.")
@click.option("--title", default=None, help="Override page title.")
def quiz_cmd(
    path: Path,
    output: Path | None,
    locale: str,
    n_questions: int,
    types: str,
    seed: int | None,
    title: str | None,
) -> None:
    """Generate an interactive HTML bidding quiz from a BBDSL YAML file."""
    from bbdsl.core.loader import load_document
    from bbdsl.exporters.quiz_exporter import export_quiz as _export

    try:
        doc = load_document(path)
        question_types = [t.strip() for t in types.split(",")]
        html = _export(
            doc,
            output_path=output,
            n=n_questions,
            question_types=question_types,
            locale=locale,
            title=title,
            seed=seed,
        )
    except Exception as e:
        raise click.ClickException(str(e)) from e

    if output:
        click.secho(f"Quiz ({n_questions} questions) → {output}", fg="green")
    else:
        click.echo(html, nl=False)


@cli.command("simulate")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--deals", "-n", default=10, show_default=True, type=int,
              help="Number of deals to simulate.")
@click.option("--output", "-o", type=click.Path(path_type=Path),
              help="Output .json file for full results.")
@click.option("--ew-system", "ew_system", type=click.Path(exists=True, path_type=Path),
              default=None, help="BBDSL YAML file for E/W bidding system.")
@click.option("--dealer", default="N", show_default=True,
              type=click.Choice(["N", "E", "S", "W"]),
              help="Starting dealer seat.")
@click.option("--seed", default=None, type=int, help="Random seed for reproducibility.")
def simulate_cmd(
    path: Path,
    deals: int,
    output: Path | None,
    ew_system: Path | None,
    dealer: str,
    seed: int | None,
) -> None:
    """Simulate bridge bidding auctions using a BBDSL system."""
    from bbdsl.core.loader import load_document
    from bbdsl.core.sim_engine import simulate as _simulate

    try:
        ns_doc = load_document(path)
        ew_doc = load_document(ew_system) if ew_system else None
        results = _simulate(ns_doc, n_deals=deals, ew_doc=ew_doc, dealer=dealer, seed=seed)
    except Exception as e:
        raise click.ClickException(str(e)) from e

    # Print summary to stdout
    for r in results:
        auction_str = " ".join(f"{s.seat}:{s.bid}" for s in r.auction)
        if r.passed_out:
            click.echo(f"Deal {r.deal_number}: (Passed out)")
        else:
            click.echo(f"Deal {r.deal_number}: Auction: {auction_str} → {r.final_contract}")

    # Optionally write full JSON output
    if output:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        data = [r.to_dict() for r in results]
        output.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        click.secho(f"Results ({len(results)} deals) → {output}", fg="green")


@cli.command("compare")
@click.argument("path_a", type=click.Path(exists=True, path_type=Path))
@click.argument("path_b", type=click.Path(exists=True, path_type=Path))
@click.option("--deals", "-n", default=50, show_default=True, type=int,
              help="Number of deals to simulate.")
@click.option("--output", "-o", type=click.Path(path_type=Path),
              help="Output .json file for full report.")
@click.option("--seed", default=None, type=int, help="Random seed.")
@click.option("--locale", "-l", default="en", show_default=True,
              help="Language for system names (en or zh-TW).")
@click.option("--dealer", default="N", show_default=True,
              type=click.Choice(["N", "E", "S", "W"]),
              help="Starting dealer seat.")
def compare_cmd(
    path_a: Path,
    path_b: Path,
    deals: int,
    output: Path | None,
    seed: int | None,
    locale: str,
    dealer: str,
) -> None:
    """Compare two BBDSL bidding systems on the same random deals."""
    from bbdsl.core.loader import load_document
    from bbdsl.core.comparator import compare_systems as _compare

    try:
        doc_a = load_document(path_a)
        doc_b = load_document(path_b)
        report = _compare(doc_a, doc_b, n_deals=deals, seed=seed, locale=locale, dealer=dealer)
    except Exception as e:
        raise click.ClickException(str(e)) from e

    click.echo(report.summary_text(locale=locale))

    # Show a sample of diff cases
    if report.diff_cases:
        click.echo("\nSample differences (first 5):")
        for dc in report.diff_cases[:5]:
            click.echo(
                f"  Deal {dc.deal_number}: "
                f"{report.system_a}→{dc.contract_a or 'Pass'}  "
                f"{report.system_b}→{dc.contract_b or 'Pass'}"
            )

    if output:
        import json as _json
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            _json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        click.secho(f"Report → {output}", fg="green")


@cli.command("select")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--hcp", type=int, default=None, help="Hand HCP.")
@click.option("--hearts", type=int, default=0, help="Heart suit length.")
@click.option("--spades", type=int, default=0, help="Spade suit length.")
@click.option("--diamonds", type=int, default=0, help="Diamond suit length.")
@click.option("--clubs", type=int, default=0, help="Club suit length.")
@click.option("--controls", type=int, default=0, help="Control count.")
@click.option("--shape", default=None, help="Shape category (balanced/semi_balanced).")
def select_cmd(
    path: Path,
    hcp: int | None,
    hearts: int,
    spades: int,
    diamonds: int,
    clubs: int,
    controls: int,
    shape: str | None,
) -> None:
    """Select an opening bid using selection_rules for a given hand description."""
    from bbdsl.core.loader import load_document
    from bbdsl.core.selector import select_opening

    try:
        doc = load_document(path)
    except Exception as e:
        raise click.ClickException(str(e)) from e

    if not doc.selection_rules:
        raise click.ClickException("Document has no selection_rules defined.")

    hand = {
        "hcp": hcp or 0,
        "hearts": hearts,
        "spades": spades,
        "diamonds": diamonds,
        "clubs": clubs,
        "controls": controls,
    }
    if shape:
        hand["shape"] = shape

    result = select_opening(hand, doc.selection_rules)
    if result:
        click.secho(f"Selected opening: {result}", fg="green")
    else:
        click.secho("No opening selected (no matching rule).", fg="yellow")
        sys.exit(1)


@cli.group("import")
def import_group() -> None:
    """Import a bidding system from another format."""


@import_group.command("bml")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--name", "-n", default=None, help="System name (default: derived from filename).")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output BBDSL YAML path.")
def import_bml(path: Path, name: str | None, output: Path | None) -> None:
    """Import a BML (Bridge Markup Language) file to BBDSL YAML."""
    from bbdsl.importers.bml_importer import import_bml as _import_bml

    try:
        doc, n_unresolved = _import_bml(path, system_name=name, output_path=output)
    except Exception as e:
        raise click.ClickException(str(e)) from e

    n_openings = len(doc.get("openings", []))
    if output:
        click.secho(f"Imported {n_openings} opening(s) → {output}", fg="green")
    else:
        click.echo(f"Imported {n_openings} opening(s) from {path.name}")

    if n_unresolved:
        click.secho(
            f"  {n_unresolved} UnresolvedNode(s) need manual fixing "
            f"(search for 'is_unresolved: true' in output).",
            fg="yellow",
        )
    else:
        click.secho("  All nodes resolved successfully.", fg="green")

    if n_unresolved:
        sys.exit(1)  # Unresolved nodes → warning exit


@import_group.command("bboalert")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--name", "-n", default=None, help="System name.")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output BBDSL YAML path.")
def import_bboalert_cmd(path: Path, name: str | None, output: Path | None) -> None:
    """Import a BBOalert CSV file to BBDSL YAML."""
    from bbdsl.importers.bboalert_importer import import_bboalert as _import

    try:
        doc, n_unresolved = _import(path, system_name=name, output_path=output)
    except Exception as e:
        raise click.ClickException(str(e)) from e

    n_openings = len(doc.get("openings", []))
    if output:
        click.secho(f"Imported {n_openings} opening(s) → {output}", fg="green")
    else:
        click.echo(f"Imported {n_openings} opening(s) from {path.name}")

    if n_unresolved:
        click.secho(
            f"  {n_unresolved} UnresolvedNode(s) need manual fixing.",
            fg="yellow",
        )
    else:
        click.secho("  All nodes resolved successfully.", fg="green")

    if n_unresolved:
        sys.exit(1)


# ────────────────────── Registry Commands (5.1.7) ──────────────────────


@cli.group("registry")
@click.option(
    "--api-url",
    envvar="BBDSL_API_URL",
    default="http://localhost:8000/api/v1",
    show_default=True,
    help="Platform API base URL.",
)
@click.option(
    "--token",
    envvar="BBDSL_API_TOKEN",
    default=None,
    help="API bearer token (or set BBDSL_API_TOKEN env var).",
)
@click.pass_context
def registry_group(ctx: click.Context, api_url: str, token: str | None) -> None:
    """Interact with the BBDSL Platform Convention Registry."""
    from bbdsl.cli.registry_client import RegistryClient

    ctx.ensure_object(dict)
    ctx.obj["client"] = RegistryClient(api_url=api_url, token=token)


@registry_group.command("publish")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--name", "-n", required=True, help="Convention display name.")
@click.option("--namespace", "-ns", required=True,
              help="Namespace ID (e.g. 'precision', 'sayc').")
@click.option("--version", "-v", default="1.0.0", show_default=True,
              help="SemVer version string.")
@click.option("--description", "-d", default=None,
              help="Short description of the convention.")
@click.option("--tags", "-t", default=None,
              help="Comma-separated tags (e.g. 'natural,2/1,gf').")
@click.pass_context
def registry_publish(
    ctx: click.Context,
    path: Path,
    name: str,
    namespace: str,
    version: str,
    description: str | None,
    tags: str | None,
) -> None:
    """Publish a BBDSL YAML file to the Convention Registry.

    The server validates the YAML automatically; invalid files
    are rejected.
    """
    from bbdsl.cli.registry_client import RegistryError

    yaml_content = path.read_text(encoding="utf-8")
    client = ctx.obj["client"]

    try:
        result = client.publish(
            name=name,
            namespace=namespace,
            version=version,
            yaml_content=yaml_content,
            description=description,
            tags=tags,
        )
    except RegistryError as e:
        raise click.ClickException(str(e)) from e

    click.secho(
        f"✅ Published '{result['name']}' "
        f"({result['namespace']} v{result['version']}) "
        f"— ID {result['id']}",
        fg="green",
    )


@registry_group.command("search")
@click.option("--query", "-q", default=None,
              help="Search by name or namespace.")
@click.option("--tag", default=None,
              help="Filter by tag.")
@click.option("--namespace", "-ns", default=None,
              help="Filter by exact namespace.")
@click.option("--author", default=None,
              help="Filter by author name.")
@click.option("--sort", default="newest", show_default=True,
              type=click.Choice(["newest", "oldest", "downloads", "name"]),
              help="Sort order.")
@click.option("--page", default=1, show_default=True, type=int)
@click.option("--page-size", default=20, show_default=True, type=int)
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Output raw JSON instead of formatted table.")
@click.pass_context
def registry_search(
    ctx: click.Context,
    query: str | None,
    tag: str | None,
    namespace: str | None,
    author: str | None,
    sort: str,
    page: int,
    page_size: int,
    as_json: bool,
) -> None:
    """Search the Convention Registry."""
    from bbdsl.cli.registry_client import RegistryError

    client = ctx.obj["client"]

    try:
        data = client.search(
            query=query,
            tag=tag,
            namespace=namespace,
            author=author,
            sort=sort,
            page=page,
            page_size=page_size,
        )
    except RegistryError as e:
        raise click.ClickException(str(e)) from e

    if as_json:
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return

    items = data.get("items", [])
    total = data.get("total", 0)

    if not items:
        click.secho("No conventions found.", fg="yellow")
        return

    click.echo(
        f"Found {total} convention(s) "
        f"(page {data.get('page', 1)}/{max(1, -(-total // page_size))}):\n"
    )
    for item in items:
        name_str = click.style(item["name"], fg="cyan", bold=True)
        ns_str = f"{item['namespace']} v{item['version']}"
        dl_str = f"{item['downloads']} downloads"
        click.echo(f"  {name_str}  ({ns_str})  [{dl_str}]")
        if item.get("description"):
            click.echo(f"    {item['description']}")
        if item.get("tags"):
            click.echo(
                f"    tags: {item['tags']}"
            )
        click.echo(f"    by {item['author_name']}  "
                    f"({item['created_at'][:10]})")
        click.echo()


@registry_group.command("install")
@click.argument("namespace")
@click.option("--version", "-v", default=None,
              help="Specific version (default: latest).")
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output YAML file path (default: <namespace>.bbdsl.yaml).",
)
@click.pass_context
def registry_install(
    ctx: click.Context,
    namespace: str,
    version: str | None,
    output: Path | None,
) -> None:
    """Download a convention from the Registry by namespace.

    If --version is omitted the latest version is fetched.
    The YAML content is saved to a local file.
    """
    from bbdsl.cli.registry_client import RegistryError

    client = ctx.obj["client"]

    try:
        data = client.install(namespace, version=version)
    except RegistryError as e:
        raise click.ClickException(str(e)) from e

    # Determine output path
    if output is None:
        safe_ns = namespace.replace("/", "_")
        output = Path(f"{safe_ns}.bbdsl.yaml")

    yaml_content = data.get("yaml_content", "")
    if not yaml_content:
        raise click.ClickException(
            "Server returned empty YAML content."
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml_content, encoding="utf-8")

    click.secho(
        f"✅ Installed '{data.get('name', namespace)}' "
        f"v{data.get('version', '?')} → {output}",
        fg="green",
    )
