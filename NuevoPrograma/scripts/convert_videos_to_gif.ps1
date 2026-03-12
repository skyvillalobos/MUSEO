# Batch convert MP4 files to GIF using ffmpeg (recommended)
# Usage: Open PowerShell in the repo root and run: .\scripts\convert_videos_to_gif.ps1

$srcDir = "assets/videos_finales"
$fps = 15
$width = 640 # target width to keep GIF size reasonable

Get-ChildItem -Path $srcDir -Filter *.mp4 | ForEach-Object {
    $in = $_.FullName
    $base = $_.BaseName
    $palette = Join-Path $srcDir "$base" + "_palette.png"
    $out = Join-Path $srcDir ($base + ".gif")

    Write-Host "Convirtiendo: $in -> $out"

    # generar paleta
    & ffmpeg -y -i "$in" -vf "fps=$fps,scale=$width:-1:flags=lanczos,palettegen" "$palette"
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "ffmpeg falló al generar la paleta para $in"
        return
    }

    # generar gif usando la paleta
    & ffmpeg -y -i "$in" -i "$palette" -filter_complex "fps=$fps,scale=$width:-1:flags=lanczos[x];[x][1:v]paletteuse" "$out"
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "ffmpeg falló al crear el GIF para $in"
    } else {
        Write-Host "GIF creado: $out"
        # opcional: eliminar paleta
        Remove-Item "$palette" -ErrorAction SilentlyContinue
    }
}
