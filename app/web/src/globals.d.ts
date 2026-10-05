import type { AccountSettings, AccountUser, AuthAdapter, IntegrationProvider, SavedFilm } from "./accounts/types";
import type { ProductView, ThemePreference } from "./navigation/types";

export interface RuntimeConfiguration {
  apiBase?: string; publicMode?: boolean; videoAnalysisEnabled?: boolean;
  supabaseUrl?: string; supabasePublishableKey?: string;
  buildId?: string; buildNumber?: number; buildChannel?: string; buildCommit?: string;
  localTestAccountEmail?: string;
}
declare global {
  interface Window {
    FIRSTROLL_CONFIG?: Readonly<RuntimeConfiguration>;
    FirstRollAuth?: Readonly<AuthAdapter>;
    FirstRollUI?: Readonly<{ setThemePreference(value: unknown): void; themePreference(): ThemePreference }>;
    FirstRollIntegrations?: Readonly<{
      configured(provider: IntegrationProvider): boolean;
      requestHeaders(provider: IntegrationProvider): Record<string, string>;
    }>;
  }
  interface DocumentEventMap {
    "firstroll:auth-changed": CustomEvent<{ configured: boolean; user: AccountUser | null }>;
    "firstroll:account-data-changed": CustomEvent<{ savedFilms: SavedFilm[] }>;
    "firstroll:account-settings-changed": CustomEvent<AccountSettings>;
    "firstroll:integration-changed": CustomEvent<{ provider: IntegrationProvider }>;
    "firstroll:view-changed": CustomEvent<{ view: ProductView }>;
  }
  interface HTMLElementEventMap {
    "firstroll:select-film": CustomEvent<{ filmId?: string }>;
  }
}
