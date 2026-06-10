# 作用：服务类型关键词匹配，兼容“肩颈按摩”与“肩颈理疗/肩颈舒缓”等真实门店命名差异。

SERVICE_ALIASES: dict[str, list[str]] = {
    "肩颈": ["肩颈", "颈肩", "脖子"],
    "全身": ["全身", "放松"],
    "足": ["足底", "足疗", "足部", "脚"],
    "精油": ["精油", "spa"],
    "推拿": ["推拿", "经络", "中式"],
    "拉伸": ["拉伸", "运动", "筋膜", "康复"],
}


def service_query_terms(service_type: str | None) -> list[str]:
    """把用户说的服务类型拆成可匹配关键词。"""
    if not service_type:
        return []
    normalized = service_type.strip().lower().replace(" ", "")
    suffixes = ["按摩", "理疗", "护理", "服务", "项目"]
    terms = {normalized}
    for suffix in suffixes:
        if normalized.endswith(suffix):
            terms.add(normalized[: -len(suffix)])
    for key, aliases in SERVICE_ALIASES.items():
        if key.lower() in normalized or any(alias.lower() in normalized for alias in aliases):
            terms.update(alias.lower() for alias in aliases)
    return [term for term in terms if len(term) >= 2]


def matches_service_type(service_type: str | None, service_text: str) -> bool:
    """判断用户服务类型是否能命中门店服务名称、分类或标签。"""
    if not service_type:
        return True
    normalized_text = service_text.lower().replace(" ", "")
    return any(term in normalized_text for term in service_query_terms(service_type))
