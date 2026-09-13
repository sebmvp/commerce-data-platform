export type View = "overview" | "inventory" | "librarian" | "eval" | "health";
export type Environment = "demo" | "heldout" | "private";
export type GroundingStatus = "grounded" | "abstained" | "invalid";

export interface ContextObject {
  type: string;
  id: string;
  properties: Record<string, unknown>;
}

export interface ContextLink {
  type: string;
  from_ref: string;
  to_ref: string;
}

export interface ContextEvent {
  type: string;
  at: string | null;
  object_ref: string;
  source: string;
  detail?: unknown;
}

export interface MissingContext {
  concept: string;
  reason: string;
  required_for: string;
}

export interface Requirement {
  concept: string;
  present: boolean;
}

export interface EvidenceUnit {
  ref: string;
  kind: string;
  label: string;
  value?: unknown;
  object_ref?: string | null;
  provenance?: string | null;
}

export interface PolicyRef {
  id: string;
  version: string;
  category?: string;
  title?: string;
}

export interface ContextBundle {
  question: string;
  intent: string;
  as_of: string;
  objects: ContextObject[];
  relationships: ContextLink[];
  facts: Record<string, unknown>;
  metrics: Record<string, unknown>;
  events: ContextEvent[];
  applicable_rules: Array<Record<string, unknown>>;
  applicable_policies?: PolicyRef[];
  retrieved_evidence: Array<Record<string, unknown>>;
  provenance: Record<string, unknown>;
  missing_context: MissingContext[];
  sufficient: boolean;
  why: string;
  requirements?: Requirement[];
  evidence_units?: EvidenceUnit[];
  evidence_catalog?: string[];
}

export interface QuestionPlan {
  capability?: string;
  subject?: string | null;
  source?: string;
  domain?: string;
  as_of?: string | null;
}

export interface ActionSuggestion {
  action_type: string;
  target_type?: string | null;
  target_id?: string | null;
  payload?: Record<string, unknown>;
  reason?: string | null;
  recommendation?: string | null;
}

export interface ActionRecord {
  action_id: string;
  status: string;
  action_type: string;
  target_type?: string;
  target_id?: string;
  payload?: Record<string, unknown>;
  proposed_payload?: Record<string, unknown>;
  resulting_value?: Record<string, unknown>;
}

export interface ToolTraceStep {
  tool: string;
  subject?: string | null;
  ok: boolean;
  summary: string;
  detail?: string;
}

export interface LibrarianResponse {
  question?: string;
  resolved_question?: string;
  answer: string;
  abstained: boolean;
  grounding_status: GroundingStatus;
  evidence_refs: string[];
  caveats?: string[];
  suggested_action?: ActionSuggestion | null;
  plan?: QuestionPlan;
  provider?: string;
  model?: string;
  provider_kind?: string;
  real_model?: boolean;
  bundle?: ContextBundle;
  tool_trace?: ToolTraceStep[];
  policies?: PolicyRef[];
  evidence?: {
    evidence_units?: EvidenceUnit[];
    evidence_refs?: string[];
    evidence_catalog?: string[];
    missing_context?: MissingContext[];
  };
  invalid_reason?: string;
  untrusted_output?: string | null;
}

export interface RuntimeInfo {
  environment: Environment;
  world_name: string;
  as_of?: string;
  purpose?: string;
  synthetic: boolean;
  database?: string;
  model?: {
    provider: string;
    kind: "fake" | "local" | "remote";
    model: string;
    real?: boolean;
    auth_configured?: boolean;
    base_url?: string | null;
  };
}

export interface InventoryRow {
  sku: string;
  product: string;
  variant?: string | null;
  size?: string | null;
  status: string;
  category_key?: string | null;
  acquisition_cost_cny?: number | null;
  target_price_usd?: number | null;
  qty?: number;
  has_active_listing?: boolean;
}

export interface SnapshotData {
  items_total?: number;
  owned_unlisted?: number;
  listed_items?: number;
  sold_items?: number;
  capital_tied_up_cny?: number | null;
  capital_tied_up_usd_est?: number | null;
  active_listings?: number;
  stale_active_listings?: number;
  [key: string]: unknown;
}

export interface BusinessSnapshot {
  kind?: string;
  data?: SnapshotData;
  provenance?: Record<string, unknown>;
}

export interface AttentionQueueRow {
  sku: string;
  product?: string;
  item_status?: string;
  attention_reason?: string;
  listing_age_days?: number | null;
  inventory_age_days?: number | null;
  watchers?: number | null;
  offers?: number | null;
  views?: number | null;
  watch_rate?: number | null;
  listing_price_usd?: number | null;
  platform?: string | null;
  [key: string]: unknown;
}

export interface AttentionQueue {
  kind?: string;
  data?: {
    recommendations?: Array<Record<string, unknown>>;
    queue?: AttentionQueueRow[];
  };
  provenance?: Record<string, unknown>;
}

export interface ItemListing {
  listing_id?: string;
  platform?: string;
  status?: string;
  price_usd?: number | null;
  listed_at?: string | null;
  watchers?: number | null;
  views?: number | null;
  offers?: number | null;
  watch_rate?: number | null;
  listing_age_days?: number | null;
  [key: string]: unknown;
}

export interface ItemPayload {
  kind?: string;
  data?: {
    item?: Record<string, unknown>;
    listings?: ItemListing[];
    orders?: Array<Record<string, unknown>>;
    engagement?: Array<Record<string, unknown>>;
    notes?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };
  provenance?: Record<string, unknown>;
}

export interface ItemHistory {
  kind?: string;
  data?: {
    timeline?: Array<Record<string, unknown>>;
    engagement?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };
  provenance?: Record<string, unknown>;
}

export interface EvalLayerReport {
  total?: number;
  passed?: number;
  failed?: number;
  skipped?: number;
  cases?: Array<{
    id?: string;
    question?: string;
    passed?: boolean;
    skipped?: boolean;
  }>;
  lexical?: { passed?: number; total?: number };
  engine?: { passed?: number; total?: number };
}

export interface TrustReport {
  ok?: boolean;
  reasons?: string[];
  [key: string]: unknown;
}

export interface CompletenessReport {
  counts?: Record<string, number>;
  coverage?: Array<{ category?: string; status?: string; detail?: string }>;
  latest_ingest?: Record<string, unknown>;
  world_as_of?: string;
  seed?: number;
  missing_source_systems?: string[];
}

export interface IngestRun {
  source?: string;
  status?: string;
  started_at?: string;
  run_id?: string;
  rows_loaded?: number;
  rows_rejected?: number;
}
