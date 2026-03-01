export type MatchMode = "pn" | "term" | "all";
export type SortMode = "relevance" | "name";

export type SearchState = {
  q: string;
  match: MatchMode;
  sort: SortMode;
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
  nomenclature_hit_snippet?: string | null;
};

export type SearchResponse = {
  results: SearchResultItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
  match: MatchMode;
  sort?: SortMode;
  source_pdf?: string;
  source_dir?: string;
};

export type DocumentItem = {
  pdf_name?: string;
  relative_path?: string;
  relative_dir?: string;
};

export type DocsTreeDirectory = {
  name: string;
  path: string;
};

export type DocsTreeFile = {
  name: string;
  relative_path: string;
  indexed: boolean;
  document?: DocumentItem;
};

export type DbListItem = {
  name: string;
  relative_path: string;
  indexed: boolean;
  is_dir: boolean;
  document?: DocumentItem;
};

export type DocsTreeResponse = {
  path: string;
  directories: DocsTreeDirectory[];
  files: DocsTreeFile[];
};

export type PartPayload = {
  id?: number;
  pn?: string;
  part_number_canonical?: string;
  part_number_cell?: string;
  source_relative_path?: string;
  source_pdf?: string;
  pdf?: string;
  page?: number;
  page_num?: number;
  page_end?: number;
  fig?: string;
  figure_code?: string;
  fig_item?: string;
  units?: string;
  units_per_assy?: string;
  eff?: string;
  effectivity?: string;
  figure_label?: string;
  date_text?: string;
  page_token?: string;
  rf_text?: string;
  nom?: string;
  nomenclature?: string;
  nomenclature_clean?: string;
};

export type HierarchyItem = {
  id: number;
  pn?: string;
  part_number?: string;
};

export type PartDetailResponse = {
  part?: PartPayload;
  parents?: HierarchyItem[];
  siblings?: HierarchyItem[];
  children?: HierarchyItem[];
};

export type JobStatus = "queued" | "running" | "success" | "failed";

export type ImportJob = {
  job_id: string;
  filename?: string;
  relative_path?: string;
  status?: JobStatus;
  error?: string;
};

export type ScanJob = {
  job_id: string;
  path?: string;
  status?: JobStatus;
  error?: string;
};

export type WriteAuthMode = "disabled" | "api_key";

export type CapabilitiesResponse = {
  import_enabled: boolean;
  scan_enabled: boolean;
  import_reason: string;
  scan_reason: string;
  write_auth_mode: WriteAuthMode;
  write_auth_required: boolean;
  legacy_folder_routes_enabled: boolean;
  directory_policy: "single_level";
  path_policy_warning_count: number;
};

export type RenameDocRequest = {
  path: string;
  new_name: string;
};

export type RenameDocResponse = {
  updated: boolean;
  old_path: string;
  new_path: string;
  pdf_name: string;
};

export type MoveDocRequest = {
  path: string;
  target_dir: string;
};

export type MoveDocResponse = {
  updated: boolean;
  old_path: string;
  new_path: string;
  pdf_name: string;
};

export type DbActionPhase = "idle" | "pending" | "success" | "error";
export type DbGlobalActionKey = "upload" | "batchDelete" | "rescan" | "createFolder";
export type DbGlobalActionState = Record<
  DbGlobalActionKey,
  {
    phase: DbActionPhase;
    message: string;
    updatedAt: number;
    error?: string;
  }
>;

export type DbRowActionState = {
  mode: "normal" | "renaming" | "moving";
  value: string;
  error: string;
  phase: DbActionPhase;
};
