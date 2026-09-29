export interface ResearchJournalEntry {
  id: string;
  title: string;
  content: string;
  tags: string[];
  linked_run_ids?: string[];
  created_at: string;
  updated_at: string;
}

export interface ResearchJournalTag {
  tag: string;
  count: number;
}

export interface ResearchJournalDraft {
  title: string;
  content: string;
  tags?: string[];
  linked_run_ids?: string[];
}
