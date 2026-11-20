(() => {
  const source = document.getElementById("page-preview");
  const overlay = document.getElementById("corner-overlay");
  const panel = document.getElementById("corner-tools");
  const outline = document.getElementById("corner-outline");
  const corrected = document.getElementById("corrected-preview");
  const message = document.getElementById("corner-message");
  const apply = document.getElementById("apply-corners");
  const retry = document.getElementById("detect-corners");
  const reset = document.getElementById("reset-corners");
  const addPage = document.getElementById("add-page");
  const edit = document.getElementById("edit-corners");
  const heading = document.getElementById("corner-heading");
  const names = ["kiri atas", "kanan atas", "kanan bawah", "kiri bawah"];

  let points = [];
  let sourceBlob = null;
  let correctedUrl = "";
  let activeRequest = null;
  let dragging = null;
  let hasSource = false;
  let suspended = false;
  let showingResult = false;
  let needsDetection = false;

  const handles = names.map((name, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "corner-handle";
    button.dataset.index = index;
    button.setAttribute("aria-label", "Sudut " + name);
    const number = document.createElement("span");
    number.textContent = index + 1;
    button.append(number);
    overlay.append(button);
    return button;
  });

  function positionOverlay() {
    const bounds = source.getBoundingClientRect();
    const scale = Math.min(bounds.width / source.width, bounds.height / source.height);
    overlay.style.width = source.width * scale + "px";
    overlay.style.height = source.height * scale + "px";
  }
  new ResizeObserver(positionOverlay).observe(source);

  function render() {
    panel.hidden = !hasSource || suspended;
    overlay.hidden = panel.hidden || showingResult;
    corrected.hidden = panel.hidden || !showingResult;
    edit.hidden = !showingResult;
    addPage.hidden = !showingResult;
    for (const control of [apply, retry, reset]) control.hidden = showingResult;
    apply.disabled = points.length !== 4 || Boolean(activeRequest);
    retry.disabled = Boolean(activeRequest);
    heading.textContent = showingResult ? "Halaman diluruskan" : "Sudut dokumen";
    if (overlay.hidden) return;

    positionOverlay();
    const path = [];
    overlay.firstElementChild.setAttribute("viewBox", [0, 0, source.width, source.height].join(" "));
    handles.forEach((button, index) => {
      const point = points[index];
      button.hidden = !point;
      if (!point) return;
      // Coordinates denote centers of pixels in the original, EXIF-oriented image.
      const [x, y] = point.map(value => value + 0.5);
      button.style.left = (100 * x / source.width) + "%";
      button.style.top = (100 * y / source.height) + "%";
      path.push(x + "," + y);
    });
    if (points.length === 4) path.push(path[0]);
    overlay.toggleAttribute("data-complete", points.length === 4);
    outline.setAttribute("points", path.join(" "));
  }

  function guidance() {
    return points.length === 4
      ? "Geser titik ke sudut halaman, lalu pilih Luruskan halaman. Gunakan tombol panah untuk penyesuaian."
      : "Pilih sudut " + names[points.length] + " (" + (points.length + 1) +
        "/4). Ketuk foto atau tekan Enter di area foto untuk menempatkan titik.";
  }

  function stopRequest() {
    activeRequest?.abort();
    activeRequest = null;
    dragging = null;
  }

  async function postImage(path, request, extraHeaders = {}) {
    if (!sourceBlob) {
      const blob = await new Promise(resolve => source.toBlob(resolve, "image/png"));
      if (request.signal.aborted) throw new DOMException("Cancelled", "AbortError");
      if (!blob) throw new Error("Gagal menyiapkan gambar.");
      sourceBlob = blob;
    }
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "image/png", ...extraHeaders },
      body: sourceBlob,
      signal: request.signal,
    });
    if (!response.ok) {
      const details = await response.json().catch(() => null);
      throw new Error(details?.error || "Layanan pemindai lokal gagal memproses foto.");
    }
    return response;
  }

  function errorMessage(error) {
    if (error instanceof TypeError) return "Periksa koneksi ke layanan pemindai lokal dan coba lagi.";
    return error.message;
  }

  async function detect() {
    stopRequest();
    const request = new AbortController();
    activeRequest = request;
    needsDetection = true;
    message.textContent = "Mencari empat sudut halaman…";
    render();
    try {
      const response = await postImage("/api/corners", request);
      const data = await response.json();
      if (request.signal.aborted) return;
      if (data.corners !== null && !(Array.isArray(data.corners) && data.corners.length === 4 &&
          data.corners.every(p => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite)))) {
        throw new Error("Tanggapan detektor tidak valid.");
      }
      points = data.corners || [];
      message.textContent = (data.corners ? "Empat sudut ditemukan. " : "Sudut belum ditemukan. ") + guidance();
    } catch (error) {
      if (!request.signal.aborted) message.textContent = "Deteksi gagal. " + errorMessage(error);
    } finally {
      if (activeRequest === request) {
        activeRequest = null;
        needsDetection = false;
        render();
      }
    }
  }

  function clamp(value, max) {
    return Math.min(max, Math.max(0, value));
  }

  function eventPoint(event) {
    const rect = overlay.getBoundingClientRect();
    return [
      clamp((event.clientX - rect.left) / rect.width * source.width - 0.5, source.width - 1),
      clamp((event.clientY - rect.top) / rect.height * source.height - 0.5, source.height - 1),
    ];
  }

  overlay.addEventListener("pointerdown", event => {
    if (activeRequest || !event.isPrimary || event.button !== 0) return;
    const handle = event.target.closest(".corner-handle");
    let index;
    if (handle) {
      index = Number(handle.dataset.index);
    } else {
      if (points.length === 4) return;
      index = points.length;
      points.push(eventPoint(event));
      message.textContent = guidance();
      render();
    }
    dragging = index;
    overlay.setPointerCapture(event.pointerId);
    handles[index].focus({ preventScroll: true });
    event.preventDefault();
  });
  overlay.addEventListener("pointermove", event => {
    if (dragging === null || !overlay.hasPointerCapture(event.pointerId)) return;
    points[dragging] = eventPoint(event);
    render();
  });
  overlay.addEventListener("lostpointercapture", () => { dragging = null; });

  overlay.addEventListener("keydown", event => {
    if (activeRequest) return;
    const index = handles.indexOf(event.target);
    if (event.key === "Enter" && points.length < 4) {
      const defaults = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]];
      const [x, y] = defaults[points.length];
      points.push([Math.round((source.width - 1) * x), Math.round((source.height - 1) * y)]);
      render();
      handles[points.length - 1].focus();
      message.textContent = "Geser titik dengan tombol panah. " + guidance();
    } else {
      const deltas = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
      if (index < 0 || !Object.hasOwn(deltas, event.key)) return;
      const [dx, dy] = deltas[event.key];
      const step = event.shiftKey ? 10 : 1;
      points[index] = [clamp(points[index][0] + dx * step, source.width - 1),
                       clamp(points[index][1] + dy * step, source.height - 1)];
      message.textContent = "Sudut " + names[index] + " di piksel " + points[index].map(Math.round).join(", ") + ".";
      render();
    }
    event.preventDefault();
  });

  reset.addEventListener("click", () => {
    stopRequest();
    needsDetection = false;
    points = [];
    message.textContent = guidance();
    render();
    overlay.focus();
  });
  retry.addEventListener("click", detect);

  apply.addEventListener("click", async () => {
    if (points.length !== 4 || activeRequest) return;
    const request = new AbortController();
    activeRequest = request;
    message.textContent = "Meluruskan halaman…";
    render();
    let url;
    try {
      const response = await postImage("/api/warp", request, { "X-Document-Corners": JSON.stringify(points) });
      const blob = await response.blob();
      url = URL.createObjectURL(blob);
      const result = new Image();
      result.src = url;
      await result.decode();
      if (request.signal.aborted) return;
      if (correctedUrl) URL.revokeObjectURL(correctedUrl);
      correctedUrl = url;
      url = null;
      corrected.src = correctedUrl;
      showingResult = true;
      document.dispatchEvent(new CustomEvent("page-rectified", {
        detail: { blob, pixels: result.naturalWidth * result.naturalHeight },
      }));
      message.textContent = "Periksa hasilnya, lalu tambahkan halaman ke dokumen.";
    } catch (error) {
      if (!request.signal.aborted) message.textContent = "Halaman gagal diluruskan. " + errorMessage(error);
    } finally {
      if (url) URL.revokeObjectURL(url);
      if (activeRequest === request) {
        activeRequest = null;
        render();
        if (showingResult) edit.focus({ preventScroll: true });
      }
    }
  });
  edit.addEventListener("click", () => {
    showingResult = false;
    message.textContent = guidance();
    render();
    handles[0].focus({ preventScroll: true });
  });

  document.addEventListener("page-ready", () => {
    stopRequest();
    if (correctedUrl) URL.revokeObjectURL(correctedUrl);
    correctedUrl = "";
    corrected.removeAttribute("src");
    sourceBlob = null;
    points = [];
    showingResult = false;
    hasSource = true;
    suspended = false;
    detect();
  });
  document.addEventListener("page-suspend", () => {
    stopRequest();
    suspended = true;
    render();
  });
  document.addEventListener("page-resume", () => {
    suspended = false;
    if (hasSource && needsDetection) detect();
    else {
      if (hasSource && !showingResult) message.textContent = guidance();
      render();
    }
  });
})();
