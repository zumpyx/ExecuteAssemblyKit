from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "manage_build_branches.py"
SPEC = importlib.util.spec_from_file_location("manage_build_branches", MODULE_PATH)
MANAGE_BUILD_BRANCHES = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MANAGE_BUILD_BRANCHES)

BUILD_SCRIPT_PATH = REPO_ROOT / "scripts" / "build_dotnet_tools.py"
BUILD_SPEC = importlib.util.spec_from_file_location("build_dotnet_tools", BUILD_SCRIPT_PATH)
BUILD_DOTNET_TOOLS = importlib.util.module_from_spec(BUILD_SPEC)
assert BUILD_SPEC and BUILD_SPEC.loader
BUILD_SPEC.loader.exec_module(BUILD_DOTNET_TOOLS)


class ManageBuildBranchesTests(unittest.TestCase):
    def test_root_build_config_has_no_seed_tool_repositories(self) -> None:
        config = json.loads((REPO_ROOT / "build-config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["tools"], [])

    def test_build_config_contains_only_supported_targets(self) -> None:
        config = json.loads((REPO_ROOT / "build-config.json").read_text(encoding="utf-8"))

        self.assertEqual(
            config["targets"],
            [
                {
                    "framework_version": "4.7",
                    "framework_moniker": "net47",
                    "platform": "Any",
                    "display_name": ".NET_4.7_Any",
                }
            ],
        )

    def test_config_without_targets_falls_back_to_supported_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "build-config.json"
            config_path.write_text(json.dumps({"tools": []}), encoding="utf-8")

            config = MANAGE_BUILD_BRANCHES.load_config(config_path)

            self.assertEqual(
                MANAGE_BUILD_BRANCHES.configured_targets(config),
                [
                    {
                        "framework_version": "4.7",
                        "framework_moniker": "net47",
                        "platform": "Any",
                        "display_name": ".NET_4.7_Any",
                        "branch": "NET_4.7_Any",
                        "msbuild_platform": "Any CPU",
                        "platform_target": "AnyCPU",
                    }
                ],
            )

    def test_normalize_target_sanitizes_invalid_branch_name(self) -> None:
        normalized = MANAGE_BUILD_BRANCHES.normalize_target(
            {
                "framework_version": "4.0",
                "framework_moniker": "net40",
                "platform": "Any",
                "display_name": ".NET_4.0_Any",
            }
        )

        self.assertEqual(normalized["display_name"], ".NET_4.0_Any")
        self.assertEqual(normalized["branch"], "NET_4.0_Any")
        self.assertEqual(normalized["msbuild_platform"], "Any CPU")
        self.assertEqual(normalized["platform_target"], "AnyCPU")

    def test_update_main_readme_replaces_status_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            readme_path = Path(temp_dir) / "README.md"
            readme_path.write_text(
                "# Demo\n\n"
                f"{MANAGE_BUILD_BRANCHES.README_START}\nold\n{MANAGE_BUILD_BRANCHES.README_END}\n",
                encoding="utf-8",
            )

            MANAGE_BUILD_BRANCHES.update_main_readme(
                readme_path,
                {
                    "generated_at": "2026-03-13T00:00:00+00:00",
                    "tools": [],
                    "branches": [],
                    "summary": {"tool_count": 0, "branch_count": 0},
                },
            )

            content = readme_path.read_text(encoding="utf-8")
            self.assertIn("2026-03-13T00:00:00+00:00", content)
            self.assertNotIn("\nold\n", content)

    def test_aggregate_status_collects_branch_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            config_path = temp_root / "build-config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "tools": [],
                        "targets": [
                            {
                                "framework_version": "4.0",
                                "framework_moniker": "net40",
                                "platform": "Any",
                                "display_name": ".NET_4.0_Any",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            results_dir = temp_root / "results" / "branch-result-NET_4.0_Any"
            results_dir.mkdir(parents=True)
            (results_dir / "build-result.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-03-13T00:00:00+00:00",
                        "branch_name": "NET_4.0_Any",
                        "branch_display_name": ".NET_4.0_Any",
                        "summary": {
                            "status": "success",
                            "successful_targets": 1,
                            "failed_targets": 0,
                            "copied_files": 2,
                        },
                        "tools": [
                            {
                                "name": "ToolA",
                                "repository": "https://example.invalid/ToolA.git",
                                "latest_revision": "abc123",
                                "updated": True,
                            }
                        ],
                        "results": [],
                    }
                ),
                encoding="utf-8",
            )

            readme_path = temp_root / "README.md"
            readme_path.write_text("# Demo\n", encoding="utf-8")
            status_output = temp_root / "build-status.json"

            exit_code = MANAGE_BUILD_BRANCHES.aggregate_status(
                config_path,
                temp_root / "results",
                status_output,
                readme_path,
                None,
            )

            self.assertEqual(exit_code, 0)
            status = json.loads(status_output.read_text(encoding="utf-8"))
            self.assertEqual(status["summary"]["branch_count"], 1)
            self.assertEqual(status["summary"]["tool_count"], 1)
            self.assertEqual(status["branches"][0]["branch"], "NET_4.0_Any")
            self.assertEqual(status["branches"][0]["status"], "success")
            self.assertIn("NET_4.0_Any", readme_path.read_text(encoding="utf-8"))

    def test_write_result_json_handles_empty_target_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "build-result.json"

            class Args:
                configuration = "Release"
                branch_name = "NET_4.0_Any"
                branch_display_name = ".NET_4.0_Any"
                framework_version = "4.0"
                framework_moniker = "net40"
                platform = "Any"
                platform_target = "AnyCPU"
                msbuild_platform = "Any CPU"
                tools_metadata = None
                result_json = output_path

            BUILD_DOTNET_TOOLS.write_result_json(Args(), REPO_ROOT, REPO_ROOT / "artifacts", [])
            result = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertEqual(result["summary"]["total_targets"], 0)
            self.assertEqual(result["summary"]["status"], "success")
            self.assertEqual(result["results"], [])

    def test_copy_outputs_includes_nested_solution_pe_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            solution_path = temp_root / "ToolSuite.sln"
            solution_path.write_text("", encoding="utf-8")

            project_output_dir = temp_root / "Rubeus" / "bin" / "Release"
            project_output_dir.mkdir(parents=True)
            exe_path = project_output_dir / "Rubeus.exe"
            dll_path = project_output_dir / "Helper.dll"
            pdb_path = project_output_dir / "Helper.pdb"
            exe_path.write_text("exe", encoding="utf-8")
            dll_path.write_text("dll", encoding="utf-8")
            pdb_path.write_text("pdb", encoding="utf-8")

            ignored_ref_dir = project_output_dir / "ref"
            ignored_ref_dir.mkdir()
            (ignored_ref_dir / "Ignored.dll").write_text("ignored", encoding="utf-8")

            output_dir = temp_root / "artifacts"
            copied_files = BUILD_DOTNET_TOOLS.copy_outputs(solution_path, "Release", output_dir)

            self.assertEqual(copied_files, 3)
            self.assertTrue((output_dir / "ToolSuite" / "Rubeus" / "bin" / "Release" / "Rubeus.exe").exists())
            self.assertTrue((output_dir / "ToolSuite" / "Rubeus" / "bin" / "Release" / "Helper.dll").exists())
            self.assertTrue((output_dir / "ToolSuite" / "Rubeus" / "bin" / "Release" / "Helper.pdb").exists())
            self.assertFalse(
                (output_dir / "ToolSuite" / "Rubeus" / "bin" / "Release" / "ref" / "Ignored.dll").exists()
            )


if __name__ == "__main__":
    unittest.main()
