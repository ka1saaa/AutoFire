$ErrorActionPreference = 'Stop'

python -m PyInstaller --noconfirm --clean --windowed --onedir --name AutoFire app.py

New-Item -ItemType Directory -Force -Path release | Out-Null
if (Test-Path release\AutoFire) {
    Remove-Item -Recurse -Force release\AutoFire
}
Copy-Item -Recurse dist\AutoFire release\AutoFire
Copy-Item README.md release\AutoFire\README.md
Compress-Archive -Path release\AutoFire -DestinationPath release\AutoFire-windows-x64.zip -Force
Write-Host "发布文件已生成：release\AutoFire\AutoFire.exe"
Write-Host "发布压缩包已生成：release\AutoFire-windows-x64.zip"
