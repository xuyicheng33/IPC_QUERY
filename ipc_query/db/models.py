"""
数据模型定义

定义系统中所有数据库表的模型类。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Document:
    """PDF文档模型"""

    id: int | None = None
    pdf_name: str = ""
    pdf_path: str = ""
    miner_dir: str = ""
    created_at: str = ""

    @classmethod
    def from_row(cls, row: dict[str, Any] | None) -> "Document | None":
        if row is None:
            return None
        return cls(
            id=row.get("id"),
            pdf_name=row.get("pdf_name", ""),
            pdf_path=row.get("pdf_path", ""),
            miner_dir=row.get("miner_dir", ""),
            created_at=row.get("created_at", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pdf_name": self.pdf_name,
            "pdf_path": self.pdf_path,
            "miner_dir": self.miner_dir,
            "created_at": self.created_at,
        }


@dataclass
class Page:
    """页面模型"""

    id: int | None = None
    document_id: int = 0
    page_num: int = 0
    figure_code: str | None = None
    figure_label: str | None = None
    date_text: str | None = None
    page_token: str | None = None
    rf_text: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any] | None) -> "Page | None":
        if row is None:
            return None
        return cls(
            id=row.get("id"),
            document_id=row.get("document_id", 0),
            page_num=row.get("page_num", 0),
            figure_code=row.get("figure_code"),
            figure_label=row.get("figure_label"),
            date_text=row.get("date_text"),
            page_token=row.get("page_token"),
            rf_text=row.get("rf_text"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "page_num": self.page_num,
            "figure_code": self.figure_code,
            "figure_label": self.figure_label,
            "date_text": self.date_text,
            "page_token": self.page_token,
            "rf_text": self.rf_text,
        }


@dataclass
class Part:
    """零件模型"""

    id: int | None = None
    document_id: int = 0
    page_num: int = 0
    page_end: int = 0
    extractor: str = "pdf_coords"
    meta_data_raw: str | None = None
    figure_code: str | None = None
    fig_item_raw: str | None = None
    fig_item_no: str | None = None
    fig_item_no_source: str | None = None
    not_illustrated: int = 0
    part_number_cell: str | None = None
    part_number_extracted: str | None = None
    part_number_canonical: str | None = None
    pn_corrected: int = 0
    pn_method: str | None = None
    pn_best_similarity: float | None = None
    pn_needs_review: int = 0
    correction_note: str | None = None
    row_kind: str = "part"
    nom_level: int = 0
    nomenclature_clean: str | None = None
    parent_part_id: int | None = None
    attached_to_part_id: int | None = None
    nomenclature: str | None = None
    effectivity: str | None = None
    units_per_assy: str | None = None
    miner_table_img_path: str | None = None

    # 关联数据（非数据库字段）
    pdf_name: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any] | None) -> "Part | None":
        if row is None:
            return None
        return cls(
            id=row.get("id"),
            document_id=row.get("document_id", 0),
            page_num=row.get("page_num", 0),
            page_end=row.get("page_end", 0),
            extractor=row.get("extractor", "pdf_coords"),
            meta_data_raw=row.get("meta_data_raw"),
            figure_code=row.get("figure_code"),
            fig_item_raw=row.get("fig_item_raw"),
            fig_item_no=row.get("fig_item_no"),
            fig_item_no_source=row.get("fig_item_no_source"),
            not_illustrated=row.get("not_illustrated", 0),
            part_number_cell=row.get("part_number_cell"),
            part_number_extracted=row.get("part_number_extracted"),
            part_number_canonical=row.get("part_number_canonical"),
            pn_corrected=row.get("pn_corrected", 0),
            pn_method=row.get("pn_method"),
            pn_best_similarity=row.get("pn_best_similarity"),
            pn_needs_review=row.get("pn_needs_review", 0),
            correction_note=row.get("correction_note"),
            row_kind=row.get("row_kind", "part"),
            nom_level=row.get("nom_level", 0),
            nomenclature_clean=row.get("nomenclature_clean"),
            parent_part_id=row.get("parent_part_id"),
            attached_to_part_id=row.get("attached_to_part_id"),
            nomenclature=row.get("nomenclature"),
            effectivity=row.get("effectivity"),
            units_per_assy=row.get("units_per_assy"),
            miner_table_img_path=row.get("miner_table_img_path"),
            pdf_name=row.get("pdf_name"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "page_num": self.page_num,
            "page_end": self.page_end,
            "extractor": self.extractor,
            "figure_code": self.figure_code,
            "fig_item_no": self.fig_item_no,
            "not_illustrated": bool(self.not_illustrated),
            "part_number": self.part_number_canonical,
            "pn_corrected": bool(self.pn_corrected),
            "pn_method": self.pn_method,
            "nom_level": self.nom_level,
            "nomenclature": self.nomenclature,
            "nomenclature_clean": self.nomenclature_clean,
            "effectivity": self.effectivity,
            "units_per_assy": self.units_per_assy,
            "pdf_name": self.pdf_name,
        }

    def to_api_dict(self) -> dict[str, Any]:
        """转换为API响应格式"""
        return {
            "id": self.id,
            "pn": self.part_number_canonical,
            "pn_cell": self.part_number_cell,
            "pn_corrected": bool(self.pn_corrected),
            "nom": self.nomenclature,
            "nom_clean": self.nomenclature_clean,
            "nom_level": self.nom_level,
            "fig": self.figure_code,
            "fig_item": self.fig_item_no,
            "eff": self.effectivity,
            "units": self.units_per_assy,
            "page": self.page_num,
            "pdf": self.pdf_name,
        }


@dataclass
class XRef:
    """交叉引用模型"""

    id: int | None = None
    part_id: int = 0
    kind: str = ""
    target: str = ""

    @classmethod
    def from_row(cls, row: dict[str, Any] | None) -> "XRef | None":
        if row is None:
            return None
        return cls(
            id=row.get("id"),
            part_id=row.get("part_id", 0),
            kind=row.get("kind", ""),
            target=row.get("target", ""),
        )


@dataclass
class Alias:
    """别名模型"""

    id: int | None = None
    part_id: int = 0
    alias_type: str = ""
    alias_value: str = ""

    @classmethod
    def from_row(cls, row: dict[str, Any] | None) -> "Alias | None":
        if row is None:
            return None
        return cls(
            id=row.get("id"),
            part_id=row.get("part_id", 0),
            alias_type=row.get("alias_type", ""),
            alias_value=row.get("alias_value", ""),
        )


@dataclass
class SearchResult:
    """搜索结果模型"""

    parts: list[Part] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_more: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "results": [p.to_api_dict() for p in self.parts],
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "has_more": self.has_more,
        }


@dataclass
class PartDetail:
    """零件详情模型（含层级信息）"""

    part: Part
    parents: list[Part] = field(default_factory=list)  # 父辈链
    siblings: list[Part] = field(default_factory=list)  # 同级
    children: list[Part] = field(default_factory=list)  # 子级
    xrefs: list[XRef] = field(default_factory=list)  # 交叉引用

    def to_dict(self) -> dict[str, Any]:
        return {
            "part": self.part.to_api_dict(),
            "parents": [p.to_api_dict() for p in self.parents],
            "siblings": [p.to_api_dict() for p in self.siblings],
            "children": [p.to_api_dict() for p in self.children],
            "xrefs": [{"kind": x.kind, "target": x.target} for x in self.xrefs],
        }
