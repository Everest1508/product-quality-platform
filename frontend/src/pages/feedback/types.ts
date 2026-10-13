export type SurveyItem = {
  id: number; name: string; description: string; type: string; type_label: string; status: string; status_label: string;
  product: { id: number; name: string }; response_count: number; created_at: string; url: string;
};
export type SurveyListResponse = {
  items: SurveyItem[];
  page: { number: number; num_pages: number; count: number; per_page: number };
};
export type SurveyMeta = { types: [string, string][]; statuses: [string, string][]; products: { id: number; name: string }[] };
export type SurveyDetail = {
  survey: SurveyItem & { created_by: string; public_path: string; avg_score: number | null; nps: number | null };
  distribution: { score: number; count: number; label: string }[];
  responses: { id: number; score: number; label: string; comment: string; contact_name: string; created_at: string }[];
  message?: string;
};
export type CsHub = {
  total_responses: number;
  avg_all: number | null;
  active_surveys: SurveyItem[];
  sentiment_total: number;
  sentiment: { id: number; product: string; source: string; score: number; recorded_at: string }[];
  product_stats: { product: { id: number; name: string; slug: string }; survey_count: number; response_count: number; avg_score: number | null; dashboard_url: string }[];
};
export type PublicSurvey = { id: number; name: string; description: string; type: string; product: string; scores: number[] };
