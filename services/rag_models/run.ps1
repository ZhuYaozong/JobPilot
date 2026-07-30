$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Push-Location $projectRoot
try {
    if ($env:CONDA_DEFAULT_ENV -ne "j-rag") {
        Write-Warning "当前 Conda 环境不是 j-rag，模型服务可能无法导入依赖。"
    }

    python -m services.rag_models.app
}
finally {
    Pop-Location
}
