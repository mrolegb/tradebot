param(
    [Parameter(Position = 0)]
    [ValidateSet("help", "setup", "install", "test", "compile", "run", "sim", "local-smoke", "testnet", "testnet-smoke", "live", "live-smoke", "report", "batch", "api", "web-install", "web-dev", "web-build", "clean", "status")]
    [string]$Task = "help"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$VenvUvicorn = Join-Path $Root ".venv\Scripts\uvicorn.exe"

function Invoke-Python {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    if (Test-Path $VenvPython) {
        & $VenvPython @Args
        return
    }

    & python @Args
}

function Show-Help {
    Write-Host "Usage: .\task.ps1 <task>"
    Write-Host ""
    Write-Host "Tasks:"
    Write-Host "  setup    Create .venv, install dependencies, create .env if missing"
    Write-Host "  install  Install dependencies into .venv"
    Write-Host "  test     Run pytest"
    Write-Host "  compile  Compile app and tests"
    Write-Host "  run      Run bot with configs/global.yaml"
    Write-Host "  sim      Run bot with configs/local_test.yaml"
    Write-Host "  local-smoke Run local simulation smoke test"
    Write-Host "  testnet  Run one bot pass with configs/binance_testnet.yaml"
    Write-Host "  testnet-smoke Verify Binance testnet account, rules, market data, and guarded order flow"
    Write-Host "  live     Run one bot pass with configs/binance_live.yaml (requires live env guards)"
    Write-Host "  live-smoke Verify Binance live order flow with extra smoke confirmation"
    Write-Host "  report   Run local multi-candle simulation and export reports"
    Write-Host "  batch    Run multi-seed, multi-regime robustness suite"
    Write-Host "  api      Start FastAPI dev server"
    Write-Host "  web-install Install React dashboard dependencies"
    Write-Host "  web-dev  Start React dashboard dev server"
    Write-Host "  web-build Build React dashboard"
    Write-Host "  clean    Remove Python caches and pytest cache"
    Write-Host "  status   Show git status"
}

Set-Location $Root

switch ($Task) {
    "help" {
        Show-Help
    }
    "setup" {
        if (-not (Test-Path $VenvPython)) {
            python -m venv .venv
        }
        & $VenvPython -m pip install -r requirements.txt
        if (-not (Test-Path ".env")) {
            Copy-Item ".env.example" ".env"
        }
    }
    "install" {
        if (-not (Test-Path $VenvPython)) {
            python -m venv .venv
        }
        & $VenvPython -m pip install -r requirements.txt
    }
    "test" {
        Invoke-Python -m pytest -q
    }
    "compile" {
        Invoke-Python -m compileall app tests
    }
    "run" {
        Invoke-Python -m app.main --config configs/global.yaml
    }
    "sim" {
        Invoke-Python -m app.main --config configs/local_test.yaml
    }
    "local-smoke" {
        Invoke-Python -m app.runtime.smoke --mode local --config configs/local_test.yaml
    }
    "testnet" {
        Invoke-Python -m app.main --config configs/binance_testnet.yaml
    }
    "testnet-smoke" {
        Invoke-Python -m app.runtime.smoke --mode testnet --config configs/binance_testnet.yaml
    }
    "live" {
        Invoke-Python -m app.main --config configs/binance_live.yaml
    }
    "live-smoke" {
        Invoke-Python -m app.runtime.smoke --mode live --config configs/binance_live.yaml
    }
    "report" {
        Invoke-Python -m app.simulation.cli --config configs/local_test.yaml
    }
    "batch" {
        Invoke-Python -m app.simulation.batch --config configs/local_test.yaml
    }
    "api" {
        if (Test-Path $VenvUvicorn) {
            & $VenvUvicorn app.api:app --reload
            return
        }
        Invoke-Python -m uvicorn app.api:app --reload
    }
    "web-install" {
        Push-Location (Join-Path $Root "web")
        npm install
        Pop-Location
    }
    "web-dev" {
        Push-Location (Join-Path $Root "web")
        npm run dev
        Pop-Location
    }
    "web-build" {
        Push-Location (Join-Path $Root "web")
        npm run build
        Pop-Location
    }
    "clean" {
        Get-ChildItem -Path $Root -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
        if (Test-Path ".pytest_cache") {
            Remove-Item ".pytest_cache" -Recurse -Force
        }
    }
    "status" {
        git status --short
    }
}
