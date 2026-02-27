# Icon Replacement Matrix (Part 2)

This matrix defines the SVG replacement policy for legacy icon-like glyphs.

| Legacy | Target Icon (Lucide) | Notes |
|---|---|---|
| `📁` | `Folder` | DB tree directory row |
| `📄` | `FileText` | DB tree file leaf |
| `▸` | `ChevronRight` | collapsed tree state |
| `▾` | `ChevronDown` | expanded tree state |
| `★` | `Star` (filled style) | favorite active |
| `☆` | `StarOff` / outlined Star | favorite inactive |

Rules:

- Do not use emoji as UI icon.
- Keep one icon family (Lucide) for consistency.
- Pair icon with text for status-critical actions.
