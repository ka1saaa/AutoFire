from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path


class OCRError(RuntimeError):
    pass


_SKIP_PATTERNS = (
    r"^消息$",
    r"^搜索",
    r"^全部$",
    r"^朋友$",
    r"^群聊$",
    r"^关注$",
    r"^粉丝$",
    r"^新的朋友$",
    r"^在线$",
    r"^置顶$",
    r"^抖音$",
    r"^回复$",
    r"^发送$",
    r"^输入",
    r"^\d{1,2}:\d{2}$",
    r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$",
    r"^\d{1,2}[-/.]\d{1,2}$",
    r"^(刚刚|昨天|今天|星期.|周.|上午|下午|晚上)",
    r"^\d+\s*(秒|分钟|小时|天)前$",
)


def extract_contact_candidates(image_path: Path) -> list[str]:
    text = extract_text_from_image(image_path)
    return parse_contact_candidates(text)


def extract_text_from_image(image_path: Path) -> str:
    image_path = image_path.expanduser().resolve()
    if not image_path.exists():
        raise OCRError("图片文件不存在。")
    powershell = shutil.which("powershell")
    if not powershell:
        raise OCRError("未找到 Windows PowerShell，无法调用系统 OCR。")

    env = os.environ.copy()
    env["AUTOFIRE_OCR_IMAGE"] = str(image_path)
    script = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$imagePath = $env:AUTOFIRE_OCR_IMAGE
if (-not $imagePath) {
    throw '缺少图片路径。'
}

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.FileAccessMode, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult, Windows.Media.Ocr, ContentType = WindowsRuntime]

function Await-Operation($operation, [Type]$resultType) {
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq 'AsTask' -and
            $_.IsGenericMethodDefinition -and
            $_.GetParameters().Count -eq 1
        } |
        Select-Object -First 1
    $task = $method.MakeGenericMethod($resultType).Invoke($null, @($operation))
    $task.Wait()
    return $task.Result
}

$file = Await-Operation ([Windows.Storage.StorageFile]::GetFileFromPathAsync($imagePath)) ([Windows.Storage.StorageFile])
$stream = Await-Operation ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await-Operation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await-Operation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) {
    throw '当前 Windows 用户语言没有可用 OCR 引擎。请在系统设置中安装中文 OCR/语言包。'
}
$result = Await-Operation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$result.Lines | ForEach-Object { $_.Text }
"""
    try:
        completed = subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            encoding="utf-8",
            env=env,
            errors="replace",
            timeout=45,
            check=False,
        )
    except OSError as error:
        raise OCRError(f"无法启动 Windows OCR：{error}") from error
    except subprocess.TimeoutExpired as error:
        raise OCRError("识别超时，请裁剪截图后重试。") from error

    output = completed.stdout.strip()
    if completed.returncode != 0:
        detail = completed.stderr.strip() or output or "未知错误"
        raise OCRError(detail)
    return output


def parse_contact_candidates(text: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        name = clean_candidate(raw_line)
        if not name or name in seen:
            continue
        names.append(name)
        seen.add(name)
    return names


def clean_candidate(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" \t\r\n•·-—|｜")
    if not value:
        return ""
    if len(value) > 32:
        return ""
    if re.fullmatch(r"[\W_]+", value):
        return ""
    if any(re.search(pattern, value, re.IGNORECASE) for pattern in _SKIP_PATTERNS):
        return ""
    return value
