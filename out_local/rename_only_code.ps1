# rename_only_code.ps1
$ErrorActionPreference = "Stop"

# 1) 대상: 루트의 *.html (필요하면 -Recurse로 하위폴더까지)
$files = Get-ChildItem -File -Filter *.html

$seen = @{}
foreach ($f in $files) {
  # 파일명 예: 1000000001_01_백철가마솥_....html
  if ($f.BaseName -notmatch '^(\d+)_') { continue }

  $code = $Matches[1]
  $newName = "$code.html"

  # 충돌(동일 코드가 2개 이상) 방지
  if ($seen.ContainsKey($newName)) {
    Write-Host "SKIP (duplicate code): $($f.Name) -> $newName"
    continue
  }
  $seen[$newName] = $true

  if ($f.Name -ne $newName) {
    git mv -- "$($f.Name)" "$newName"
    Write-Host "RENAMED: $($f.Name) -> $newName"
  }
}

Write-Host "`nDone. Check: git status"
