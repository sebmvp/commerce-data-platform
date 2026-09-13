export type Tab = "overview" | "inventory" | "context" | "eval" | "health";
export type Environment = "demo" | "heldout" | "private";

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
  applicable_policies?: Array<Record<string, unknown>>;
  retrieved_evidence: Array<Record<string, unknown>>;
  provenance: Record<string, unknown>;
  missing_context: MissingContext[];
  sufficient: boolean;
  why: string;
  requirements?: Requirement[];
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
