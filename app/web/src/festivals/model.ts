import type { Festival } from "./data";
export interface Point { x: number; y: number }
export interface MapView extends Point { w: number; h: number }
export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
export const SOON_DAYS = 60;
  // Day-of-year arithmetic uses a fixed non-leap year so windows stay comparable across years.
export const CUMULATIVE = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365];
export const MAP_TOP = 16;
export const MAP_HEIGHT = 396;
export const MAX_ZOOM = 8;
export const BUTTON_ZOOM = 1.6;
export const DRAG_THRESHOLD = 4;


export function dayOfYear([month, day]: [number, number]) {
    return CUMULATIVE[month - 1] + day;
  }

export function todayOfYear(now = new Date()) {
    const month = now.getMonth() + 1;
    // 29 February counts as the 28th.
    return dayOfYear([month, Math.min(now.getDate(), CUMULATIVE[month] - CUMULATIVE[month - 1])]);
  }

export function project(lat: number, lon: number) {
    return { x: 500 + (lon * 1000) / 360, y: 250 - (lat * 1000) / 360 };
  }

export function status(festival: Festival, today: number) {
    const start = dayOfYear(festival.start);
    const end = dayOfYear(festival.end);
    if (today >= start && today <= end) return { key: "now", label: "Within typical window", days: 0 };
    const until = (start - today + 365) % 365;
    if (until <= SOON_DAYS) return { key: "soon", label: `Typical window in ~${until} days`, days: until };
    return { key: "later", label: `Typical window in ~${Math.max(1, Math.round(until / 30.4))} months`, days: until };
  }

export function inMonth(festival: Festival, month: number) {
    if (!month) return true;
    const first = CUMULATIVE[month - 1] + 1;
    const last = CUMULATIVE[month];
    return dayOfYear(festival.start) <= last && dayOfYear(festival.end) >= first;
  }

export function formatWindow(festival: Festival) {
    const [sm, sd] = festival.start;
    const [em, ed] = festival.end;
    if (sm === em && sd === ed) return `${sd} ${MONTHS[sm - 1]}`;
    return sm === em
      ? `${sd}–${ed} ${MONTHS[sm - 1]}`
      : `${sd} ${MONTHS[sm - 1]} – ${ed} ${MONTHS[em - 1]}`;
  }
