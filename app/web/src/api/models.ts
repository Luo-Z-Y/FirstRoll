import { array, boolean, dictionary, number, record, shape, text } from "./decode";
export const source = shape({
    name: text, url: text, licence: text
});
export const review = shape({
    source_id: text, title: text, author: text, url: text, summary: text, excerpt: text, language: text, rating_label: text, source
});
export const claim = shape({
    claim_id: text, source_id: text, critic_claim: text, lens_tags: array(text), missing_fields: array(text), extraction_confidence: text, short_source_excerpt: text, scene_or_sequence: text, described_observation: text
});
export const criticismBundle = shape({
    provider: text, notice: text, claim_status: text, reviews: array(review), claims: array(claim)
});
export const provider = shape({
    state: text, installed: boolean, configured: boolean
});
export const video = shape({
    title: text, url: text, embed_url: text, category: text, platform: text, relevance: text, duration_seconds: number, creator: text
});
export const videoBundle = shape({
    videos: array(video), notice: text
});
export const award = shape({
    name: text, title: text, url: text, description: text, category: text, year: number
});
const filmFields = shape({
    title: text, original_title: text, provider_id: text, alternative_titles: array(text), year: number, matched_year: number,
    release_years: array(number), runtime_minutes: number, directors: array(text), poster_url: text, poster_source: source,
    backdrop_url: text, overview: text, source, overview_source: source, genres: array(text), awards: array(award),
    credits: shape({
        directors: array(text), writers: array(text), producers: array(text), cinematographers: array(text), editors: array(text)
    }),
    crew_sources: array(source), reviews: array(review),
    critical_research: shape({
        providers: dictionary(provider), bundles: dictionary(criticismBundle), bundle: criticismBundle
    }),
    video_sources: shape({
        providers: dictionary(provider), bundle: videoBundle
    }),
});
export function film(value: unknown) {
    const input = record(value);
    const id = text(input.id);
    if (!id.trim())
        throw new Error("The film identifier is missing.");
    return {
        ...filmFields(input), id
    };
}
export const discoveryQuery = shape({
    title: text, q: text, year: (value: unknown) => typeof value === "number" ? String(number(value)) : text(value), director: text
});
export const searchResult = shape({
    results: array(film), query: discoveryQuery, mode: text
});
export const relatedResult = shape({
    same_director: array(film), state: text
});
export const statusResult = shape({
    mode: text, local_library: shape({
        index: shape({
            warmup: shape({
                state: text
            })
        })
    })
});
export const receptionResult = shape({
    scores: array(shape({
        provider: text, score: number, scale: number, votes: number
    })),
    aggregate: shape({
        score: number, method: text
    }), providers: dictionary(provider),
});
export const quota = shape({
    unlimited: boolean, reset_at: text, user: shape({
        remaining: number, limit: number
    }), global: shape({
        remaining: number, limit: number
    })
});
export const selection = shape({
    candidate_items: number, omitted_items: number, selected_characters: number, omission_reasons: dictionary(number)
});
export const studySource = shape({
    id: text, title: text, locator: text, page: number, excerpt: text
});
export const attributedSource = shape({
    evidence_id: text, title: text, locator: text, evidence_type: text, content: text, source_url: text
});
export const sectionQuality = shape({
    issues: array(text)
});
export const studySection = shape({
    source_ids: array(text), critic_claim_ids: array(text), attributed_source_ids: array(text), critic_reports: text, theory_explains: text, hypothesis: text, analysis: text, mechanism: text, alternative_reading: text
});
export const study = shape({
    model: text, title: text, central_argument: text, creator_intent_boundary: text, grounding_notice: text,
    sections: array(studySection), sources: array(studySource), critical_claims: array(claim), attributed_sources: array(attributedSource), next_viewing: array(text),
    quality: shape({
        status: text, score: number, repair_attempted: boolean, sections: array(sectionQuality)
    }),
    evidence_packet: shape({
        retrieval: shape({
            theory_selection: selection, critical_selection: selection, attributed_selection: selection, plan: array(shape({
                origin: text, lens: text, query: text
            })), method: text, candidate_count: number, embedding: shape({
                state: text
            })
        })
    }),
    packet_quality: shape({
        issues: array(text), status: text, provenance: shape({
            completeness_ratio: number
        }), duplication: shape({
            duplicate_ratio: number
        }), focus_relevance: shape({
            relevance_ratio: number
        })
    }),
    observability: shape({
        stages: array(shape({
            name: text, status: text, duration_ms: number
        })), counts: shape({
            prompt_tokens: number
        })
    }),
});
export const studyResult = shape({
    study, quota
});
export type Film = Omit<ReturnType<typeof film>, keyof import("../discovery/types").FilmSummary | "poster_source"> & import("../discovery/types").FilmSummary & {
    poster_source?: Source | null;
};
export type SearchResult = Omit<ReturnType<typeof searchResult>, "results"> & {
    results?: Film[];
};
export type RelatedResult = ReturnType<typeof relatedResult>;
export type Review = ReturnType<typeof review>;
export type Claim = ReturnType<typeof claim>;
export type CriticismBundle = ReturnType<typeof criticismBundle>;
export type Providers = Record<string, ReturnType<typeof provider>>;
export type Video = ReturnType<typeof video>;
export type VideoBundle = ReturnType<typeof videoBundle>;
export type Award = ReturnType<typeof award>;
export type Source = Omit<ReturnType<typeof source>, "url"> & {
    url?: string | null;
};
export type Study = ReturnType<typeof study>;
export type Quota = ReturnType<typeof quota>;
export type Selection = ReturnType<typeof selection>;
export type StudySource = ReturnType<typeof studySource>;
export type AttributedSource = ReturnType<typeof attributedSource>;
export type StudySection = ReturnType<typeof studySection>;
export type SectionQuality = ReturnType<typeof sectionQuality>;
