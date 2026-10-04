export type ThemePreference = "system" | "light" | "dark";
export type ProductView = "discovery" | "analyse" | "festivals" | "settings";

export function isThemePreference(value: unknown): value is ThemePreference {
  return value === "system" || value === "light" || value === "dark";
}

export function isProductView(value: unknown): value is ProductView {
  return value === "discovery" || value === "analyse" || value === "festivals" || value === "settings";
}

export interface ProductViewOptions {
  captureCurrent?: boolean;
  persist?: boolean;
  restoreScroll?: boolean;
}

// A narrow structural contract: navigation does not need the dossier or clip state.
export interface NavigationContext {
  state: { productView: ProductView; viewScroll: Record<ProductView, number> };
  refs: {
    buildIdentity: HTMLElement | null;
    videoAnalysisComingSoon: HTMLElement;
    themeToggle: HTMLButtonElement;
    productViews: Record<ProductView, HTMLElement>;
    productNav: HTMLElement[];
  };
  runtimeConfig: {
    buildId: string; buildChannel: string; buildCommit: string;
    accountUi: boolean; videoAnalysisEnabled: boolean;
  };
  systemThemeMedia: Pick<MediaQueryList, "matches">;
}

export interface NavigationServices {
  session: { persistProductSession(): void };
}
