import * as THREE from "three";
import { GLTFLoader } from "./vendor/three/addons/loaders/GLTFLoader.js";

const MODEL_URL = "/assets/models/firstroll-closet.glb?v=20260814-8";
const CASE_TONES = ["#632d28", "#304138", "#87512f", "#35404a", "#897c64", "#4d3d4d"];
const CAMERA_BOUNDS = { minX: -0.82, maxX: 0.82, minZ: -3.28, maxZ: 3.82 };
const SHELF_VERTICAL_CENTRE = 2.27;
const DEFAULT_CAMERA_POSITION = new THREE.Vector3(0, SHELF_VERTICAL_CENTRE, 0.12);
const DEFAULT_CAMERA_PITCH = 0;
const SHELF_ROW_SIZE = 10;

let activeViewer = null;

class FirstRollClosetViewer {
  constructor(root, payload) {
    this.root = root;
    this.payload = payload;
    this.canvas = root.querySelector("[data-closet-canvas]");
    this.loading = root.querySelector("[data-closet-loading]");
    this.caption = root.closest(".film-closet")?.querySelector("[data-closet-caption]");
    this.renderer = null;
    this.scene = null;
    this.camera = null;
    this.clock = new THREE.Clock();
    this.model = null;
    this.filmCases = [];
    this.shelfPlaques = [];
    this.posterTextureCache = new Map();
    this.collectionKey = null;
    this.collectionLoadPromise = null;
    this.loadingFinished = false;
    this.hoveredCase = null;
    this.drag = null;
    this.yaw = 0;
    this.pitch = DEFAULT_CAMERA_PITCH;
    this.destroyed = false;
    this.animationFrame = null;
    this.resizeObserver = null;
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.keys = new Set();
    this.reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.bound = {
      resize: () => this.resize(),
      pointerDown: (event) => this.onPointerDown(event),
      pointerMove: (event) => this.onPointerMove(event),
      pointerUp: (event) => this.onPointerUp(event),
      wheel: (event) => this.onWheel(event),
      keyDown: (event) => this.onKeyDown(event),
      keyUp: (event) => this.onKeyUp(event),
      blur: () => this.keys.clear(),
    };
  }

  async initialise() {
    if (!this.canvas || !this.canvas.getContext) return;
    try {
      this.renderer = new THREE.WebGLRenderer({
        canvas: this.canvas,
        antialias: window.devicePixelRatio < 2.2,
        powerPreference: "high-performance",
      });
    } catch (error) {
      this.showError("WebGL is unavailable in this browser.");
      return;
    }
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.94;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x080705);
    this.scene.fog = new THREE.FogExp2(0x0b0907, 0.018);
    this.camera = new THREE.PerspectiveCamera(55, 1, 0.05, 28);
    this.camera.position.copy(DEFAULT_CAMERA_POSITION);
    this.updateCameraRotation();
    this.updateHud();
    this.addLighting();
    this.bindEvents();
    this.resize();
    this.animate();

    try {
      const gltf = await new GLTFLoader().loadAsync(MODEL_URL);
      if (this.destroyed) return;
      this.model = gltf.scene;
      this.model.name = "FirstRoll Blender shelf";
      this.model.traverse((object) => {
        if (!object.isMesh) return;
        object.receiveShadow = true;
        object.castShadow = true;
        if (object.material) object.material.envMapIntensity = 0.55;
      });
      this.scene.add(this.model);
      if (this.loading) {
        this.loading.querySelector("strong").textContent = this.hasShelfCollections()
          ? "Shelving the collection"
          : "Curating the shelf";
      }
      await this.addLiveCollections();
      if (this.destroyed) return;
      this.root.dataset.liveCaseCount = String(this.filmCases.length);
      this.renderer.render(this.scene, this.camera);
      this.root.classList.add("is-ready");
      if (this.hasShelfCollections()) await this.finishLoading();
    } catch (error) {
      console.error("FirstRoll shelf model failed to load", error);
      this.showError("The 3D archive model could not be loaded.");
    }
  }

  addLighting() {
    this.scene.add(new THREE.HemisphereLight(0xeadfc8, 0x15110d, 0.78));
    this.scene.add(new THREE.AmbientLight(0x806f58, 0.28));

    const lightPositions = [
      [0, 4.12, 2.65],
      [0, 4.12, 0],
      [0, 4.12, -2.65],
    ];
    lightPositions.forEach(([x, y, z], index) => {
      const light = new THREE.PointLight(0xffd59c, index === 1 ? 16 : 12, 7.5, 1.9);
      light.position.set(x, y, z);
      light.castShadow = index === 1;
      light.shadow.mapSize.set(1024, 1024);
      light.shadow.bias = -0.0008;
      this.scene.add(light);
    });
    const entrance = new THREE.SpotLight(0xe4c79c, 18, 9, Math.PI / 4.8, 0.78, 1.6);
    entrance.position.set(0, 3.55, 4.1);
    entrance.target.position.set(0, 1.25, -1.3);
    this.scene.add(entrance, entrance.target);
  }

  waitForShelfReveal() {
    return new Promise((resolve) => {
      window.requestAnimationFrame(() => window.requestAnimationFrame(resolve));
    });
  }

  hasShelfCollections() {
    return (this.payload.collections || []).some((collection) => collection.films?.length);
  }

  async finishLoading() {
    if (this.loadingFinished || !this.loading) return;
    this.loadingFinished = true;
    this.loading.querySelector("strong").textContent = "Shelf ready";
    await this.waitForShelfReveal();
    if (this.destroyed) return;
    await new Promise((resolve) => window.setTimeout(resolve, 420));
    if (!this.destroyed && this.loading) this.loading.remove();
  }

  async addLiveCollections() {
    const collections = this.payload.collections || [];
    const shelfFilms = collections.flatMap((collection) => collection.films || []);
    const collectionKey = shelfFilms.map((film) => film?.id).filter(Boolean).join("|");
    const shelfEditions = shelfFilms.map((film) => {
      const title = String(film.title || film.original_title || "")
        .normalize("NFKC")
        .toLocaleLowerCase("en-GB")
        .replace(/[\p{P}\p{S}\s]+/gu, " ")
        .trim();
      return `${title}|${film.year || "undated"}`;
    });
    this.root.dataset.filmCount = String(shelfFilms.length);
    this.root.dataset.uniqueFilmCount = String(new Set(shelfEditions).size);
    if (!collectionKey) return;
    if (collectionKey === this.collectionKey) return this.collectionLoadPromise;
    if (this.collectionLoadPromise) await this.collectionLoadPromise;
    if (this.destroyed || collectionKey === this.collectionKey) return this.collectionLoadPromise;
    if (this.filmCases.length || this.shelfPlaques.length) this.clearLiveCollections();
    this.collectionKey = collectionKey;
    this.collectionLoadPromise = Promise.all(collections.map(async (collection) => {
      if (!collection.films?.length) return;
      await this.addFilmRow(collection);
      this.addShelfPlaque(collection);
    }));
    await this.collectionLoadPromise;
    this.root.dataset.liveCaseCount = String(this.filmCases.length);
  }

  clearLiveCollections() {
    const dispose = (object) => {
      this.scene.remove(object);
      object.traverse((child) => {
        child.geometry?.dispose?.();
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        materials.filter(Boolean).forEach((material) => {
          if (material.map?.isCanvasTexture) material.map.dispose();
          material.dispose?.();
        });
      });
    };
    this.filmCases.forEach(dispose);
    this.shelfPlaques.forEach(dispose);
    this.filmCases = [];
    this.shelfPlaques = [];
    this.hoveredCase = null;
    this.collectionKey = null;
    this.collectionLoadPromise = null;
  }

  async update(payload) {
    this.payload = payload;
    if (!this.model || this.destroyed) return;
    if (this.loading) this.loading.querySelector("strong").textContent = "Shelving the collection";
    await this.addLiveCollections();
    if (this.destroyed) return;
    this.renderer.render(this.scene, this.camera);
    this.root.classList.add("is-ready");
    if (this.hasShelfCollections()) await this.finishLoading();
  }

  async addFilmRow(collection) {
    const films = collection.films.filter((film) => film?.id && film?.title).slice(0, SHELF_ROW_SIZE);
    const shelfHeights = { bottom: 0.61, lower: 1.44, middle: 2.27, upper: 3.10, top: 3.93 };
    const baseY = shelfHeights[collection.shelf] || shelfHeights.lower;
    const available = 2.78;
    const gap = 0.035;
    const width = Math.min(
      0.205,
      Math.max(0.12, (available - gap * Math.max(0, films.length - 1)) / films.length),
    );
    const span = films.length * width + Math.max(0, films.length - 1) * gap;

    const filmCases = films.map((film, index) => {
      let position;
      let rotationY = 0;
      let pullDirection;
      const rowCentre = 0;
      const offset = rowCentre - span / 2 + width / 2 + index * (width + gap);
      if (collection.wall === "back") {
        position = new THREE.Vector3(offset, baseY, -3.62);
        pullDirection = new THREE.Vector3(0, 0, 1);
      } else {
        const side = collection.wall === "left" ? -1 : 1;
        position = new THREE.Vector3(side * 0.79, baseY, offset);
        rotationY = side < 0 ? Math.PI / 2 : -Math.PI / 2;
        pullDirection = new THREE.Vector3(-side, 0, 0);
      }
      return this.createFilmCase(film, index, width, position, rotationY, pullDirection);
    });
    filmCases.forEach((filmCase) => {
      this.scene.add(filmCase);
      this.filmCases.push(filmCase);
    });
  }

  createFilmCase(film, index, width, position, rotationY, pullDirection) {
    const group = new THREE.Group();
    group.name = `Selectable case — ${film.title || "Untitled"}`;
    group.position.copy(position);
    group.rotation.y = rotationY;
    group.userData = {
      film,
      filmId: film.id,
      basePosition: position.clone(),
      pullDirection,
      hoverAmount: 0,
      targetHover: 0,
      selectableCase: true,
    };

    const height = 0.64;
    const depth = 0.13;
    const faceWidth = width * 0.82;
    const faceHeight = height * 0.91;
    if (film.poster_url) {
      this.loadPosterTexture(film.poster_url).then((posterTexture) => {
        if (!posterTexture || this.destroyed) return;
        const poster = new THREE.Mesh(
          new THREE.PlaneGeometry(faceWidth, faceHeight),
          new THREE.MeshStandardMaterial({ map: posterTexture, roughness: 0.62, metalness: 0.0 }),
        );
        poster.position.z = depth / 2 + 0.005;
        poster.userData.caseOwner = group;
        group.add(poster);
      });
    }
    const insertTexture = this.createSpineTexture(
      film,
      index,
      false,
      faceWidth / faceHeight,
    );
    const insertMaterial = new THREE.MeshStandardMaterial({
      map: insertTexture,
      roughness: 0.58,
      metalness: 0.0,
      transparent: false,
      depthWrite: true,
    });
    const insert = new THREE.Mesh(new THREE.PlaneGeometry(faceWidth, faceHeight), insertMaterial);
    insert.position.z = depth / 2 + 0.008;
    insert.userData.caseOwner = group;
    group.add(insert);

    const shellMaterial = new THREE.MeshPhysicalMaterial({
      color: 0xf2f0e8,
      roughness: 0.12,
      metalness: 0.0,
      transmission: 0.16,
      thickness: 0.035,
      transparent: true,
      opacity: 0.22,
      clearcoat: 0.9,
      clearcoatRoughness: 0.16,
    });
    const shell = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), shellMaterial);
    shell.castShadow = true;
    shell.receiveShadow = true;
    shell.userData.caseOwner = group;
    group.add(shell);

    const hingeMaterial = new THREE.MeshStandardMaterial({
      color: 0xd8d6cf,
      roughness: 0.28,
      transparent: true,
      opacity: 0.72,
    });
    const hinge = new THREE.Mesh(new THREE.BoxGeometry(Math.max(0.018, width * 0.12), height * 0.96, depth * 1.02), hingeMaterial);
    hinge.position.x = -width * 0.44;
    hinge.userData.caseOwner = group;
    group.add(hinge);

    return group;
  }

  loadPosterTexture(url) {
    if (!url) return Promise.resolve(null);
    if (this.posterTextureCache.has(url)) return this.posterTextureCache.get(url);
    const promise = new Promise((resolve) => {
      let settled = false;
      const finish = (texture) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timeout);
        if (texture) {
          texture.colorSpace = THREE.SRGBColorSpace;
          texture.anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());
          texture.repeat.set(0.46, 1);
          texture.offset.set(0.27, 0);
        }
        resolve(texture || null);
      };
      const timeout = window.setTimeout(() => finish(null), 6000);
      new THREE.TextureLoader().setCrossOrigin("anonymous").load(url, finish, undefined, () => finish(null));
    });
    this.posterTextureCache.set(url, promise);
    return promise;
  }

  createSpineTexture(film, index, hasPoster = false, faceAspect = 0.25) {
    const canvas = document.createElement("canvas");
    canvas.height = 1024;
    // Match the canvas to the physical insert so its lettering is not geometrically squeezed.
    canvas.width = Math.round(canvas.height * faceAspect);
    const context = canvas.getContext("2d");
    const tone = CASE_TONES[index % CASE_TONES.length];
    if (hasPoster) {
      const veil = context.createLinearGradient(0, 0, canvas.width, 0);
      veil.addColorStop(0, "rgba(8,6,5,.78)");
      veil.addColorStop(0.22, "rgba(8,6,5,.30)");
      veil.addColorStop(0.78, "rgba(8,6,5,.38)");
      veil.addColorStop(1, "rgba(8,6,5,.82)");
      context.fillStyle = veil;
      context.fillRect(0, 0, canvas.width, canvas.height);
    } else {
      context.fillStyle = tone;
      context.fillRect(0, 0, canvas.width, canvas.height);
    }
    const gloss = context.createLinearGradient(0, 0, canvas.width, 0);
    gloss.addColorStop(0, "rgba(255,255,255,.34)");
    gloss.addColorStop(0.18, "rgba(255,255,255,.04)");
    gloss.addColorStop(0.78, "rgba(0,0,0,.12)");
    gloss.addColorStop(1, "rgba(255,255,255,.18)");
    context.fillStyle = gloss;
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.strokeStyle = "rgba(255,248,229,.65)";
    context.lineWidth = 7;
    context.strokeRect(12, 12, canvas.width - 24, canvas.height - 24);

    context.save();
    context.translate(canvas.width / 2, canvas.height / 2);
    context.rotate(-Math.PI / 2);
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillStyle = "#fff8e8";
    const fullTitle = String(film.title || "Untitled").toUpperCase();
    const title = fullTitle.length > 30 ? `${fullTitle.slice(0, 29).trimEnd()}…` : fullTitle;
    let titleSize = 72;
    do {
      context.font = `700 ${titleSize}px sans-serif`;
      titleSize -= 2;
    } while (context.measureText(title).width > 740 && titleSize > 48);
    context.fillText(title, 35, -8);
    context.font = "600 40px monospace";
    context.fillStyle = "rgba(255,248,232,.82)";
    context.fillText(String(film.year || "FILM"), -395, -8);
    context.restore();

    context.fillStyle = "rgba(255,248,232,.86)";
    context.font = "700 28px monospace";
    context.textAlign = "center";
    context.fillText("FR", canvas.width / 2, 62);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());
    return texture;
  }

  addShelfPlaque(collection) {
    const canvas = document.createElement("canvas");
    canvas.width = 2048;
    // The texture and physical fascia share an aspect ratio, keeping captions natural.
    canvas.height = 96;
    const context = canvas.getContext("2d");
    context.fillStyle = "#b69762";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "rgba(255,249,226,.2)";
    context.fillRect(0, 0, canvas.width, 8);
    context.strokeStyle = "#4a331a";
    context.lineWidth = 4;
    context.strokeRect(6, 6, canvas.width - 12, canvas.height - 12);
    context.fillStyle = "#17130e";
    context.textBaseline = "middle";
    const label = String(collection.label || "Film collection");
    let labelSize = 52;
    do {
      context.font = `700 ${labelSize}px sans-serif`;
      labelSize -= 2;
    } while (context.measureText(label).width > 1660 && labelSize > 36);
    context.fillText(label, 56, 49);
    context.textAlign = "right";
    context.font = "700 44px sans-serif";
    context.fillText(String(collection.films.length), 1980, 49);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const plaque = new THREE.Mesh(
      new THREE.PlaneGeometry(collection.wall === "back" ? 2.62 : 2.4, 0.12),
      new THREE.MeshStandardMaterial({ map: texture, roughness: 0.5, metalness: 0.2 }),
    );
    texture.anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());
    const plaqueHeights = { bottom: 0.25, lower: 1.08, middle: 1.91, upper: 2.74, top: 3.57 };
    const y = plaqueHeights[collection.shelf] || plaqueHeights.lower;
    if (collection.wall === "back") {
      plaque.position.set(0, y, -3.39);
    } else {
      const side = collection.wall === "left" ? -1 : 1;
      plaque.position.set(side * 0.56, y, 0);
      plaque.rotation.y = side < 0 ? Math.PI / 2 : -Math.PI / 2;
    }
    this.scene.add(plaque);
    this.shelfPlaques.push(plaque);
  }

  bindEvents() {
    this.canvas.addEventListener("pointerdown", this.bound.pointerDown);
    this.canvas.addEventListener("pointermove", this.bound.pointerMove);
    this.canvas.addEventListener("pointerup", this.bound.pointerUp);
    this.canvas.addEventListener("pointercancel", this.bound.pointerUp);
    this.canvas.addEventListener("wheel", this.bound.wheel, { passive: false });
    this.root.addEventListener("keydown", this.bound.keyDown);
    this.root.addEventListener("keyup", this.bound.keyUp);
    window.addEventListener("blur", this.bound.blur);
    this.resizeObserver = new ResizeObserver(this.bound.resize);
    this.resizeObserver.observe(this.root);
  }

  onPointerDown(event) {
    if (event.button !== 0) return;
    this.root.focus({ preventScroll: true });
    this.drag = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      lastX: event.clientX,
      lastY: event.clientY,
      moved: false,
    };
    this.canvas.setPointerCapture(event.pointerId);
    this.root.classList.add("is-dragging");
  }

  onPointerMove(event) {
    if (this.drag && this.drag.pointerId === event.pointerId) {
      const deltaX = event.clientX - this.drag.lastX;
      const deltaY = event.clientY - this.drag.lastY;
      if (Math.hypot(event.clientX - this.drag.startX, event.clientY - this.drag.startY) > 5) {
        this.drag.moved = true;
      }
      if (this.drag.moved) {
        this.yaw -= deltaX * 0.0042;
        this.pitch = THREE.MathUtils.clamp(this.pitch - deltaY * 0.0034, -0.62, 0.55);
        this.updateCameraRotation();
      }
      this.drag.lastX = event.clientX;
      this.drag.lastY = event.clientY;
      return;
    }
    this.updateHover(event);
  }

  onPointerUp(event) {
    if (!this.drag || this.drag.pointerId !== event.pointerId) return;
    const moved = this.drag.moved;
    this.root.classList.remove("is-dragging");
    if (this.canvas.hasPointerCapture(event.pointerId)) this.canvas.releasePointerCapture(event.pointerId);
    this.drag = null;
    if (!moved) {
      const filmCase = this.pickCase(event);
      if (filmCase?.userData.filmId) {
        this.root.dispatchEvent(new CustomEvent("firstroll:select-film", {
          bubbles: true,
          detail: { filmId: filmCase.userData.filmId },
        }));
      }
    }
  }

  onWheel(event) {
    event.preventDefault();
    this.walk(-event.deltaY * 0.0065);
  }

  onKeyDown(event) {
    if (event.key === "Shift") this.keys.add("shift");
    if (["w", "W", "a", "A", "s", "S", "d", "D", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) {
      event.preventDefault();
      this.keys.add(event.key.toLowerCase());
    }
    if (event.key === "Home") {
      event.preventDefault();
      this.reset();
    }
  }

  onKeyUp(event) {
    this.keys.delete(event.key.toLowerCase());
  }

  updateHover(event) {
    const filmCase = this.pickCase(event);
    if (filmCase === this.hoveredCase) return;
    if (this.hoveredCase) this.hoveredCase.userData.targetHover = 0;
    this.hoveredCase = filmCase;
    if (this.hoveredCase) this.hoveredCase.userData.targetHover = 1;
    this.updateCaseCaption(this.hoveredCase?.userData.film);
    this.root.classList.toggle("is-case-hovered", Boolean(filmCase));
  }

  updateCaseCaption(film) {
    if (!this.caption) return;
    if (!film) {
      this.caption.textContent = this.caption.dataset.defaultCaption || "Film shelf";
      return;
    }
    const director = (film.directors || [])[0];
    this.caption.textContent = [film.title, film.year, director].filter(Boolean).join(" · ");
  }

  pickCase(event) {
    if (!this.camera || !this.renderer) return null;
    const bounds = this.canvas.getBoundingClientRect();
    this.pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
    this.pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hits = this.raycaster.intersectObjects(this.filmCases, true);
    if (!hits.length) return null;
    return hits[0].object.userData.caseOwner || this.findCaseOwner(hits[0].object);
  }

  findCaseOwner(object) {
    let current = object;
    while (current && !current.userData.selectableCase) current = current.parent;
    return current || null;
  }

  walk(distance) {
    if (!this.camera) return;
    const { forward } = this.movementBasis();
    this.camera.position.addScaledVector(forward, distance);
    this.constrainCamera();
    this.updateHud();
  }

  strafe(distance) {
    if (!this.camera) return;
    const { right } = this.movementBasis();
    this.camera.position.addScaledVector(right, distance);
    this.constrainCamera();
    this.updateHud();
  }

  movementBasis() {
    const forward = new THREE.Vector3();
    this.camera.getWorldDirection(forward);
    forward.y = 0;
    if (forward.lengthSq() < Number.EPSILON) forward.set(0, 0, -1);
    forward.normalize();
    const right = new THREE.Vector3().crossVectors(forward, this.camera.up).normalize();
    return { forward, right };
  }

  constrainCamera() {
    this.camera.position.x = THREE.MathUtils.clamp(this.camera.position.x, CAMERA_BOUNDS.minX, CAMERA_BOUNDS.maxX);
    this.camera.position.z = THREE.MathUtils.clamp(this.camera.position.z, CAMERA_BOUNDS.minZ, CAMERA_BOUNDS.maxZ);
  }

  reset() {
    this.camera.position.copy(DEFAULT_CAMERA_POSITION);
    this.yaw = 0;
    this.pitch = DEFAULT_CAMERA_PITCH;
    this.updateCameraRotation();
    this.updateHud();
  }

  updateCameraRotation() {
    if (!this.camera) return;
    this.camera.rotation.order = "YXZ";
    this.camera.rotation.y = this.yaw;
    this.camera.rotation.x = this.pitch;
  }

  updateMovement(delta) {
    const speed = (this.keys.has("shift") ? 3.4 : 2.15) * delta;
    if (this.keys.has("w") || this.keys.has("arrowup")) this.walk(speed);
    if (this.keys.has("s") || this.keys.has("arrowdown")) this.walk(-speed);
    if (this.keys.has("a") || this.keys.has("arrowleft")) this.strafe(-speed);
    if (this.keys.has("d") || this.keys.has("arrowright")) this.strafe(speed);
  }

  updateCases(delta) {
    this.filmCases.forEach((filmCase) => {
      const data = filmCase.userData;
      const amount = this.reducedMotion
        ? data.targetHover
        : THREE.MathUtils.damp(data.hoverAmount, data.targetHover, 13, delta);
      data.hoverAmount = amount;
      filmCase.position.copy(data.basePosition).addScaledVector(data.pullDirection, amount * 0.13);
      filmCase.scale.setScalar(1);
    });
  }

  updateHud() {
    const closet = this.root.closest(".film-closet");
    const radarDot = closet?.querySelector(".closet-radar span");
    const coordinate = closet?.querySelector(".closet-coordinate");
    const depthTrack = closet?.querySelector(".closet-depth-track i");
    if (radarDot) {
      radarDot.style.left = `${8 + ((this.camera.position.x - CAMERA_BOUNDS.minX) / (CAMERA_BOUNDS.maxX - CAMERA_BOUNDS.minX)) * 84}%`;
      radarDot.style.top = `${10 + ((this.camera.position.z - CAMERA_BOUNDS.minZ) / (CAMERA_BOUNDS.maxZ - CAMERA_BOUNDS.minZ)) * 76}%`;
    }
    if (depthTrack) {
      const progress = (CAMERA_BOUNDS.maxZ - this.camera.position.z) / (CAMERA_BOUNDS.maxZ - CAMERA_BOUNDS.minZ);
      depthTrack.style.width = `${Math.round(progress * 100)}%`;
    }
    if (coordinate) {
      const zone = this.camera.position.z > 2.75 ? "DISTANT VIEW" : this.camera.position.z < -2.15 ? "CLOSE VIEW" : "MID VIEW";
      const gaze = Math.abs(Math.sin(this.yaw)) > 0.42 ? "SHELF EDGE" : "FILM SHELF";
      coordinate.textContent = `${zone} · ${gaze}`;
    }
  }

  animate() {
    if (this.destroyed) return;
    const delta = Math.min(this.clock.getDelta(), 0.05);
    this.updateMovement(delta);
    this.updateCases(delta);
    this.renderer.render(this.scene, this.camera);
    this.animationFrame = window.requestAnimationFrame(() => this.animate());
  }

  resize() {
    if (!this.renderer || !this.camera) return;
    const width = Math.max(1, this.root.clientWidth);
    const height = Math.max(1, this.root.clientHeight);
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  showError(message) {
    this.root.classList.add("has-error");
    if (this.loading) {
      this.loading.innerHTML = `<strong>3D archive unavailable</strong><small>${message}</small>`;
    }
  }

  destroy() {
    this.destroyed = true;
    window.cancelAnimationFrame(this.animationFrame);
    this.resizeObserver?.disconnect();
    this.canvas?.removeEventListener("pointerdown", this.bound.pointerDown);
    this.canvas?.removeEventListener("pointermove", this.bound.pointerMove);
    this.canvas?.removeEventListener("pointerup", this.bound.pointerUp);
    this.canvas?.removeEventListener("pointercancel", this.bound.pointerUp);
    this.canvas?.removeEventListener("wheel", this.bound.wheel);
    this.root?.removeEventListener("keydown", this.bound.keyDown);
    this.root?.removeEventListener("keyup", this.bound.keyUp);
    window.removeEventListener("blur", this.bound.blur);
    this.scene?.traverse((object) => {
      object.geometry?.dispose?.();
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.filter(Boolean).forEach((item) => {
        Object.values(item).forEach((value) => value?.isTexture && value.dispose());
        item.dispose?.();
      });
    });
    this.renderer?.dispose();
  }
}

function mount(payload) {
  const root = payload?.root || document.querySelector("[data-closet-viewport]");
  if (!root) return;
  activeViewer?.destroy();
  activeViewer = new FirstRollClosetViewer(root, payload);
  activeViewer.initialise();
}

window.FirstRollCloset = {
  mount,
  update(payload) {
    if (!activeViewer || activeViewer.root !== payload?.root) {
      mount(payload);
      return;
    }
    activeViewer.update(payload);
  },
  unmount() {
    activeViewer?.destroy();
    activeViewer = null;
  },
  walk(distance) {
    activeViewer?.walk(Number(distance) || 0);
  },
  reset() {
    activeViewer?.reset();
  },
};

window.addEventListener("firstroll:mount-closet", (event) => mount(event.detail));
if (window.__firstRollClosetPayload) mount(window.__firstRollClosetPayload);
