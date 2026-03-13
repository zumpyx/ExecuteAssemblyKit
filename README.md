# ExecuteAssemblyKit

在自己的仓库里自动编译并归档 .NET 工具，避免依赖第三方的集中式构建仓库。

## 自动编译

仓库已经包含一个 GitHub Actions 工作流：`/.github/workflows/build-tools.yml`

它会在以下场景自动执行：

- push 到 `main` 或 `master`
- Pull Request
- 手动触发 `workflow_dispatch`
- 每天凌晨 03:00 UTC 定时执行

工作流会：

1. 读取 `build-config.json`，决定要同步和构建哪些工具
2. 每天检查配置中的工具仓库是否有新的提交
3. 按 `.NET 4.0 / 4.5 / 4.7` 与 `Any / x86 / x64` 组合分别构建
4. 将编译结果（包含生成的 PE 文件，如 `.exe` / `.dll`）发布到对应的输出分支，并在分支 README 中写入成功/失败状态
5. 回写 `main` 分支上的 `build-status.json` 与 README 状态摘要

## 使用方式

在 `main` 分支根目录的 `build-config.json` 里维护需要自动构建的工具仓库，默认已经预置了以下仓库：

```json
{
  "tools": [
    {
      "name": "Rubeus",
      "repository": "https://github.com/GhostPack/Rubeus.git",
      "enabled": true
    },
    {
      "name": "RunasCs",
      "repository": "https://github.com/antonioCoco/RunasCs.git",
      "enabled": true
    }
  ]
}
```

工作流会把这些仓库克隆到 `tools/` 目录，再自动发现其中的 `.sln` / `.csproj` 并执行构建。

默认已经包含以下目标分支显示名称：

- `.NET_4.0_Any`
- `.NET_4.0_x86`
- `.NET_4.0_x64`
- `.NET_4.5_Any`
- `.NET_4.5_x86`
- `.NET_4.5_x64`
- `.NET_4.7_Any`
- `.NET_4.7_x86`
- `.NET_4.7_x64`

由于 Git 分支名不能以 `.` 开头，工作流会自动把这些显示名称映射为 `NET_4.0_Any` 这类实际分支名。

然后直接在仓库里触发 Actions 即可。

本地也可以手动执行：

```bash
python scripts/manage_build_branches.py --config build-config.json matrix
python scripts/build_dotnet_tools.py --continue-on-error --result-json branch-results/local/build-result.json
```

如果 `tools/` 下暂时没有项目，脚本会安全退出，不会报错。

## 说明

- SDK-style 项目默认使用 `dotnet build`
- 传统 .NET Framework 项目在 Windows runner 上会优先使用 `msbuild`
- 输出分支通过全新初始化仓库并 `force push` 的方式发布，因此不会保留旧的 Git 历史
- `main` 分支只保留配置、状态汇总与自动化脚本
- 本仓库中的 `.gitignore` 已忽略常见的 `bin/`、`obj/` 和 `artifacts/` 输出目录，避免误提交构建产物

<!-- build-status:start -->
## 当前构建状态

- 最后同步时间：`2026-03-13T01:36:35+00:00`
- 已配置工具数：`0`
- 已配置目标分支数：`9`

### 工具仓库检查

| 工具 | 仓库 | 最新提交 | 检测到更新 |
| --- | --- | --- | --- |
| - | - | - | - |

### 目标分支构建结果

| 显示名称 | Git 分支 | 状态 | 成功/失败 | 最后构建时间 |
| --- | --- | --- | --- | --- |
| .NET_4.0_Any | `NET_4.0_Any` | success | 0/0 | `2026-03-13T01:34:46+00:00` |
| .NET_4.0_x86 | `NET_4.0_x86` | success | 0/0 | `2026-03-13T01:36:15+00:00` |
| .NET_4.0_x64 | `NET_4.0_x64` | success | 0/0 | `2026-03-13T01:36:00+00:00` |
| .NET_4.5_Any | `NET_4.5_Any` | success | 0/0 | `2026-03-13T01:34:57+00:00` |
| .NET_4.5_x86 | `NET_4.5_x86` | success | 0/0 | `2026-03-13T01:34:32+00:00` |
| .NET_4.5_x64 | `NET_4.5_x64` | success | 0/0 | `2026-03-13T01:34:27+00:00` |
| .NET_4.7_Any | `NET_4.7_Any` | success | 0/0 | `2026-03-13T01:34:44+00:00` |
| .NET_4.7_x86 | `NET_4.7_x86` | success | 0/0 | `2026-03-13T01:34:46+00:00` |
| .NET_4.7_x64 | `NET_4.7_x64` | success | 0/0 | `2026-03-13T01:34:52+00:00` |

> 说明：Git 分支名不能以 `.` 开头，因此像 `.NET_4.0_Any` 这样的显示名称会自动映射为 `NET_4.0_Any` 分支。
<!-- build-status:end -->
