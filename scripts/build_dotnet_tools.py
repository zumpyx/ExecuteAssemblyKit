from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree


IGNORED_DIRS = {".git", ".github", "artifacts", "bin", "obj"}
COPY_EXCLUDE_DIRS = {"obj", "ref", "refs"}


def parse_args() -> argparse.Namespace:
    script_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Discover and compile .NET tools stored in this repository."
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
        help="Directory under the repository root that contains tool sources.",
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
    return parser.parse_args()


def iter_candidates(base_dir: Path, suffix: str) -> Iterable[Path]:
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


def build_target(target: Path, configuration: str) -> None:
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

        if len(parts) < 2 or parts[0] != "bin" or parts[1] != configuration:
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
        return 0

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Build targets:")
    for target in targets:
        print(f" - {target.relative_to(repo_root)}")

    total_copied = 0
    for target in targets:
        build_target(target, args.configuration)
        copied = copy_outputs(target, args.configuration, output_dir)
        total_copied += copied
        print(f"Copied {copied} output file(s) for {target.name}")

    print(f"Finished. Copied {total_copied} file(s) into {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
