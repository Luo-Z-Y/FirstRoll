import { colourfulInfinityFragment } from "./colourful-infinity";

// Local shader source; no third-party scripts, textures or runtime requests.
const vertexSource = `
attribute vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }
`;

/** Renderer states, published as `data-shader-state` on both the canvas and its dialog. */
export type ShaderState = "static" | "paused" | "running";

export function shaderSize(width: number, height: number, dpr: number): [number, number] {
  const scale = Math.min(Math.max(dpr, 1), 1.25, 960 / Math.max(width, 1), 540 / Math.max(height, 1));
  return [Math.max(1, Math.round(width * scale)), Math.max(1, Math.round(height * scale))];
}

export function mountDiscoveryShader(): () => void {
  const canvas = document.getElementById("discoveryShader") as HTMLCanvasElement | null;
  const toggle = document.getElementById("shaderToggle") as HTMLButtonElement | null;
  // The canvas must be a direct child of the welcome dialog, which carries the mirrored state.
  const host = canvas?.parentElement as HTMLDialogElement | null;
  if (!canvas || !toggle || !host) return () => {};
  if (typeof canvas.getContext !== "function" || typeof IntersectionObserver === "undefined"
      || typeof ResizeObserver === "undefined" || typeof MutationObserver === "undefined") {
    // Keep the readable static presentation when the browser lacks what the renderer needs.
    canvas.dataset.shaderState = host.dataset.shaderState = "static";
    return () => {};
  }

  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let gl: WebGLRenderingContext | null = null;
  let program: WebGLProgram | null = null;
  let buffer: WebGLBuffer | null = null;
  const shaders: WebGLShader[] = [];
  let uniforms: { resolution: WebGLUniformLocation | null; time: WebGLUniformLocation | null } | null = null;
  let visible = false, paused = false, suspended = false, failed = false, disposed = false;
  let frame = 0, last = 0, elapsed = 0;

  // Mirror the state onto the dialog too, so CSS can restyle its text without :has().
  function setState(state: ShaderState): void {
    canvas!.dataset.shaderState = state;
    host!.dataset.shaderState = state;
  }

  function stop(): void {
    if (frame) window.cancelAnimationFrame(frame);
    frame = 0;
    last = 0;
  }

  function release(): void {
    if (gl) {
      shaders.forEach(shader => gl?.deleteShader(shader));
      if (buffer) gl.deleteBuffer(buffer);
      if (program) gl.deleteProgram(program);
    }
    shaders.length = 0;
    buffer = null; program = null; uniforms = null;
  }

  function fallback(): void {
    failed = true;
    stop(); release();
    setState("static");
    toggle!.hidden = true;
  }

  function initialise(): boolean {
    try {
      gl = canvas!.getContext("webgl", { alpha: false, antialias: false, depth: false,
        stencil: false, powerPreference: "low-power" });
      if (!gl) return false;
      program = gl.createProgram();
      if (!program) return false;
      for (const [type, source] of [[gl.VERTEX_SHADER, vertexSource], [gl.FRAGMENT_SHADER, colourfulInfinityFragment]] as const) {
        const shader = gl.createShader(type);
        if (!shader) return false;
        shaders.push(shader);
        gl.shaderSource(shader, source); gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) return false;
        gl.attachShader(program, shader);
      }
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return false;
      gl.useProgram(program);
      buffer = gl.createBuffer();
      if (!buffer) return false;
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
      const position = gl.getAttribLocation(program, "position");
      if (position < 0) return false;
      gl.enableVertexAttribArray(position);
      gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
      uniforms = { resolution: gl.getUniformLocation(program, "resolution"),
        time: gl.getUniformLocation(program, "time") };
      return true;
    } catch { return false; }
  }

  function draw(): void {
    if (!gl || !uniforms) return;
    const bounds = host!.getBoundingClientRect();
    const [width, height] = shaderSize(bounds.width, bounds.height, window.devicePixelRatio || 1);
    if (canvas!.width !== width || canvas!.height !== height) {
      canvas!.width = width; canvas!.height = height;
    }
    gl.viewport(0, 0, width, height);
    gl.uniform2f(uniforms.resolution, width, height);
    gl.uniform1f(uniforms.time, elapsed / 1000);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  function tick(now: number): void {
    frame = 0;
    if (disposed || failed) return;
    if (!last || now - last >= 1000 / 30) {
      elapsed += last ? Math.min(now - last, 100) : 0;
      last = now;
      try { draw(); } catch { fallback(); return; }
    }
    frame = window.requestAnimationFrame(tick);
  }

  function sync(): void {
    if (disposed || failed) return;
    stop();
    const active = visible && host!.open && !document.hidden && !suspended;
    toggle!.hidden = motion.matches;
    toggle!.textContent = paused ? "▶" : "Ⅱ";
    toggle!.setAttribute("aria-label", paused ? "Play background animation" : "Pause background animation");
    toggle!.title = paused ? "Play background animation" : "Pause background animation";
    if (motion.matches) { setState("static"); return; }
    if (!active) return;
    if (!program && !initialise()) { fallback(); return; }
    setState(paused ? "paused" : "running");
    try { draw(); } catch { fallback(); return; }
    if (!paused) frame = window.requestAnimationFrame(tick);
  }

  const intersection = new IntersectionObserver(entries => {
    visible = entries.some(entry => entry.isIntersecting); sync();
  });
  const resize = new ResizeObserver(sync);
  const attributes = new MutationObserver(sync);
  const onToggle = () => { paused = !paused; sync(); };
  const onLoss = () => fallback(); // Keep the static fallback after GPU/context failure.
  const onHide = (event: PageTransitionEvent) => {
    if (!event.persisted) dispose();
    else { suspended = true; stop(); }
  };
  const onShow = () => { suspended = false; sync(); };
  function dispose(): void {
    if (disposed) return;
    disposed = true; stop(); release();
    intersection.disconnect(); resize.disconnect(); attributes.disconnect();
    motion.removeEventListener("change", sync);
    document.removeEventListener("visibilitychange", sync);
    window.removeEventListener("pagehide", onHide); window.removeEventListener("pageshow", onShow);
    canvas!.removeEventListener("webglcontextlost", onLoss);
    toggle!.removeEventListener("click", onToggle);
    toggle!.hidden = true; setState("static");
  }
  // Nothing is drawn until the dialog is visible, so both elements start static.
  setState("static");
  intersection.observe(host);
  resize.observe(host);
  // Watch only `open`: the mirrored data-shader-state attribute must not re-trigger sync().
  attributes.observe(host, { attributes: true, attributeFilter: ["open"] });
  motion.addEventListener("change", sync);
  document.addEventListener("visibilitychange", sync);
  window.addEventListener("pagehide", onHide); window.addEventListener("pageshow", onShow);
  canvas.addEventListener("webglcontextlost", onLoss);
  toggle.addEventListener("click", onToggle);
  sync();
  return dispose;
}
