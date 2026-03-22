# ExecuteAssemblyKit (`execute-assembly`)

在自己的仓库里自动编译并归档 .NET 程序 / .NET Framework 项目，避免依赖第三方的集中式构建仓库或不受控的聚合二进制来源。

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
3. 按 `build-config.json` 中声明的目标组合分别构建，仓库默认使用当前 Actions runner 可稳定成功的 `.NET 4.7 / Any`
4. 将编译结果（包含生成的 PE 文件，如 `.exe` / `.dll`）发布到对应的输出分支，并在分支 README 中写入成功/失败状态
5. 回写 `main` 分支上的 `build-status.json` 与 README 状态摘要

## 使用方式

在 `main` 分支根目录的 `build-config.json` 里维护需要自动构建的源码仓库。默认配置不会预置任何第三方仓库，你只需要把自己的仓库地址填进去即可：

```json
{
  "tools": [
    {
      "name": "ExampleApp",
      "repository": "https://github.com/your-org/ExampleApp.git",
      "enabled": true
    }
  ]
}
```

工作流会把这些仓库克隆到 `tools/` 目录，再自动发现其中的 `.sln` / `.csproj` 并执行构建。这样你可以只编译自己明确指定的源码仓库，减少依赖第三方聚合仓库带来的供应链风险。
如果配置文件里省略 `targets` 字段，脚本也会默认回退到 `.NET_4.7_Any`，避免重新生成当前 runner 无法稳定通过的旧矩阵。

默认已经包含以下目标分支显示名称：

- `.NET_4.7_Any`

之所以默认只保留这个目标，是因为当前 GitHub Actions Windows runner 上，`.NET 4.0 / 4.5` 缺少对应的 targeting pack。与此同时，仓库内现有解决方案也没有 `x86` / `x64` 的可用 solution configuration；继续保留这些组合会导致工作流稳定失败。

由于 Git 分支名不能以 `.` 开头，工作流会自动把这些显示名称映射为 `NET_4.7_Any` 这类实际分支名。

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

- 最后同步时间：`2026-03-22T03:50:47+00:00`
- 已配置源码仓库数：`1`
- 已配置目标分支数：`1`

### 源码仓库检查

| 仓库名 | 仓库 | 最新提交 | 检测到更新 |
| --- | --- | --- | --- |
| Rubeus | https://github.com/GhostPack/Rubeus.git | `74215f68ea70bd6a66c008da91bf5fe21d20b154` | 否 |

### 目标分支构建结果

| 显示名称 | Git 分支 | 状态 | 成功/失败 | 最后构建时间 |
| --- | --- | --- | --- | --- |
| .NET_4.7_Any | `NET_4.7_Any` | success | 1/0 | `2026-03-22T03:50:34+00:00` |

> 说明：Git 分支名不能以 `.` 开头，因此像 `.NET_4.0_Any` 这样的显示名称会自动映射为 `NET_4.0_Any` 分支。
<!-- build-status:end -->
