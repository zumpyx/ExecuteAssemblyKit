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

1. 在 `tools/` 目录下自动发现 `.sln` 和 `.csproj`
2. 自动编译这些工具的 `Release` 版本
3. 将编译产物收集到 `artifacts/`
4. 把产物作为 GitHub Actions artifact 上传

## 使用方式

把你想自己维护和编译的工具源码放到类似下面的目录：

```text
tools/
  ToolA/
    ToolA.sln
  ToolB/
    ToolB.csproj
```

然后直接在仓库里触发 Actions 即可。

本地也可以手动执行：

```bash
python scripts/build_dotnet_tools.py
```

如果 `tools/` 下暂时没有项目，脚本会安全退出，不会报错。

## 说明

- SDK-style 项目默认使用 `dotnet build`
- 传统 .NET Framework 项目在 Windows runner 上会优先使用 `msbuild`
- 本仓库中的 `.gitignore` 已忽略常见的 `bin/`、`obj/` 和 `artifacts/` 输出目录，避免误提交构建产物
