import { array, boolean, number, record, shape, text } from "../api/decode";
import { isThemePreference } from "../navigation/types";
import type { AccountUser, AuthMode, Preferences, Profile, SavedFilm } from "./types";

export function authMode(value: unknown): AuthMode {
  return value === "sign-up" || value === "recovery" ? value : "sign-in";
}
export function displayName(user: AccountUser | null): string {
  const value = user?.user_metadata?.display_name;
  return typeof value === "string" ? value : "";
}
export const profile: (value: unknown) => Profile = shape({ display_name: text, created_at: text, updated_at: text });
export function preferences(value: unknown): Preferences {
  const input = record(value);
  if (!isThemePreference(input.theme) || typeof input.shelf_motion !== "boolean") throw new Error("Invalid account preferences.");
  return { ...shape({ created_at: text, updated_at: text })(input), theme: input.theme, shelf_motion: input.shelf_motion };
}
export function savedFilm(value: unknown): SavedFilm {
  const input = record(value);
  const film_id = text(input.film_id);
  if (!film_id.trim()) throw new Error("Saved film identity is missing.");
  return {
    ...shape({ original_title: text, release_year: number, director: text, poster_url: text, created_at: text })(input),
    film_id, title: text(input.title),
  };
}
export const savedFilms = array(savedFilm);
export function readStorage<T>(key: string, fallback: T, decode: (value: unknown) => T): T {
  try {
    const stored = window.localStorage.getItem(key);
    return stored === null ? fallback : decode(JSON.parse(stored));
  } catch (_) {
    return fallback;
  }
}
export { boolean };
