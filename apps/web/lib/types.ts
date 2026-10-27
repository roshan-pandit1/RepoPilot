export type Repository = { id: string; full_name: string; enabled: boolean };
export type Issue = { id: string; number: number; title: string; state: "open" | "closed"; updated_at: string; ingestion_status: string };
export type IssuePage = { items: Issue[]; ingestion: Record<"pending" | "processed" | "ignored" | "failed", number> };
