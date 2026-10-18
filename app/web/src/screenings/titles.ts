// Title keys for grouping one film's listings across venues. No DOM access.
//
// Multiplexes add ratings, formats and hall names to titles: "Dune (NC16)", "Dune [IMAX]".
// Only a bracketed group made entirely of such tags is dropped. Ordinary words are never
// stripped, so "The Dreamers", "Lux Aeterna" and "Premiere" stay distinct films, and a
// bracket holding anything else ("The Kiss (くちづけ, 1957)") stays part of the title.

const TAG_WORDS = new Set([
  // Singapore classifications.
  "g", "pg", "pg13", "nc16", "m18", "r21", "tbc", "tba", "nr",
  // Formats and premium halls.
  "imax", "4dx", "3d", "2d", "hfr", "atmos", "dbox", "screenx", "ultrascreen", "lux", "dreamers",
  "premiere", "onyx", "laser", "70mm", "35mm", "4k", "digital",
  // Language versions.
  "dub", "dubbed", "sub", "subs", "subbed", "subtitled", "subtitles", "ver", "version", "eng",
  "english", "mandarin", "chinese", "cantonese", "malay", "tamil", "hindi", "telugu", "malayalam",
  "japanese", "korean", "thai", "original",
  // Event labels.
  "preview", "previews", "sneak", "sneaks", "advance", "special", "screening", "screenings", "gala",
  "qa", "rerelease", "remastered", "restored", "encore",
  // Connectives inside an all-tag group, such as "(With English Subtitles)".
  "with", "and", "in",
]);

const TAG_PAIRS = new Set([
  "gold class", "dolby atmos", "dolby cinema", "dolby vision", "ultra screen", "sold out",
  "fan screening", "opening night", "closing night",
]);

const BRACKETED = /\(([^()]*)\)|\[([^[\]]*)\]/g;

function fold(value: string): string {
  return value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

// Case, accent and punctuation-insensitive text for matching a viewer's query.
export function searchKey(value: string): string {
  return fold(value).replace(/[^\p{L}\p{M}\p{N}]+/gu, " ").trim().normalize("NFC");
}

export function isTagGroup(inner: string): boolean {
  const tokens = fold(inner)
    .split(/[\s,/+|·:;]+/)
    .map((token) => token.replace(/[^\p{L}\p{N}]/gu, ""))
    .filter(Boolean);
  if (!tokens.length) return false;
  for (let index = 0; index < tokens.length;) {
    if (index + 1 < tokens.length && TAG_PAIRS.has(`${tokens[index]} ${tokens[index + 1]}`)) {
      index += 2;
    } else if (TAG_WORDS.has(tokens[index])) {
      index += 1;
    } else {
      return false;
    }
  }
  return true;
}

export function filmKey(title: string): string {
  const stripped = fold(title).replace(BRACKETED, (match, round?: string, square?: string) =>
    isTagGroup(round ?? square ?? "") ? " " : match);
  return searchKey(stripped);
}
