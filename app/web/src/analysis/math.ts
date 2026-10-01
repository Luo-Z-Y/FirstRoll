import type { RGB } from "./types";

// Numerical helpers shared by the local analysis algorithms and their renderers.
export function rgbDistance(a: RGB, b: RGB): number {
  const dr = a[0] - b[0];
  const dg = a[1] - b[1];
  const db = a[2] - b[2];
  return Math.sqrt(dr * dr + dg * dg + db * db);
}

export function l1Dist(a: readonly number[], b: readonly number[]): number {
  let sum = 0;
  for (let i = 0; i < a.length; i += 1) {
    sum += Math.abs(a[i] - b[i]);
  }
  return sum;
}

export function avg(arr: readonly number[]): number {
  if (!arr || !arr.length) return 0;
  return arr.reduce((s, x) => s + x, 0) / arr.length;
}

export function std(arr: readonly number[]): number {
  if (!arr || arr.length < 2) return 0;
  const m = avg(arr);
  const variance = avg(arr.map((x) => (x - m) ** 2));
  return Math.sqrt(variance);
}

export function averageRgb(list: readonly RGB[]): RGB {
  if (!list.length) return [0, 0, 0];
  const total = list.reduce<[number, number, number]>(
    (acc, rgb) => [acc[0] + rgb[0], acc[1] + rgb[1], acc[2] + rgb[2]],
    [0, 0, 0],
  );
  return [total[0] / list.length, total[1] / list.length, total[2] / list.length];
}

export function pct(n: number, d: number): number {
  if (!d) return 0;
  return Math.round((n / d) * 100);
}

export function rgbToHue(rgb: RGB): number {
  let [r, g, b] = rgb.map((v) => v / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const diff = max - min;

  if (diff === 0) return 0;

  let hue;
  switch (max) {
    case r:
      hue = ((g - b) / diff) % 6;
      break;
    case g:
      hue = (b - r) / diff + 2;
      break;
    default:
      hue = (r - g) / diff + 4;
      break;
  }

  const deg = hue * 60;
  return deg < 0 ? deg + 360 : deg;
}

export function rgbToCss(rgb: RGB): string {
  const [r, g, b] = rgb.map((v) => Math.max(0, Math.min(255, Math.round(v))));
  return `rgb(${r}, ${g}, ${b})`;
}

export function rgbLabel(rgb: RGB): string {
  const [r, g, b] = rgb.map((v) => Math.round(v));
  return `RGB(${r}, ${g}, ${b})`;
}
