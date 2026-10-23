# Start the UI only. Model engines are separately installed; see docs/INSTALL_AR.md.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Creating local server environment..."
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python 3.11 installation not found." }
}
Write-Host "Installing the small web-server dependencies..."
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Server dependency installation failed." }
Write-Host "Opening Mina Voice Studio at http://127.0.0.1:7860"
& $python -m uvicorn studio.app:app --host 127.0.0.1 --port 7860
