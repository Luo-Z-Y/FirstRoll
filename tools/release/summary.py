"""Human-readable approval summary generation.

Transforms a structured ``ReleaseManifest`` into a clear, human-centred
approval summary.  The primary view answers:

  What am I releasing?
  What will users notice?
  What is the risk?
  Did the required checks pass?
  Is there a database migration?
  Is there an infrastructure change?
  Will there be downtime?
  What happens after I approve?
  How do I undo it?

Raw technical identifiers are placed in an expandable details section and
never appear in the primary summary.
"""

from __future__ import annotations

from tools.release.manifest import ReleaseManifest


def _check_icon(passed: bool | None) -> str:
    if passed is True:
        return "✅"
    if passed is False:
        return "❌"
    return "⚠️  Not configured"


def _risk_icon(level: str) -> str:
    icons = {"low": "🟢", "medium": "🟡", "high": "🔴", "blocked": "🚫"}
    return icons.get(level, "⚪")


def _field_or_unavailable(value: str | None) -> str:
    return value if value else "unavailable"


def generate_approval_summary(manifest: ReleaseManifest) -> str:
    """Generate the primary human-readable approval summary."""
    cs = manifest.change_summary
    v = manifest.verification
    pr = manifest.pull_request

    pr_line = ""
    if pr:
        pr_line = f"PR #{pr.number} — {pr.title}"
    else:
        pr_line = cs.release_title

    # Primary summary
    lines: list[str] = []
    lines.append("# FirstRoll backend release is ready")
    lines.append("")
    lines.append("## Release")
    lines.append(pr_line)
    lines.append("")

    # What will change
    lines.append("## What will change")
    if cs.user_visible_changes:
        for change in cs.user_visible_changes:
            lines.append(f"- {change}")
    else:
        lines.append("- Backend service update (no user-visible behaviour change documented).")
    lines.append("- The frontend is unchanged.")
    lines.append("")

    # Expected user impact
    lines.append("## Expected user impact")
    if cs.expected_downtime == "none":
        lines.append("- No planned downtime.")
    else:
        lines.append(f"- Expected downtime: {cs.expected_downtime}")

    if cs.expected_impact:
        for impact in cs.expected_impact:
            lines.append(f"- {impact}")
    else:
        lines.append("- Existing accounts and data are unaffected.")

    if cs.database_migration:
        lines.append(f"- ⚠️  Database migration included ({len(cs.migration_files)} file(s)).")
    else:
        lines.append("- No database migration is included.")
    lines.append("")

    # Safety checks
    lines.append("## Safety checks")
    lines.append(f"- {_check_icon(v.ci_passed)} Automated tests passed.")
    lines.append(f"- {_check_icon(v.container_tests_passed)} Container startup test passed.")
    if v.scan_passed is not None:
        lines.append(
            f"- {_check_icon(v.scan_passed)} "
            f"{'No blocking vulnerabilities found.' if v.scan_passed else 'Security scan reported issues.'}"
        )
    else:
        lines.append("- ⚠️  Security scanner not configured.")
    if v.sbom_generated is not None:
        lines.append(
            f"- {_check_icon(v.sbom_generated)} SBOM {'generated' if v.sbom_generated else 'not generated'}."
        )
    if v.terraform_plan_available is not None:
        lines.append(
            f"- {_check_icon(v.terraform_plan_available)} "
            f"Terraform plan {'reviewed' if v.terraform_plan_available else 'not available'}."
        )
    lines.append(f"- Deployment plan changes {cs.infrastructure_change}.")
    lines.append("")

    # Risk
    lines.append("## Risk")
    lines.append(f"{_risk_icon(cs.risk_level)} **{cs.risk_level.capitalize()}**")
    lines.append("")
    if cs.risk_reasons:
        lines.append("### Why")
        for reason in cs.risk_reasons:
            lines.append(f"- {reason}")
    else:
        lines.append(
            "This release changes backend behaviour without modifying "
            "authentication, billing, database schemas, or cloud permissions."
        )
    lines.append("")

    # Rollback
    lines.append("## Rollback")
    lines.append(cs.rollback_summary)
    lines.append("")

    # After approval
    lines.append("## After approval")
    lines.append("- Deploy the prepared backend image.")
    lines.append("- Wait for Container Apps readiness.")
    lines.append("- Check the health endpoint.")
    lines.append("- Verify representative API behaviour.")
    lines.append("- Verify CORS for firstroll.app.")
    lines.append("- Verify the expected release identity.")
    lines.append("- Report the result.")
    lines.append("")

    return "\n".join(lines)


def generate_technical_details(manifest: ReleaseManifest) -> str:
    """Generate the expandable technical details section."""
    pr = manifest.pull_request
    c = manifest.candidate
    cp = manifest.current_production

    lines: list[str] = []
    lines.append("## Technical details")
    lines.append("")
    lines.append(f"| Field | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Environment | `{manifest.environment}` |")
    lines.append(f"| Repository | `{manifest.repository}` |")

    if pr:
        lines.append(f"| Pull request | #{pr.number} — {pr.title} |")
    else:
        lines.append("| Pull request | unavailable |")

    lines.append(f"| Workflow run ID | `{manifest.workflow_run_id}` |")
    lines.append(f"| Full commit SHA | `{manifest.commit_sha}` |")
    lines.append(f"| Source branch | `{manifest.branch}` |")
    lines.append(f"| Candidate image repository | `{c.image_repository}` |")
    lines.append(f"| Candidate image digest | `{c.image_digest}` |")
    lines.append(f"| Candidate artefact digest | `{c.artifact_digest}` |")
    lines.append(
        f"| Current production image digest | `{_field_or_unavailable(cp.image_digest)}` |"
    )
    lines.append(f"| Current production revision | `{_field_or_unavailable(cp.revision)}` |")
    lines.append(f"| Rollback revision | `{_field_or_unavailable(cp.revision)}` |")
    lines.append(f"| CI result | `{'passed' if manifest.verification.ci_passed else 'FAILED'}` |")

    scan_status = "not configured"
    if manifest.verification.scan_passed is True:
        scan_status = "passed"
    elif manifest.verification.scan_passed is False:
        scan_status = "FAILED"
    lines.append(f"| Container scan result | `{scan_status}` |")

    sbom_status = "not configured"
    if manifest.verification.sbom_generated is True:
        sbom_status = "generated"
    elif manifest.verification.sbom_generated is False:
        sbom_status = "not generated"
    lines.append(f"| SBOM status | `{sbom_status}` |")

    tf_status = "not applicable"
    if manifest.verification.terraform_plan_available is True:
        tf_status = "plan available"
    elif manifest.verification.terraform_plan_available is False:
        tf_status = "plan not available"
    lines.append(f"| Terraform plan | `{tf_status}` |")

    lines.append(f"| Candidate creation time | `{c.created_at}` |")
    lines.append("")

    # Migration details
    if manifest.change_summary.migration_files:
        lines.append("### Migration files")
        for mf in manifest.change_summary.migration_files:
            lines.append(f"- `{mf}`")
        lines.append("")

    # Terraform change details
    if manifest.change_summary.terraform_changed_files:
        lines.append("### Terraform changes")
        for tf in manifest.change_summary.terraform_changed_files:
            lines.append(f"- `{tf}`")
        lines.append("")

    return "\n".join(lines)


def generate_full_approval_view(manifest: ReleaseManifest) -> str:
    """Generate the complete approval view with primary summary and details."""
    primary = generate_approval_summary(manifest)
    details = generate_technical_details(manifest)

    return f"{primary}\n<details>\n<summary>View technical details</summary>\n\n{details}\n</details>\n"
