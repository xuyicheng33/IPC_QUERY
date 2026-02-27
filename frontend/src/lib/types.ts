export type MatchMode = "pn" | "term" | "all";

export type SearchState = {
  q: string;
  match: MatchMode;
  page: number;
  include_notes: boolean;
  source_dir: string;
  source_pdf: string;
};

export type SearchResultItem = {
  id: number;
  part_number_canonical?: string | null;
  part_number_cell?: string | null;
  source_relative_path?: string | null;
  source_pdf?: string | null;
  page_num?: number | null;
  nomenclature_preview?: string | null;
};

export type SearchResponse = {
  results: SearchResultItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
  match: MatchMode;
  source_pdf?: string;
  source_dir?: string;
};

export type DocumentItem = {
  pdf_name?: string;
  relative_path?: string;
  relative_dir?: string;
};

export type LegacyHistoryItem = {
  q: string;
  match: MatchMode;
  include_notes: boolean;
  source_dir: string;
  source_pdf: string;
  ts: number;
};

export type LegacyFavoriteItem = {
  id: number;
  pn: string;
  source: string;
  page: number;
};
