(() => {
  const add = document.getElementById("add-page");
  const panel = document.getElementById("document-panel");
  const list = document.getElementById("document-pages");
  const count = document.getElementById("page-count");
  const mode = document.getElementById("document-mode");
  const pageSize = document.getElementById("document-page-size");
  const documentName = document.getElementById("document-name");
  const download = document.getElementById("download-pdf");
  const retry = document.getElementById("retry-previews");
  const status = document.getElementById("document-status");
  const pages = [];
  let sourceId = 0;
  let candidate = null;
  let previewRequest = null;
  let exporting = false;
  let preparingPage = false;
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
    if (exporting || preparingPage || to < 0 || to >= pages.length) return;
    pages.splice(from, 1);
    pages.splice(to, 0, page);
    render();
    const preferred = direction === 1 ? page.down : page.up;
    const alternative = direction === 1 ? page.up : page.down;
    (preferred.disabled ? alternative : preferred).focus({ preventScroll: true });
    status.textContent = "Halaman dipindahkan ke posisi " + (to + 1) + ".";
  }

  function removePage(page) {
    const index = pages.indexOf(page);
    if (exporting || preparingPage || index < 0) return;
    const loading = Boolean(previewRequest);
    previewRequest?.abort();
    previewRequest = null;
    pages.splice(index, 1);
    invalidate(page);
    page.row.remove();
    const missingPreviews = pages.some(item => !item.url);
    if (!missingPreviews) retry.hidden = true;
    render();
    if (loading && missingPreviews) refresh();
    if (pages.length) {
      status.textContent = "Halaman " + (index + 1) + " dihapus. Tersisa " + pages.length + " halaman.";
      pages[Math.min(index, pages.length - 1)].remove.focus({ preventScroll: true });
    } else {
      const camera = document.getElementById("open-camera");
      const target = add.getClientRects().length && !add.disabled ? add :
        (camera.hidden ? document.getElementById("stop-camera") : camera);
      document.getElementById("status").textContent = "Halaman terakhir dihapus. Dokumen kosong.";
      target.focus();
    }
  }

  function newPage(id) {
    const row = document.createElement("li");
    row.innerHTML = '<div class="page-thumbnail"><span>Memuat…</span><img class="thumbnail" hidden></div>' +
      '<span class="page-label"></span><div class="document-order">' +
      '<button class="button rotate-page" type="button">Putar 90°</button>' +
      '<button class="button move-up" type="button">Naik</button>' +
      '<button class="button move-down" type="button">Turun</button>' +
      '<button class="button remove-page" type="button">Hapus</button></div>';
    const page = {
      id, row, url: "", image: row.querySelector("img"), pending: row.querySelector(".page-thumbnail span"),
      rotate: row.querySelector(".rotate-page"),
      remove: row.querySelector(".remove-page"),
      label: row.querySelector(".page-label"), up: row.querySelector(".move-up"), down: row.querySelector(".move-down"),
    };
    page.up.addEventListener("click", () => move(page, -1));
    page.down.addEventListener("click", () => move(page, 1));
    page.remove.addEventListener("click", () => removePage(page));
    page.rotate.addEventListener("click", () => {
      if (!page.rotate.disabled) savePage(page, page.original, (page.turns + 1) % 4);
    });
    return page;
  }

  function render() {
    const previous = pages.find(page => page.id === sourceId);
    const busy = exporting || preparingPage;
    const alreadyAdded = Boolean(previous && previous.original === candidate);
    add.disabled = busy || !candidate || alreadyAdded;
    add.textContent = alreadyAdded ? "Sudah ditambahkan" : "Tambah ke dokumen";
    if (previous && !alreadyAdded) add.textContent = "Perbarui halaman";
    panel.hidden = !pages.length;
    count.textContent = pages.length + " halaman";
    retry.disabled = busy;
    mode.disabled = busy;
    documentName.disabled = exporting;
    pageSize.disabled = exporting;
    download.disabled = busy || Boolean(previewRequest) || !pages.length || pages.some(page => !page.url);
    pages.forEach((page, index) => {
      const number = index + 1;
      page.label.textContent = "Halaman " + number;
      page.image.alt = "Pratinjau halaman " + number;
      page.rotate.setAttribute("aria-label", "Putar halaman " + number + " 90° ke kanan");
      page.rotate.disabled = busy || Boolean(previewRequest);
      page.remove.setAttribute("aria-label", "Hapus halaman " + number);
      page.remove.disabled = busy;
      page.up.setAttribute("aria-label", "Naikkan halaman " + number);
      page.down.setAttribute("aria-label", "Turunkan halaman " + number);
      page.up.disabled = busy || index === 0;
      page.down.disabled = busy || index === pages.length - 1;
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

  async function rotatedPng(original, turns) {
    if (!turns) return original;
    const bitmap = await createImageBitmap(original);
    const canvas = document.createElement("canvas");
    try {
      const { width, height } = bitmap;
      canvas.width = turns % 2 ? height : width;
      canvas.height = turns % 2 ? width : height;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Gagal membuat gambar halaman.");
      if (turns === 1) context.setTransform(0, 1, -1, 0, height, 0);
      if (turns === 2) context.setTransform(-1, 0, 0, -1, width, height);
      if (turns === 3) context.setTransform(0, -1, 1, 0, 0, width);
      context.imageSmoothingEnabled = false;
      context.drawImage(bitmap, 0, 0);
      const result = await new Promise(resolve => canvas.toBlob(resolve, "image/png"));
      if (!result) throw new Error("Gagal menyimpan rotasi halaman.");
      return result;
    } finally {
      bitmap.close();
      canvas.width = canvas.height = 0;
    }
  }

  async function savePage(previous, original, turns) {
    const id = previous?.id ?? sourceId;
    const rotating = previous?.original === original;
    preparingPage = true;
    render();
    try {
      const blob = await rotatedPng(original.blob, turns);
      const others = pages.filter(page => page !== previous);
      const pixels = others.reduce((sum, page) => sum + page.original.pixels, original.pixels);
      const bytes = others.reduce((sum, page) => sum + 4 + page.blob.size, 4 + blob.size);
      if (blob.size > 128 * 1024 * 1024) throw new Error("Ukuran halaman melebihi 128 MiB.");
      if (others.length >= 100 || pixels > 128_000_000 || bytes > 256 * 1024 * 1024) {
        throw new Error("Dokumen mencapai batas 100 halaman, 128 megapiksel total, atau 256 MiB. Unduh halaman yang sudah ditambahkan.");
      }
      const page = previous || newPage(id);
      if (previous) invalidate(page);
      else pages.push(page);
      Object.assign(page, { blob, original, turns });
      refresh();
      if (!rotating) panel.scrollIntoView({ block: "nearest" });
    } catch (error) {
      const message = rotating ? status : document.getElementById("corner-message");
      message.textContent = "Halaman gagal diperbarui. " + error.message;
    } finally {
      preparingPage = false;
      render();
    }
  }

  add.addEventListener("click", () => {
    if (add.disabled || !candidate) return;
    const previous = pages.find(page => page.id === sourceId);
    savePage(previous, candidate, previous?.turns || 0);
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

  function pdfFilename(value) {
    let stem = value.trim().replace(/[<>:"/\\|?*\u0000-\u001f\u007f]+/g, "-")
      .replace(/[.\s]+$/, "").replace(/(?:\.pdf\s*)+$/i, "")
      .replace(/^[.\s]+|[.\s]+$/g, "");
    if (!stem || /^-+$/.test(stem)) stem = "TrueScan";
    if (/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(stem)) stem = "_" + stem;
    return stem + ".pdf";
  }

  download.addEventListener("click", async () => {
    if (download.disabled) return;
    const filename = pdfFilename(documentName.value);
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
        method: "POST",
        headers: {
          "Content-Type": "application/octet-stream",
          "X-Document-Mode": mode.value,
          "X-Document-Page-Size": pageSize.value,
        },
        body: new Blob(parts),
      });
      const pdf = await checkedBlob(response, "application/pdf");
      if (downloadUrl) URL.revokeObjectURL(downloadUrl);
      downloadUrl = URL.createObjectURL(pdf);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = filename;
      document.body.append(link);
      link.click();
      link.remove();
      status.textContent = "Unduhan " + filename + " dimulai.";
    } catch (error) {
      status.textContent = "Unduhan gagal. " + errorText(error);
    } finally {
      exporting = false;
      render();
    }
  });
})();
