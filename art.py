"""Inline SVG artwork: one hero banner scene per screen, a page pattern and the logo.

Everything is generated here (no external images), so the app looks the same offline.
"""

from urllib.parse import quote

W, H = 1200, 260

# scene key -> (gradient end colour, soft page tint)
PALETTE = {
    "overview": ("#1d4ed8", "rgba(59,130,246,.16)"),
    "supplier": ("#0e7490", "rgba(20,184,166,.16)"),
    "decision": ("#4f46e5", "rgba(129,140,248,.18)"),
    "allocation": ("#047857", "rgba(52,211,153,.16)"),
    "orders": ("#b45309", "rgba(251,191,36,.18)"),
    "export": ("#475569", "rgba(148,163,184,.22)"),
}


def _frame(end: str, inner: str) -> str:
    grid = "".join(f'<path d="M{x} 0V{H}" />' for x in range(0, W, 60)) + "".join(
        f'<path d="M0 {y}H{W}" />' for y in range(0, H, 60)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMaxYMid slice">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b1f3a"/>'
        f'<stop offset="1" stop-color="{end}"/></linearGradient></defs>'
        f'<rect width="{W}" height="{H}" fill="url(#g)"/>'
        f'<g stroke="#fff" stroke-opacity=".05" stroke-width="1">{grid}</g>'
        f'<circle cx="1010" cy="120" r="230" fill="#fff" opacity=".05"/>'
        f'<circle cx="1130" cy="40" r="110" fill="#fff" opacity=".05"/>'
        f"{inner}</svg>"
    )


def _overview() -> str:
    parts = []
    for x in (690, 900, 1110):  # uprights
        parts.append(f'<rect x="{x}" y="30" width="9" height="205" rx="3" fill="#94a3b8"/>')
    colors = ["#f5b942", "#5aa9ff", "#e2e8f0", "#2dd4bf", "#f59e0b", "#93c5fd"]
    layout = [  # per shelf: (x offset, width, height)
        [(14, 46, 38), (66, 36, 28), (108, 54, 44), (170, 40, 32)],
        [(14, 40, 30), (60, 58, 46), (124, 36, 26), (166, 42, 38)],
        [(14, 58, 40), (78, 40, 34), (124, 38, 28), (168, 36, 44)],
    ]
    k = 0
    for r, row in enumerate(layout):
        base = 85 + r * 70
        for half in (690, 900):
            for dx, w, h in row:
                c = colors[k % len(colors)]
                k += 1
                parts.append(f'<rect x="{half + dx}" y="{base - h}" width="{w}" height="{h}" rx="4" fill="{c}"/>')
                parts.append(f'<rect x="{half + dx + w / 2 - 3}" y="{base - h}" width="6" height="{h}" fill="#0b1f3a" opacity=".18"/>')
        parts.append(f'<rect x="690" y="{base}" width="428" height="7" rx="3" fill="#cbd5e1"/>')
    parts.append('<rect x="660" y="236" width="500" height="6" rx="3" fill="#fff" opacity=".25"/>')
    return "".join(parts)


def _supplier() -> str:
    return (
        '<rect x="640" y="226" width="520" height="5" rx="2" fill="#fff" opacity=".3"/>'
        '<path d="M1010 74 C 950 8, 860 20, 838 104" fill="none" stroke="#fff" stroke-width="3" stroke-dasharray="8 8" opacity=".7"/>'
        '<rect x="1010" y="42" width="112" height="76" rx="10" fill="#f8fafc"/>'
        '<path d="M1016 52 L1066 92 L1116 52" fill="none" stroke="#0e7490" stroke-width="6" stroke-linejoin="round" stroke-linecap="round"/>'
        '<circle cx="1122" cy="44" r="18" fill="#2dd4bf"/>'
        '<path d="M1114 44 l6 7 l11 -13" fill="none" stroke="#0b1f3a" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
        '<rect x="740" y="112" width="250" height="100" rx="10" fill="#17325a" stroke="#cbd5e1" stroke-width="3"/>'
        '<rect x="756" y="150" width="58" height="52" rx="5" fill="#5aa9ff"/><rect x="756" y="150" width="58" height="9" rx="4" fill="#0b1f3a" opacity=".25"/>'
        '<rect x="822" y="130" width="62" height="72" rx="5" fill="#f5b942"/><rect x="822" y="130" width="62" height="9" rx="4" fill="#0b1f3a" opacity=".25"/>'
        '<rect x="892" y="162" width="46" height="40" rx="5" fill="#2dd4bf"/><rect x="944" y="146" width="34" height="56" rx="5" fill="#e2e8f0"/>'
        '<path d="M996 150 h52 l34 32 v30 h-86z" fill="#f5b942"/>'
        '<path d="M1010 160 h30 l20 20 h-50z" fill="#0b1f3a" opacity=".65"/>'
        '<g fill="#0f172a" stroke="#cbd5e1" stroke-width="4"><circle cx="790" cy="214" r="18"/>'
        '<circle cx="850" cy="214" r="18"/><circle cx="1030" cy="214" r="18"/></g>'
    )


def _decision() -> str:
    base, rev = [100, 50, 0, 0], [100, 0, 30, 20]
    parts = ['<rect x="700" y="222" width="440" height="4" rx="2" fill="#fff" opacity=".35"/>']
    for i, x in enumerate((730, 850, 970, 1090)):
        for j, (vals, col) in enumerate(((base, "#cbd5e1"), (rev, "#5aa9ff"))):
            h = vals[i] * 1.7
            if h:
                parts.append(f'<rect x="{x + j * 34 - 34}" y="{222 - h}" width="28" height="{h}" rx="5" fill="{col}"/>')
    # a late-delivery marker over the 13 Oct bar, and a risk flag
    parts.append('<circle cx="990" cy="150" r="13" fill="#f85149"/><rect x="987" y="142" width="6" height="12" rx="2" fill="#fff"/>'
                 '<circle cx="990" cy="160" r="3" fill="#fff"/>')
    return "".join(parts)


def _allocation() -> str:
    pattern = [["ok", "none", "none", "none"], ["ok", "late", "none", "none"], ["none", "ok", "ok", "none"]]
    fill = {"ok": "#3fb950", "late": "#f85149", "none": "#fff"}
    parts = []
    for c, label_w in enumerate((92, 70, 70, 70)):
        parts.append(f'<rect x="{720 + c * 100}" y="34" width="{label_w}" height="10" rx="5" fill="#fff" opacity=".55"/>')
    for r, row in enumerate(pattern):
        parts.append(f'<rect x="660" y="{78 + r * 56}" width="38" height="10" rx="5" fill="#fff" opacity=".55"/>')
        for c, kind in enumerate(row):
            op = ".14" if kind == "none" else ".95"
            parts.append(f'<rect x="{720 + c * 100}" y="{60 + r * 56}" width="88" height="46" rx="10" fill="{fill[kind]}" opacity="{op}"/>')
    parts.append('<rect x="1010" y="116" width="88" height="46" rx="10" fill="none" stroke="#fff" stroke-width="3"/>')
    return "".join(parts)


def _orders() -> str:
    parts = [
        '<rect x="700" y="26" width="230" height="214" rx="18" fill="#f8fafc"/>',
        '<rect x="766" y="14" width="98" height="30" rx="10" fill="#334155"/>',
    ]
    for i, (col, w) in enumerate((("#3fb950", 130), ("#f5b942", 100), ("#f85149", 120))):
        y = 76 + i * 52
        parts.append(f'<circle cx="736" cy="{y + 12}" r="12" fill="{col}"/>')
        parts.append(f'<rect x="762" y="{y}" width="{w}" height="10" rx="5" fill="#334155" opacity=".85"/>')
        parts.append(f'<rect x="762" y="{y + 16}" width="{w - 40}" height="8" rx="4" fill="#94a3b8"/>')
    parts.append(
        '<path d="M1040 70 L1128 218 H952 Z" fill="#f5b942" stroke="#fff" stroke-width="8" stroke-linejoin="round"/>'
        '<rect x="1034" y="116" width="12" height="52" rx="6" fill="#0b1f3a"/><circle cx="1040" cy="190" r="8" fill="#0b1f3a"/>'
    )
    return "".join(parts)


def _export() -> str:
    return (
        '<rect x="720" y="40" width="150" height="190" rx="14" fill="#f8fafc" opacity=".55" transform="rotate(-6 795 135)"/>'
        '<rect x="750" y="30" width="150" height="196" rx="14" fill="#f8fafc"/>'
        + "".join(f'<rect x="772" y="{62 + i * 30}" width="{100 - (i % 2) * 28}" height="9" rx="4.5" fill="#94a3b8"/>' for i in range(5))
        + '<circle cx="1030" cy="108" r="64" fill="#1f6feb"/>'
        '<path d="M1030 74 V132 M1006 110 L1030 134 L1054 110" fill="none" stroke="#fff" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M964 190 V222 H1096 V190" fill="none" stroke="#fff" stroke-width="8" stroke-linecap="round" stroke-linejoin="round" opacity=".9"/>'
    )


SCENES = {
    "overview": _overview, "supplier": _supplier, "decision": _decision,
    "allocation": _allocation, "orders": _orders, "export": _export,
}


def scene_svg(key: str) -> str:
    return _frame(PALETTE[key][0], SCENES[key]())


def data_uri(svg: str) -> str:
    return "data:image/svg+xml;charset=utf-8," + quote(svg.replace("\n", ""), safe="")


def pattern(color: str = "#64748b", opacity: str = ".16") -> str:
    """Faint dot grid used as the page background texture."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28">'
        f'<circle cx="2" cy="2" r="1.2" fill="{color}" opacity="{opacity}"/></svg>'
    )


LOGO = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="230" height="46" viewBox="0 0 230 46">'
    '<circle cx="23" cy="23" r="19" fill="none" stroke="#5aa9ff" stroke-width="3"/>'
    '<path d="M23 8 L30 28 L23 24 L16 28 Z" fill="#fff"/><circle cx="23" cy="23" r="2.4" fill="#0b1f3a"/>'
    '<text x="52" y="30" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif" font-size="22" font-weight="700" fill="#fff">ShortagePilot</text>'
    "</svg>"
)


def scene_css() -> str:
    rules = [
        f".sp-hero.{k}{{background-image:url(\"{data_uri(scene_svg(k))}\")}}" for k in SCENES
    ]
    return "".join(rules)
