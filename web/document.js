(() => {
  const add = document.getElementById("add-page");
  const panel = document.getElementById("document-panel");
  const list = document.getElementById("document-pages");
  const count = document.getElementById("page-count");
  const mode = document.getElementById("document-mode");
  const download = document.getElementById("download-pdf");
  const retry = document.getElementById("retry-previews");
  const status = document.getElementById("document-status");
  const pages = [];
  let sourceId = 0;
  let candidate = null;
  let previewRequest = null;
  let exporting = false;
  let downloadUrl = "";

  document.addEventListener("page-ready", () => {
    sourceId++;
    candidate = null;
    render();
  });
  document.addEventListener("page-rectified", event => {
    candidate = event.detail;
    render();
  });

  function move(page, direction) {
    const from = pages.indexOf(page);
    const to = from + direction;
    if (exporting || to < 0 || to >= pages.length) return;
    pages.splice(from, 1);
    pages.splice(to, 0, page);
    render();
    const preferred = direction === 1 ? page.down : page.up;
    const alternative = direction === 1 ? page.up : page.down;
    (preferred.disabled ? alternative : preferred).focus({ preventScroll: true });
    status.textContent = "Halaman dipindahkan ke posisi " + (to + 1) + ".";
  }

  function newPage(id, source) {
    const row = document.createElement("li");
    row.innerHTML = '<div class="page-thumbnail"><span>Memuat…</span><img class="thumbnail" hidden></div>' +
      '<span class="page-label"></span><div class="document-order">' +
      '<button class="button move-up" type="button">Naik</button>' +
      '<button class="button move-down" type="button">Turun</button></div>';
    const page = {
      id, ...source, row, url: "", image: row.querySelector("img"), pending: row.querySelector(".page-thumbnail span"),
      label: row.querySelector(".page-label"), up: row.querySelector(".move-up"), down: row.querySelector(".move-down"),
    };
    page.up.addEventListener("click", () => move(page, -1));
    page.down.addEventListener("click", () => move(page, 1));
    return page;
  }

  function render() {
    const previous = pages.find(page => page.id === sourceId);
    const alreadyAdded = Boolean(previous && previous.blob === candidate?.blob);
    add.disabled = exporting || !candidate || alreadyAdded;
    add.textContent = alreadyAdded ? "Sudah ditambahkan" : "Tambah ke dokumen";
    if (previous && !alreadyAdded) add.textContent = "Perbarui halaman";
    panel.hidden = !pages.length;
    count.textContent = pages.length + " halaman";
    mode.disabled = exporting;
    download.disabled = exporting || Boolean(previewRequest) || !pages.length || pages.some(page => !page.url);
    pages.forEach((page, index) => {
      const number = index + 1;
      page.label.textContent = "Halaman " + number;
      page.image.alt = "Pratinjau halaman " + number;
      page.up.setAttribute("aria-label", "Naikkan halaman " + number);
      page.down.setAttribute("aria-label", "Turunkan halaman " + number);
      page.up.disabled = exporting || index === 0;
      page.down.disabled = exporting || index === pages.length - 1;
      if (list.children[index] !== page.row) list.insertBefore(page.row, list.children[index] || null);
    });
  }

  function invalidate(page) {
    page.image.hidden = true;
    page.image.removeAttribute("src");
    page.pending.hidden = false;
    page.pending.textContent = "Memuat…";
    if (page.url) URL.revokeObjectURL(page.url);
    page.url = "";
  }

  async function checkedBlob(response, type) {
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.error || "Layanan lokal gagal memproses dokumen.");
    }
    const blob = await response.blob();
    if (blob.type !== type || !blob.size) throw new Error("Hasil pemrosesan tidak dapat dibaca.");
    return blob;
  }

  function errorText(error) {
    return error instanceof TypeError ? "Periksa koneksi ke layanan pemindai lokal." : error.message;
  }

  async function refresh() {
    previewRequest?.abort();
    const request = new AbortController();
    previewRequest = request;
    const selected = mode.value;
    retry.hidden = true;
    status.textContent = "Menyiapkan pratinjau halaman…";
    render();
    try {
      // Process one full-resolution page at a time, even when the mode changes on a long document.
      let page;
      while ((page = pages.find(item => !item.url))) {
        const response = await fetch("/api/preview", {
          method: "POST", headers: { "Content-Type": "image/png", "X-Document-Mode": selected },
          body: page.blob, signal: request.signal,
        });
        const blob = await checkedBlob(response, "image/png");
        if (request.signal.aborted) return;
        const url = URL.createObjectURL(blob);
        try {
          const image = new Image();
          image.src = url;
          await image.decode();
          if (request.signal.aborted) return;
          page.url = url;
          page.image.src = url;
        } finally {
          if (page.url !== url) URL.revokeObjectURL(url);
        }
        page.pending.hidden = true;
        page.image.hidden = false;
      }
      status.textContent = "Pratinjau sesuai urutan dan mode PDF.";
    } catch (error) {
      if (request.signal.aborted) return;
      for (const page of pages.filter(item => !item.url)) page.pending.textContent = "Belum siap";
      retry.hidden = false;
      status.textContent = "Pratinjau gagal dimuat. " + errorText(error);
    } finally {
      if (previewRequest === request) {
        previewRequest = null;
        render();
      }
    }
  }

  add.addEventListener("click", () => {
    if (add.disabled || !candidate) return;
    const previous = pages.find(page => page.id === sourceId);
    const others = pages.filter(page => page !== previous);
    const pixels = others.reduce((sum, page) => sum + page.pixels, candidate.pixels);
    const bytes = others.reduce((sum, page) => sum + 4 + page.blob.size, 4 + candidate.blob.size);
    if (others.length + 1 > 100 || pixels > 128_000_000 || bytes > 256 * 1024 * 1024) {
      document.getElementById("corner-message").textContent =
        "Dokumen mencapai batas 100 halaman, 128 megapiksel total, atau 256 MiB. Unduh halaman yang sudah ditambahkan.";
      return;
    }
    if (previous) {
      invalidate(previous);
      previous.blob = candidate.blob;
      previous.pixels = candidate.pixels;
    } else {
      pages.push(newPage(sourceId, candidate));
    }
    refresh();
    panel.scrollIntoView({ block: "nearest" });
  });
  mode.addEventListener("change", () => {
    pages.forEach(invalidate);
    refresh();
  });
  retry.addEventListener("click", refresh);

  window.addEventListener("pagehide", event => {
    if (event.persisted) return;
    previewRequest?.abort();
    pages.forEach(page => { if (page.url) URL.revokeObjectURL(page.url); });
    if (downloadUrl) URL.revokeObjectURL(downloadUrl);
  });

  download.addEventListener("click", async () => {
    if (download.disabled) return;
    exporting = true;
    render();
    status.textContent = "Menyusun PDF…";
    try {
      const parts = [];
      for (const page of pages) {
        const length = new ArrayBuffer(4);
        new DataView(length).setUint32(0, page.blob.size, false);
        parts.push(length, page.blob);
      }
      const response = await fetch("/api/pdf", {
        method: "POST", headers: { "Content-Type": "application/octet-stream", "X-Document-Mode": mode.value },
        body: new Blob(parts),
      });
      const pdf = await checkedBlob(response, "application/pdf");
      if (downloadUrl) URL.revokeObjectURL(downloadUrl);
      downloadUrl = URL.createObjectURL(pdf);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = "TrueScan.pdf";
      document.body.append(link);
      link.click();
      link.remove();
      status.textContent = "Unduhan TrueScan.pdf dimulai.";
    } catch (error) {
      status.textContent = "Unduhan gagal. " + errorText(error);
    } finally {
      exporting = false;
      render();
    }
  });
})();
