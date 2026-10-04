import type { Film } from "../api/models";
import type { ThemePreference } from "../navigation/types";

export type AuthMode = "sign-in" | "sign-up" | "recovery";
export interface AccountUser { id: string; email?: string | null; provider?: string; user_metadata?: Record<string, unknown> }
export interface Profile { display_name?: string | null; created_at?: string; updated_at?: string }
export interface Preferences { theme: ThemePreference; shelf_motion: boolean; created_at?: string; updated_at?: string }
export interface SavedFilm { film_id: string; title: string; original_title?: string | null; release_year?: number | null; director?: string | null; poster_url?: string | null; created_at?: string }
export interface AccountSettings { profile: Profile | null; preferences: Preferences | null }
export interface AuthAdapter {
  ready: Promise<void>;
  configured(): boolean;
  open(mode?: AuthMode): boolean;
  currentUser(): AccountUser | null;
  accessToken(): Promise<string | null>;
  authorisationHeaders(): Promise<Record<string, string>>;
  signOut(): Promise<void>;
  currentProfile?(): Profile | null;
  currentPreferences?(): Preferences | null;
  updateDisplayName?(name: string): Promise<Profile | null>;
  updatePassword?(password: string): Promise<void>;
  updatePreferences?(changes: Partial<Preferences>): Promise<Preferences | null>;
  refreshAccountSettings?(): Promise<AccountSettings>;
  savedFilms?(): SavedFilm[];
  refreshSavedFilms?(): Promise<SavedFilm[]>;
  isFilmSaved?(filmId: string): boolean;
  saveFilm?(film: Film): Promise<SavedFilm[]>;
  removeSavedFilm?(filmId: string): Promise<SavedFilm[]>;
}
export type IntegrationProvider = "deepseek" | "youtube";
