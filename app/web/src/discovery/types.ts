// A display boundary, not a replacement for API/session validation.
// Optional fields reflect incomplete catalogue records; IDs remain the stable identity.
export interface FilmSummary {
  id: string;
  title?: string | null;
  original_title?: string | null;
  alternative_titles?: string[];
  year?: number | null;
  release_years?: number[];
  runtime_minutes?: number | null;
  directors?: string[];
  poster_url?: string | null;
}

// The normalised search form/storage shape, separate from provider film metadata.
export interface DiscoveryQuery { title: string; year: string; director: string }
