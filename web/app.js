const openCamera = document.getElementById("open-camera");
const takePhoto = document.getElementById("take-photo");
const switchCamera = document.getElementById("switch-camera");
const stopCamera = document.getElementById("stop-camera");
const photoFile = document.getElementById("photo-file");
const video = document.getElementById("camera-preview");
const canvas = document.getElementById("page-preview");
const emptyPreview = document.getElementById("empty-preview");
const statusMessage = document.getElementById("status");

let stream = null;
let cameras = [];
let selectedDeviceId = "";
let requestNumber = 0;
let hasPage = false;

function stopTracks(source) {
  for (const track of source.getTracks()) {
    track.stop();
  }
}

function releaseCamera() {
  if (stream) {
    stopTracks(stream);
    stream = null;
  }
  video.srcObject = null;
  video.hidden = true;
  takePhoto.hidden = true;
  takePhoto.disabled = true;
  switchCamera.hidden = true;
  cameras = [];
  selectedDeviceId = "";
  stopCamera.hidden = true;
  openCamera.hidden = false;
  canvas.hidden = !hasPage;
  emptyPreview.hidden = hasPage;
}

function notifyPage(eventName) {
  if (hasPage) document.dispatchEvent(new Event(eventName));
}

function cancelCamera(message, pageEvent = "page-resume") {
  requestNumber++;
  releaseCamera();
  statusMessage.textContent = message;
  openCamera.focus();
  notifyPage(pageEvent);
}

function drawPage(source, width, height) {
  if (!width || !height) {
    throw new Error("Ukuran gambar tidak tersedia.");
  }
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("Pratinjau tidak tersedia.");
  }
  canvas.width = width;
  canvas.height = height;
  hasPage = false;
  context.drawImage(source, 0, 0, width, height);
  hasPage = true;
  canvas.hidden = false;
  emptyPreview.hidden = true;
}

async function updateCameraChoices(request) {
  let devices = [];
  try {
    devices = await navigator.mediaDevices.enumerateDevices();
  } catch {
    // A browser may permit capture but withhold the list of available cameras.
  }
  if (request !== requestNumber || !stream) return;
  cameras = devices.filter(device => device.kind === "videoinput" && device.deviceId);
  switchCamera.hidden = cameras.length < 2;
}

async function startCamera(constraints, alternateDeviceId) {
  const request = ++requestNumber;
  releaseCamera();
  if (!navigator.mediaDevices?.getUserMedia) {
    notifyPage("page-resume");
    statusMessage.textContent = "Kamera tidak tersedia di browser ini. Pilih Impor foto.";
    return;
  }
  notifyPage("page-suspend");
  openCamera.hidden = true;
  stopCamera.hidden = false;
  statusMessage.textContent = alternateDeviceId ? "Mengganti kamera…" : "Menunggu izin kamera…";
  stopCamera.focus();
  try {
    let acquired;
    let requestedId = constraints.deviceId?.exact;
    try {
      acquired = await navigator.mediaDevices.getUserMedia({ video: constraints, audio: false });
    } catch (error) {
      // Devices with multiple rear lenses can lack support for an exact facing mode.
      if (request !== requestNumber || !constraints.facingMode?.exact || !alternateDeviceId ||
          !["NotFoundError", "OverconstrainedError"].includes(error.name)) throw error;
      acquired = await navigator.mediaDevices.getUserMedia({
        video: { deviceId: { exact: alternateDeviceId } }, audio: false,
      });
      requestedId = alternateDeviceId;
    }
    if (request !== requestNumber) {
      stopTracks(acquired);
      return;
    }
    stream = acquired;
    selectedDeviceId = requestedId || "";
    for (const track of stream.getVideoTracks()) {
      track.addEventListener("ended", () => {
        if (request === requestNumber) {
          cancelCamera("Kamera terputus. Buka kamera kembali atau pilih Impor foto.");
        }
      }, { once: true });
    }
    video.muted = true;
    video.playsInline = true;
    video.srcObject = stream;
    canvas.hidden = true;
    emptyPreview.hidden = true;
    video.hidden = false;
    await video.play();
    if (request !== requestNumber) return;
    takePhoto.hidden = false;
    takePhoto.disabled = false;
    statusMessage.textContent = "Kamera aktif. Posisikan dokumen, lalu ambil foto.";
    await updateCameraChoices(request);
  } catch (error) {
    if (request !== requestNumber) return;
    const denied = error.name === "NotAllowedError" || error.name === "SecurityError";
    cancelCamera(denied
      ? "Izin kamera ditolak. Pilih Impor foto untuk melanjutkan."
      : "Kamera gagal dibuka. Pilih Impor foto untuk melanjutkan.");
  }
}

openCamera.addEventListener("click", () => startCamera({ facingMode: { ideal: "environment" } }));

switchCamera.addEventListener("click", () => {
  if (!stream || cameras.length < 2) return;
  const track = stream.getVideoTracks()[0];
  const settings = track.getSettings();
  const currentId = settings.deviceId || selectedDeviceId;
  const current = cameras.findIndex(device =>
    device.deviceId === currentId || (!currentId && track.label && device.label === track.label)
  );
  const next = cameras[(current + 1) % cameras.length].deviceId;
  const hasFacing = settings.facingMode === "environment" || settings.facingMode === "user";
  if ((cameras.length > 2 || current < 0) && hasFacing) {
    const facing = settings.facingMode === "environment" ? "user" : "environment";
    startCamera({ facingMode: { exact: facing } }, next);
  } else {
    startCamera({ deviceId: { exact: next } }, next);
  }
});

navigator.mediaDevices?.addEventListener?.("devicechange", () => {
  if (stream && !takePhoto.hidden) updateCameraChoices(requestNumber);
});

takePhoto.addEventListener("click", () => {
  if (!stream || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
    statusMessage.textContent = "Menunggu gambar dari kamera. Coba ambil foto lagi.";
    return;
  }
  try {
    drawPage(video, video.videoWidth, video.videoHeight);
    cancelCamera("Foto berhasil diambil.", "page-ready");
  } catch {
    cancelCamera("Foto gagal diambil. Buka kamera kembali atau pilih Impor foto.");
  }
});

stopCamera.addEventListener("click", () => cancelCamera("Kamera ditutup."));

async function hasSupportedFormat(file) {
  const header = new Uint8Array(await file.slice(0, 12).arrayBuffer());
  const matches = (offset, bytes) => bytes.every((byte, i) => header[offset + i] === byte);
  return matches(0, [0xff, 0xd8, 0xff]) ||
    matches(0, [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]) ||
    (matches(0, [0x52, 0x49, 0x46, 0x46]) && matches(8, [0x57, 0x45, 0x42, 0x50]));
}

photoFile.addEventListener("change", async () => {
  const file = photoFile.files[0];
  if (!file) return;
  photoFile.value = "";
  const request = ++requestNumber;
  releaseCamera();
  notifyPage("page-suspend");
  statusMessage.textContent = "Membuka foto…";
  let url;
  try {
    const supported = await hasSupportedFormat(file);
    if (request !== requestNumber) return;
    if (!supported) {
      notifyPage("page-resume");
      statusMessage.textContent = "Format foto tidak didukung. Pilih JPEG, PNG, atau WebP.";
      return;
    }
    const photo = new Image();
    url = URL.createObjectURL(file);
    photo.src = url;
    // Browser decoding applies EXIF orientation to both dimensions and drawing.
    await photo.decode();
    if (request !== requestNumber) return;
    drawPage(photo, photo.naturalWidth, photo.naturalHeight);
    statusMessage.textContent = "Foto berhasil diimpor.";
    notifyPage("page-ready");
  } catch {
    if (request !== requestNumber) return;
    canvas.hidden = !hasPage;
    emptyPreview.hidden = hasPage;
    notifyPage("page-resume");
    statusMessage.textContent = "Foto gagal dibaca. Pilih foto lain.";
  } finally {
    if (url) URL.revokeObjectURL(url);
  }
});

window.addEventListener("pagehide", () => {
  notifyPage("page-suspend");
  requestNumber++;
  releaseCamera();
  statusMessage.textContent = hasPage ? "Foto siap di pratinjau." : "Siap mengambil halaman.";
});

window.addEventListener("pageshow", event => {
  if (event.persisted) notifyPage("page-resume");
});
