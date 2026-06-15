"""手机号格式化（CloudBase 要求 +86 前缀）。"""

from __future__ import annotations

import re


def normalize_phone(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    if text.startswith("+"):
        return re.sub(r"\s+", " ", text)
    digits = re.sub(r"\D", "", text)
    if not digits:
        return ""
    if digits.startswith("86") and len(digits) > 11:
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("1"):
        return f"+86 {digits}"
    return f"+86 {digits}"


def phone_lookup_variants(raw: str) -> list[str]:
    """返回用于数据库查询的手机号变体（兼容历史未规范化写入）。"""
    normalized = normalize_phone(raw)
    if not normalized:
        return []
    digits = re.sub(r"\D", "", normalized)
    if digits.startswith("86") and len(digits) > 11:
        local = digits[2:]
    else:
        local = digits
    cn11 = len(local) == 11 and local.startswith("1")
    variants: list[str] = []
    seen: set[str] = set()
    candidates = [
        normalized,
        local,
        f"+86{local}",
        f"+86 {local}",
        f"86{local}",
        raw.strip(),
    ]
    if cn11:
        candidates.extend([f"+86-{local[:3]}-{local[3:7]}-{local[7:]}", f"{local[:3]} {local[3:7]} {local[7:]}"])
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            variants.append(candidate)
    return variants


def phone_local_digits(raw: str) -> str:
    """提取 11 位中国大陆手机号（无区号）。"""
    normalized = normalize_phone(raw)
    digits = re.sub(r"\D", "", normalized or raw)
    if digits.startswith("86") and len(digits) > 11:
        return digits[2:]
    return digits
