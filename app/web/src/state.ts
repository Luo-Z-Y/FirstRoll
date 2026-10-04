import type { Film, RelatedResult } from "./api/models";
import type { DiscoveryQuery } from "./discovery/types";
import type { ProductView } from "./navigation/types";
import type { ResearchProgress } from "./study/progress";

export interface Archive {
  primary: Film;
  directorWorks: Film[];
  relevant: Film[];
}
export interface AppState {
  productView: ProductView;
  viewScroll: Record<ProductView, number>;
  discovery: {
    results: Film[];
    selectedFilm: Film | null;
    detailFilmId: string | null;
    detailController: AbortController | null;
    archive: Archive | null;
    archiveSelectionId: string | null;
    lastQuery: DiscoveryQuery | null;
    resultStage: string;
    shelfState: string;
    mode: string;
    activeCriticismProvider: string | null;
    recentSearches: DiscoveryQuery[];
    relatedFilmCache: Map<string, RelatedResult>;
    searchRequestId: number;
    searchController: AbortController | null;
    shelfRequestId: number;
    shelfRequestControllers: Set<AbortController>;
    studyRequestId: number;
    studyController: AbortController | null;
    studyProgress: ResearchProgress[];
  };
}
