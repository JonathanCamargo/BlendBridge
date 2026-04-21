# Export BlendBridge addon as a .zip for Blender addon install (Windows)
$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot

# Clear stale __pycache__ from installed extension (Blender 4.x default path)
$BlenderBase = Join-Path $env:APPDATA "Blender Foundation\Blender"
if (Test-Path $BlenderBase) {
    Get-ChildItem $BlenderBase -Directory | ForEach-Object {
        $Dirs = @(
            (Join-Path $_.FullName "extensions\user_default\blendbridge"),
            (Join-Path $_.FullName "scripts\addons\addon")
        )
        foreach ($Dir in $Dirs) {
            if (Test-Path $Dir) {
                Get-ChildItem $Dir -Directory -Recurse -Filter __pycache__ |
                    Remove-Item -Recurse -Force
            }
        }
    }
}

python scripts/build_addon_zip.py --output $env:TEMP

Pop-Location
