import { FESTIVALS } from "./data";
import { LAND_PATH } from "./land";
import { escapeHtml } from "../shared/html";
import { MONTHS, MONTH_NAMES, CUMULATIVE, MAP_TOP, MAP_HEIGHT, MAX_ZOOM,
  BUTTON_ZOOM, DRAG_THRESHOLD, dayOfYear, todayOfYear, project, status, inMonth, formatWindow } from "./model";
import type { MapView, Point } from "./model";

// Optional self-contained atlas: no credentials, provider requests or map service.
export function mountFestivalAtlas(section: HTMLElement) {
  const refs = {
    months: section.querySelector<HTMLElement>("[data-festival-months]"),
    map: section.querySelector<HTMLElement>("[data-festival-map]"),
    detail: section.querySelector<HTMLElement>("[data-festival-detail]"),
    calendar: section.querySelector<HTMLElement>("[data-festival-calendar]"),
    summary: section.querySelector<HTMLElement>("[data-festival-summary]"),
  };
  if (!refs.months || !refs.map || !refs.detail || !refs.calendar || !refs.summary) return;
  const { months, map, detail, calendar, summary } = refs;
  // The map view is a viewBox window onto the 1000-wide plane; zoom is 1000 / width.
  const state: { month: number; selected: string | null; view: MapView } = { month: 0, selected: null, view: { x: 0, y: MAP_TOP, w: 1000, h: MAP_HEIGHT } };
  const gesture: {
    pointers: Map<number, Point>;
    start: (Point & { view: MapView; distance: number }) | null;
    dragged: boolean;
  } = { pointers: new Map(), start: null, dragged: false };

  function sortedFestivals(today: number) {
    return FESTIVALS.slice().sort((a, b) => status(a, today).days - status(b, today).days
      || dayOfYear(a.start) - dayOfYear(b.start));
  }

  function renderMonths() {
    const buttons = [`<button type="button" data-festival-month="0" aria-pressed="${state.month === 0}">All year</button>`]
      .concat(MONTHS.map((label, index) => {
        const month = index + 1;
        const count = FESTIVALS.filter((festival) => inMonth(festival, month)).length;
        return `<button type="button" data-festival-month="${month}" aria-pressed="${state.month === month}" aria-label="${MONTH_NAMES[index]}, ${count} ${count === 1 ? "festival" : "festivals"}">${label}<span aria-hidden="true">${count}</span></button>`;
      }));
    months.innerHTML = buttons.join("");
  }

  function renderMap(today: number) {
    const pins = sortedFestivals(today).slice().reverse().map((festival) => {
      const { x, y } = project(festival.lat, festival.lon);
      const current = status(festival, today);
      const dimmed = !inMonth(festival, state.month);
      const selected = state.selected === festival.id;
      const classes = ["festival-pin", `is-${current.key}`, festival.kind === "awards" ? "is-awards" : "", dimmed ? "is-dimmed" : "", selected ? "is-selected" : ""].join(" ").trim();
      return `<g class="${classes}" data-x="${x.toFixed(1)}" data-y="${y.toFixed(1)}" data-festival-id="${festival.id}" role="button" tabindex="${dimmed ? -1 : 0}" aria-label="${escapeHtml(`${festival.name}, ${festival.city}, ${formatWindow(festival)}`)}" aria-pressed="${selected}">
        <circle class="festival-pin-halo" r="11"></circle>
        <circle class="festival-pin-dot" r="4.5"></circle>
        <title>${escapeHtml(`${festival.name} · ${festival.city} · ${formatWindow(festival)}`)}</title>
      </g>`;
    }).join("");
    map.innerHTML = `<div class="festival-zoom" role="group" aria-label="Map zoom">
        <button type="button" data-festival-zoom="in" aria-label="Zoom in">+</button>
        <button type="button" data-festival-zoom="out" aria-label="Zoom out">−</button>
        <button type="button" data-festival-zoom="reset" aria-label="Reset map view">⤢</button>
      </div>
      <svg viewBox="0 ${MAP_TOP} 1000 ${MAP_HEIGHT}" role="group" aria-label="World map of film festivals; scroll, pinch or double-click to zoom and drag to pan" preserveAspectRatio="xMidYMid meet">
      <path class="festival-graticule" d="${graticule()}"></path>
      <path class="festival-land" d="${LAND_PATH}"></path>
      ${pins}
    </svg>`;
    applyView();
  }

  function zoomLevel() {
    return 1000 / state.view.w;
  }

  // Keep the window inside the map plane so the world can never be panned out of sight.
  function clampView(view: Pick<MapView, 'w' | 'x' | 'y'>) {
    const w = Math.min(1000, Math.max(1000 / MAX_ZOOM, view.w));
    const h = (w * MAP_HEIGHT) / 1000;
    return {
      w,
      h,
      x: Math.min(1000 - w, Math.max(0, view.x)),
      y: Math.min(MAP_TOP + MAP_HEIGHT - h, Math.max(MAP_TOP, view.y)),
    };
  }

  // Pins are counter-scaled so they keep their on-screen size at every zoom level.
  function applyView() {
    const svg = map.querySelector("svg");
    if (!svg) return;
    const { x, y, w, h } = state.view;
    svg.setAttribute("viewBox", `${x.toFixed(2)} ${y.toFixed(2)} ${w.toFixed(2)} ${h.toFixed(2)}`);
    const scale = (1 / zoomLevel()).toFixed(4);
    svg.querySelectorAll<SVGGElement>(".festival-pin").forEach((pin) => {
      pin.setAttribute("transform", `translate(${pin.dataset.x} ${pin.dataset.y}) scale(${scale})`);
    });
    const zoomed = zoomLevel() > 1.001;
    map.classList.toggle("is-zoomed", zoomed);
    map.querySelector<HTMLButtonElement>('[data-festival-zoom="in"]')!.disabled = zoomLevel() >= MAX_ZOOM - 0.001;
    map.querySelector<HTMLButtonElement>('[data-festival-zoom="out"]')!.disabled = !zoomed;
    map.querySelector<HTMLButtonElement>('[data-festival-zoom="reset"]')!.disabled = !zoomed;
  }

  // Zoom by a factor while keeping the given map-plane point fixed on screen.
  function zoomAt(factor: number, point: Point | null = null) {
    const { x, y, w } = state.view;
    const anchor = point || { x: x + w / 2, y: y + state.view.h / 2 };
    const next = clampView({ w: w / factor, x, y });
    const ratio = next.w / w;
    state.view = clampView({
      w: next.w,
      x: anchor.x - (anchor.x - x) * ratio,
      y: anchor.y - (anchor.y - y) * ratio,
    });
    applyView();
  }

  function mapPoint(clientX: number, clientY: number) {
    const svg = map.querySelector("svg");
    const matrix = svg?.getScreenCTM();
    if (!matrix) return null;
    const point = new DOMPoint(clientX, clientY).matrixTransform(matrix.inverse());
    return { x: point.x, y: point.y };
  }

  function unitsPerPixel() {
    const svg = map.querySelector("svg");
    if (!svg) return 1;
    const rect = svg.getBoundingClientRect();
    // preserveAspectRatio "meet" fits the tighter dimension.
    return Math.max(state.view.w / rect.width, state.view.h / rect.height);
  }

  function pinchDistance() {
    const [a, b] = Array.from(gesture.pointers.values());
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  function graticule() {
    const lines = [];
    for (let lon = -150; lon <= 150; lon += 30) {
      const x = (500 + (lon * 1000) / 360).toFixed(1);
      lines.push(`M${x} ${MAP_TOP}V${MAP_TOP + MAP_HEIGHT}`);
    }
    for (let lat = -30; lat <= 60; lat += 30) {
      const y = (250 - (lat * 1000) / 360).toFixed(1);
      lines.push(`M0 ${y}H1000`);
    }
    return lines.join("");
  }

  function renderDetail(today: number) {
    const festival = FESTIVALS.find((item) => item.id === state.selected);
    if (!festival) {
      const live = FESTIVALS.filter((item) => status(item, today).key === "now");
      const next = sortedFestivals(today).find((item) => status(item, today).key !== "now");
      detail.innerHTML = `<p class="eyebrow">At a glance</p>
        <h2>${live.length ? `${live.length} typical windows include today` : "Between typical windows"}</h2>
        <p>${live.length ? escapeHtml(live.map((item) => item.name).join(", ")) : "Today falls outside the typical windows on this list."}</p>
        ${next ? `<p>Next: <strong>${escapeHtml(next.name)}</strong> in ${escapeHtml(next.city)}, ${escapeHtml(formatWindow(next))} (${escapeHtml(status(next, today).label.toLowerCase())}).</p>` : ""}
        <p class="festival-hint">Select a pin or a calendar row for details.</p>`;
      return;
    }
    const current = status(festival, today);
    const awards = festival.kind === "awards";
    detail.innerHTML = `<p class="eyebrow">${awards ? "Awards ceremony · " : ""}${escapeHtml(festival.city === festival.country ? festival.city : `${festival.city} · ${festival.country}`)}</p>
      <h2>${escapeHtml(festival.name)}</h2>
      <p class="festival-window"><strong>${escapeHtml(formatWindow(festival))}</strong> <span class="festival-status is-${current.key}">${escapeHtml(current.label)}</span></p>
      <p>${escapeHtml(festival.focus)}.</p>
      <p class="festival-hint">${awards
        ? "A single evening that usually falls in this window; confirm this year's date with the Academy."
        : "Typical annual window; confirm this year's dates with the festival."}</p>
      ${festival.url ? `<a class="festival-link" href="${escapeHtml(festival.url)}" target="_blank" rel="noopener noreferrer">Official site ↗</a>` : ""}
      <button type="button" class="festival-clear" data-festival-clear>Show overview</button>`;
  }

  function renderCalendar(today: number) {
    const todayLeft = ((today - 0.5) / 365) * 100;
    const head = `<div class="festival-calendar-row festival-calendar-head" aria-hidden="true">
      <span></span>
      <div class="festival-track">${MONTHS.map((label, index) => `<span style="left:${(CUMULATIVE[index] / 365) * 100}%">${label}</span>`).join("")}</div>
    </div>`;
    const rows = FESTIVALS.slice()
      .sort((a, b) => dayOfYear(a.start) - dayOfYear(b.start))
      .filter((festival) => inMonth(festival, state.month))
      .map((festival) => {
        const start = dayOfYear(festival.start);
        const end = dayOfYear(festival.end);
        const current = status(festival, today);
        const selected = state.selected === festival.id;
        return `<button type="button" class="festival-calendar-row${selected ? " is-selected" : ""}" data-festival-id="${festival.id}" aria-pressed="${selected}">
          <span class="festival-calendar-name"><strong>${escapeHtml(festival.name)}</strong><small>${escapeHtml(festival.city)} · ${escapeHtml(formatWindow(festival))}</small></span>
          <span class="festival-track">
            ${MONTHS.map((_, index) => `<i style="left:${(CUMULATIVE[index] / 365) * 100}%"></i>`).join("")}
            <b class="festival-bar is-${current.key}${festival.kind === "awards" ? " is-awards" : ""}" style="left:${((start - 1) / 365) * 100}%;width:${Math.max(0.8, ((end - start + 1) / 365) * 100)}%"></b>
            <em class="festival-today" style="left:${todayLeft}%"></em>
          </span>
        </button>`;
      }).join("");
    calendar.innerHTML = head + (rows || `<p class="festival-hint">No festivals on this list in ${MONTH_NAMES[state.month - 1]}.</p>`);
    const shown = FESTIVALS.filter((festival) => inMonth(festival, state.month)).length;
    summary.textContent = state.month
      ? `${shown} of ${FESTIVALS.length} event windows overlap ${MONTH_NAMES[state.month - 1]}.`
      : `${FESTIVALS.filter((festival) => festival.kind !== "awards").length} festivals and the Oscars across ${new Set(FESTIVALS.map((festival) => festival.country)).size} countries.`;
  }

  function render() {
    const today = todayOfYear();
    renderMonths();
    renderMap(today);
    renderDetail(today);
    renderCalendar(today);
  }

  function select(id: string | undefined) {
    state.selected = state.selected === id ? null : id ?? null;
    render();
  }

  section.addEventListener("click", (event) => {
    const targetElement = event.target;
    if (!(targetElement instanceof Element)) return;
    const monthButton = targetElement.closest<HTMLElement>("[data-festival-month]");
    if (monthButton) {
      const month = Number(monthButton.dataset.festivalMonth) || 0;
      // Choosing the active month again clears the filter.
      state.month = month === state.month ? 0 : month;
      const selected = FESTIVALS.find((festival) => festival.id === state.selected);
      if (selected && !inMonth(selected, state.month)) state.selected = null;
      render();
      months.querySelector<HTMLButtonElement>(`[data-festival-month="${month}"]`)?.focus();
      return;
    }
    if (targetElement.closest("[data-festival-clear]")) {
      state.selected = null;
      render();
      return;
    }
    const zoomButton = targetElement.closest<HTMLElement>("[data-festival-zoom]");
    if (zoomButton) {
      const action = zoomButton.dataset.festivalZoom;
      if (action === "reset") {
        state.view = { x: 0, y: MAP_TOP, w: 1000, h: MAP_HEIGHT };
        applyView();
      } else {
        zoomAt(action === "in" ? BUTTON_ZOOM : 1 / BUTTON_ZOOM);
      }
      return;
    }
    const target = targetElement.closest<HTMLElement | SVGElement>("[data-festival-id]");
    if (target && !gesture.dragged) select(target.dataset.festivalId);
  });

  map.addEventListener("wheel", (event) => {
    const targetElement = event.target;
    if (!(targetElement instanceof Element)) return;
    if (!targetElement.closest("svg")) return;
    event.preventDefault();
    const delta = event.deltaMode === 1 ? event.deltaY * 16 : event.deltaY;
    zoomAt(Math.exp(-delta * 0.0025), mapPoint(event.clientX, event.clientY));
  }, { passive: false });

  map.addEventListener("dblclick", (event) => {
    const targetElement = event.target;
    if (!(targetElement instanceof Element)) return;
    if (!targetElement.closest("svg") || targetElement.closest<HTMLElement | SVGElement>("[data-festival-id]")) return;
    event.preventDefault();
    zoomAt(event.shiftKey ? 1 / 2 : 2, mapPoint(event.clientX, event.clientY));
  });

  map.addEventListener("pointerdown", (event) => {
    const targetElement = event.target;
    if (!(targetElement instanceof Element)) return;
    if (!targetElement.closest("svg") || (event.pointerType === "mouse" && event.button !== 0)) return;
    gesture.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    gesture.dragged = false;
    gesture.start = {
      view: { ...state.view },
      x: event.clientX,
      y: event.clientY,
      distance: gesture.pointers.size === 2 ? pinchDistance() : 0,
    };
  });

  map.addEventListener("pointermove", (event) => {
    if (!gesture.pointers.has(event.pointerId) || !gesture.start) return;
    gesture.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (gesture.pointers.size === 2 && gesture.start.distance) {
      const [a, b] = Array.from(gesture.pointers.values());
      const centre = mapPoint((a.x + b.x) / 2, (a.y + b.y) / 2);
      const target = gesture.start.view.w / (pinchDistance() / gesture.start.distance);
      gesture.dragged = true;
      zoomAt(state.view.w / target, centre);
      return;
    }
    const dx = event.clientX - gesture.start.x;
    const dy = event.clientY - gesture.start.y;
    if (!gesture.dragged && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
    if (zoomLevel() <= 1.001) return;
    if (!gesture.dragged) map.querySelector("svg")?.setPointerCapture(event.pointerId);
    gesture.dragged = true;
    map.classList.add("is-panning");
    const scale = unitsPerPixel();
    state.view = clampView({
      w: gesture.start.view.w,
      x: gesture.start.view.x - dx * scale,
      y: gesture.start.view.y - dy * scale,
    });
    applyView();
  });

  function endGesture(event: PointerEvent) {
    if (!gesture.pointers.delete(event.pointerId)) return;
    map.classList.remove("is-panning");
    if (gesture.pointers.size) {
      // One finger lifted from a pinch: continue as a pan from the remaining finger.
      const [remaining] = Array.from(gesture.pointers.values());
      gesture.start = { view: { ...state.view }, x: remaining.x, y: remaining.y, distance: 0 };
      return;
    }
    gesture.start = null;
    // Let the click that follows a drag see the flag, then clear it.
    window.setTimeout(() => { gesture.dragged = false; }, 0);
  }
  map.addEventListener("pointerup", endGesture);
  map.addEventListener("pointercancel", endGesture);

  map.addEventListener("keydown", (event) => {
    const targetElement = event.target;
    if (!(targetElement instanceof Element)) return;
    if (event.key !== "Enter" && event.key !== " ") return;
    const pin = targetElement.closest<HTMLElement | SVGElement>("[data-festival-id]");
    if (!pin) return;
    event.preventDefault();
    select(pin.dataset.festivalId);
    map.querySelector<SVGElement>(`[data-festival-id="${pin.dataset.festivalId}"]`)?.focus();
  });

  // Re-render when the view is opened so typical-window comparisons use today's date.
  document.addEventListener("firstroll:view-changed", (event) => {
    if (event.detail?.view === "festivals") render();
  });

  render();

}
