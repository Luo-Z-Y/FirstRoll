// Provider names can contain scraped markup or raw IDs; retain the existing display filters.
export function displayCrewNames(values: unknown): string[] {
  const forbidden = /mw-parser-output|\.mw-|line-height|list-style|margin:|padding:|display:|font-size:|@media|!important|var\(|[{}<>]/i;
  const names = (Array.isArray(values) ? values : [])
    .filter((value) => typeof value === "string")
    .map((value) => value.trim())
    .filter((value) => value.length >= 2 && value.length <= 120)
    .filter((value) => !/^Q\d+$/i.test(value))
    .filter((value) => /\p{L}/u.test(value) && !forbidden.test(value))
    .filter((value) => (value.match(/[,:;]/g) || []).length <= 2);
  return [...new Set(names)];
}

export function displayCrew(values: unknown, fallback = "Not supplied"): string {
  return displayCrewNames(values).join(", ") || fallback;
}

export function firstCrewName(values: unknown, fallback = "Not supplied"): string {
  return displayCrewNames(values)[0] || fallback;
}
