from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree


IGNORED_DIRS = {".git", ".github", "artifacts", "bin", "obj"}
COPY_EXCLUDE_DIRS = {"obj", "ref", "refs"}


def parse_args() -> argparse.Namespace:
    script_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Discover and compile .NET projects stored in this repository."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=script_root,
        help="Repository root that contains the tools directory.",
    )
    parser.add_argument(
        "--projects-dir",
        default="tools",
        help="Directory under the repository root that contains project sources.",
    )
    parser.add_argument(
        "--configuration",
        default="Release",
        help="Build configuration to compile.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=script_root / "artifacts",
        help="Directory where compiled outputs will be copied.",
    )
    parser.add_argument(
        "--framework-version",
        help="Optional .NET Framework version (for example 4.0, 4.5 or 4.7).",
    )
    parser.add_argument(
        "--framework-moniker",
        help="Optional target framework moniker passed to SDK-style builds (for example net40).",
    )
    parser.add_argument(
        "--platform",
        default="Any",
        help="Display platform name used in build metadata.",
    )
    parser.add_argument(
        "--platform-target",
        default="AnyCPU",
        help="PlatformTarget property value passed to MSBuild or dotnet build.",
    )
    parser.add_argument(
        "--msbuild-platform",
        default="Any CPU",
        help="Platform property value passed to MSBuild or dotnet build.",
    )
    parser.add_argument(
        "--branch-name",
        help="Optional branch name to record in the generated build result metadata.",
    )
    parser.add_argument(
        "--branch-display-name",
        help="Optional human-readable branch label to record in the generated build result metadata.",
    )
    parser.add_argument(
        "--tools-metadata",
        type=Path,
        help="Optional JSON file describing configured source repositories and upstream revisions.",
    )
    parser.add_argument(
        "--result-json",
        type=Path,
        help="Optional JSON file to write build results into.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue building remaining targets when one target fails.",
    )
    return parser.parse_args()


def iter_candidates(base_dir: Path, suffix: str) -> list[Path]:
    if not base_dir.exists():
        return []

    return sorted(
        path
        for path in base_dir.rglob(f"*{suffix}")
        if not any(part in IGNORED_DIRS for part in path.parts)
    )


def discover_build_targets(base_dir: Path) -> list[Path]:
    solutions = list(iter_candidates(base_dir, ".sln"))
    solution_dirs = [solution.parent for solution in solutions]

    standalone_projects = [
        project
        for project in iter_candidates(base_dir, ".csproj")
        if not any(
            project.parent == solution_dir or solution_dir in project.parent.parents
            for solution_dir in solution_dirs
        )
    ]

    return solutions + standalone_projects


def is_sdk_style_project(project_file: Path) -> bool:
    try:
        root = ElementTree.parse(project_file).getroot()
    except ElementTree.ParseError:
        return False

    if root.attrib.get("Sdk"):
        return True

    return any(
        element.tag.endswith("TargetFramework") or element.tag.endswith("TargetFrameworks")
        for element in root.iter()
    )


def resolve_builder(target: Path) -> list[str]:
    if target.suffix == ".sln":
        if os.name == "nt" and shutil.which("msbuild"):
            return ["msbuild", str(target)]
        return ["dotnet", "build", str(target)]

    if is_sdk_style_project(target):
        return ["dotnet", "build", str(target)]

    if os.name == "nt" and shutil.which("msbuild"):
        return ["msbuild", str(target)]

    raise RuntimeError(
        f"{target} looks like a classic .NET Framework project and requires Windows MSBuild."
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_tools_metadata(metadata_path: Path | None) -> list[dict[str, object]]:
    if not metadata_path:
        return []

    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    tools = data.get("tools", [])
    if not isinstance(tools, list):
        raise ValueError("tools metadata file must contain a top-level 'tools' list")
    return tools


def append_target_properties(
    command: list[str],
    *,
    framework_version: str | None,
    framework_moniker: str | None,
    platform_target: str,
    msbuild_platform: str,
) -> None:
    if command[0] == "dotnet":
        if framework_moniker:
            command.append(f"-p:TargetFramework={framework_moniker}")
        if msbuild_platform:
            command.append(f"-p:Platform={msbuild_platform}")
        if platform_target:
            command.append(f"-p:PlatformTarget={platform_target}")
        return

    if framework_version:
        command.append(f"/p:TargetFrameworkVersion=v{framework_version}")
    if msbuild_platform:
        command.append(f"/p:Platform={msbuild_platform}")
    if platform_target:
        command.append(f"/p:PlatformTarget={platform_target}")


def build_target(
    target: Path,
    configuration: str,
    *,
    framework_version: str | None,
    framework_moniker: str | None,
    platform_target: str,
    msbuild_platform: str,
) -> None:
    command = resolve_builder(target)

    if command[0] == "dotnet":
        command.extend(["-c", configuration, "--nologo"])
    else:
        command.extend(
            [
                "/restore",
                "/nologo",
                f"/p:Configuration={configuration}",
                "/p:RestorePackagesConfig=true",
            ]
        )

    append_target_properties(
        command,
        framework_version=framework_version,
        framework_moniker=framework_moniker,
        platform_target=platform_target,
        msbuild_platform=msbuild_platform,
    )

    print(f"::group::Building {target}")
    print("Running:", " ".join(command))
    subprocess.run(command, check=True)
    print("::endgroup::")


def output_root_for_target(target: Path) -> Path:
    return target.parent


def release_files_for_target(target: Path, configuration: str) -> Iterable[Path]:
    root = output_root_for_target(target)

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue

        relative = file_path.relative_to(root)
        parts = relative.parts

        try:
            bin_index = parts.index("bin")
        except ValueError:
            continue

        if len(parts) <= bin_index + 1 or parts[bin_index + 1] != configuration:
            continue

        if any(part in COPY_EXCLUDE_DIRS for part in parts):
            continue

        yield file_path


def copy_outputs(target: Path, configuration: str, output_dir: Path) -> int:
    copied = 0
    destination_root = output_dir / target.stem
    source_root = output_root_for_target(target)

    for file_path in release_files_for_target(target, configuration):
        relative_path = file_path.relative_to(source_root)
        destination = destination_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, destination)
        copied += 1

    return copied


def write_result_json(args: argparse.Namespace, repo_root: Path, output_dir: Path, results: list[dict[str, object]]) -> None:
    if not args.result_json:
        return

    status = "success" if all(result["status"] == "success" for result in results) else "failed"
    payload = {
        "generated_at": utc_now(),
        "repository_root": str(repo_root),
        "output_dir": str(output_dir),
        "configuration": args.configuration,
        "branch_name": args.branch_name,
        "branch_display_name": args.branch_display_name,
        "framework_version": args.framework_version,
        "framework_moniker": args.framework_moniker,
        "platform": args.platform,
        "platform_target": args.platform_target,
        "msbuild_platform": args.msbuild_platform,
        "summary": {
            "status": status,
            "total_targets": len(results),
            "successful_targets": sum(1 for result in results if result["status"] == "success"),
            "failed_targets": sum(1 for result in results if result["status"] != "success"),
            "copied_files": sum(int(result.get("copied_files", 0)) for result in results),
        },
        "tools": load_tools_metadata(args.tools_metadata),
        "results": results,
    }

    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    args.result_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    repo_root = args.root.resolve()
    tools_dir = (repo_root / args.projects_dir).resolve()
    output_dir = args.output.resolve()

    print(f"Repository root: {repo_root}")
    print(f"Tools directory: {tools_dir}")

    targets = discover_build_targets(tools_dir)
    if not targets:
        print("No .sln or .csproj files were found under the tools directory. Nothing to build.")
        write_result_json(args, repo_root, output_dir, [])
        return 0

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Build targets:")
    for target in targets:
        print(f" - {target.relative_to(repo_root)}")

    total_copied = 0
    results: list[dict[str, object]] = []
    has_failures = False
    for target in targets:
        result: dict[str, object] = {
            "target": str(target.relative_to(repo_root)),
            "project": target.stem,
            "status": "success",
            "copied_files": 0,
        }
        try:
            build_target(
                target,
                args.configuration,
                framework_version=args.framework_version,
                framework_moniker=args.framework_moniker,
                platform_target=args.platform_target,
                msbuild_platform=args.msbuild_platform,
            )
            copied = copy_outputs(target, args.configuration, output_dir)
            total_copied += copied
            result["copied_files"] = copied
            print(f"Copied {copied} output file(s) for {target.name}")
        except (subprocess.CalledProcessError, RuntimeError, ValueError) as error:
            has_failures = True
            result["status"] = "failed"
            result["error"] = str(error)
            print(f"::error::{target.name} failed: {error}")
            if not args.continue_on_error:
                results.append(result)
                write_result_json(args, repo_root, output_dir, results)
                return 1
        results.append(result)

    print(f"Finished. Copied {total_copied} file(s) into {output_dir}")
    write_result_json(args, repo_root, output_dir, results)
    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
