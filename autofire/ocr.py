from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class OCRError(RuntimeError):
    pass


@dataclass(frozen=True)
class OCRLine:
    text: str
    left: float = 0
    top: float = 0
    width: float = 0
    height: float = 0
    image_width: float = 0
    image_height: float = 0


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
    r"^\d+$",
    r"^\[.*\]$",
    r"^\d{1,2}:\d{2}$",
    r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$",
    r"^\d{1,2}[-/.]\d{1,2}$",
    r"^(刚刚|昨天|今天|星期.|周.|上午|下午|晚上)",
    r"^\d+\s*(秒|分钟|小时|天)前$",
)


def extract_contact_candidates(image_path: Path) -> list[str]:
    lines = extract_lines_from_image(image_path)
    return parse_contact_candidates_from_lines(lines)


def extract_text_from_image(image_path: Path) -> str:
    return "\n".join(line.text for line in extract_lines_from_image(image_path))


def extract_lines_from_image(image_path: Path) -> list[OCRLine]:
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
$items = @()
foreach ($line in $result.Lines) {
    $left = [double]::PositiveInfinity
    $top = [double]::PositiveInfinity
    $right = 0.0
    $bottom = 0.0
    foreach ($word in $line.Words) {
        $rect = $word.BoundingRect
        if ($rect.X -lt $left) { $left = $rect.X }
        if ($rect.Y -lt $top) { $top = $rect.Y }
        if (($rect.X + $rect.Width) -gt $right) { $right = $rect.X + $rect.Width }
        if (($rect.Y + $rect.Height) -gt $bottom) { $bottom = $rect.Y + $rect.Height }
    }
    if ([double]::IsPositiveInfinity($left)) {
        $left = 0.0
        $top = 0.0
    }
    $items += [PSCustomObject]@{
        text = $line.Text
        left = [Math]::Round($left, 2)
        top = [Math]::Round($top, 2)
        width = [Math]::Round(($right - $left), 2)
        height = [Math]::Round(($bottom - $top), 2)
        image_width = $bitmap.PixelWidth
        image_height = $bitmap.PixelHeight
    }
}
$json = $items | ConvertTo-Json -Compress
$bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
[Console]::OpenStandardOutput().Write($bytes, 0, $bytes.Length)
"""
    try:
        completed = subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            env=env,
            timeout=45,
            check=False,
        )
    except OSError as error:
        raise OCRError(f"无法启动 Windows OCR：{error}") from error
    except subprocess.TimeoutExpired as error:
        raise OCRError("识别超时，请裁剪截图后重试。") from error

    output = completed.stdout.decode("utf-8", errors="replace").strip()
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip() or output or "未知错误"
        raise OCRError(detail)
    if not output:
        return []
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return [OCRLine(line) for line in output.splitlines()]
    if isinstance(data, dict):
        data = [data]
    return [
        OCRLine(
            text=str(item.get("text", "")),
            left=float(item.get("left") or 0),
            top=float(item.get("top") or 0),
            width=float(item.get("width") or 0),
            height=float(item.get("height") or 0),
            image_width=float(item.get("image_width") or 0),
            image_height=float(item.get("image_height") or 0),
        )
        for item in data
        if isinstance(item, dict)
    ]


def parse_contact_candidates_from_lines(lines: list[OCRLine]) -> list[str]:
    if not lines:
        return []
    if any(line.image_width and line.image_height for line in lines):
        names = parse_douyin_contact_lines(lines)
        if names:
            return names
    return parse_contact_candidates("\n".join(line.text for line in lines))


def parse_douyin_contact_lines(lines: list[OCRLine]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    last_name_top = -1.0
    image_height = next((line.image_height for line in lines if line.image_height), 0)
    min_row_gap = image_height * 0.055 if image_height else 0
    for line in sorted(lines, key=lambda item: (item.top, item.left)):
        if min_row_gap and last_name_top >= 0 and line.top - last_name_top < min_row_gap:
            continue
        if not looks_like_douyin_name_line(line):
            continue
        name = clean_douyin_name(line.text)
        if not name or name in seen:
            continue
        names.append(name)
        seen.add(name)
        last_name_top = line.top
    return names


def looks_like_douyin_name_line(line: OCRLine) -> bool:
    if not line.image_width or not line.image_height:
        return False
    if line.top < line.image_height * 0.10 or line.top > line.image_height * 0.88:
        return False
    if line.left < line.image_width * 0.18 or line.left > line.image_width * 0.72:
        return False
    if line.height < line.image_height * 0.020:
        return False
    text = line.text.strip()
    if not text:
        return False
    if clean_candidate(text) != text and not clean_douyin_name(text):
        return False
    if "火花" in text or "互聊" in text or "问候" in text or "提醒" in text or "分享图文" in text:
        return False
    if re.search(r"(分钟前|小时前|昨天|今天|上午|下午|晚上|\d{1,2}:\d{2})", text):
        return False
    return True


def clean_douyin_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s*(?:[🔥火0]\s*)?\d{1,4}\s*$", "", value).strip()
    value = compact_cjk_spaces(value)
    value = value.strip(" \t\r\n•·-—|｜")
    if not clean_candidate(value):
        return ""
    return value


def has_flame_suffix(value: str) -> bool:
    return bool(re.search(r"([🔥火]\s*)?\d{1,4}\s*$", value.strip()))


def compact_cjk_spaces(value: str) -> str:
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fffA-Za-z0-9])", "", value)
    value = re.sub(r"(?<=[A-Za-z0-9])\s+(?=[\u4e00-\u9fff])", "", value)
    return value


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
