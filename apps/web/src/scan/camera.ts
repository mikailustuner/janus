/**
 * Camera scanning (experience design §6.1): the rear camera, a frame every 150 ms drawn to an
 * offscreen canvas and decoded on the device. Nothing is recorded or sent.
 */
import { decode } from "./zxing";

export type CameraError = "unavailable" | "denied";

export async function startCamera(
  video: HTMLVideoElement,
): Promise<MediaStream> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia)
    throw "unavailable" as CameraError;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment" },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    return stream;
  } catch (e) {
    throw (
      (e as { name?: string })?.name === "NotAllowedError"
        ? "denied"
        : "unavailable"
    ) as CameraError;
  }
}

export function stopCamera(stream: MediaStream | null) {
  stream?.getTracks().forEach((t) => t.stop());
}

/** Polls frames until a code is read or `signal` aborts. */
export async function scanFrames(
  video: HTMLVideoElement,
  signal: AbortSignal,
): Promise<string | null> {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return null;
  while (!signal.aborted) {
    if (video.videoWidth > 0) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      ctx.drawImage(video, 0, 0);
      const text = await decode(
        ctx.getImageData(0, 0, canvas.width, canvas.height),
      );
      if (text) return text;
    }
    await new Promise((r) => setTimeout(r, 150));
  }
  return null;
}

/** The current frame of the camera as a PNG, for the label photo. Not stored, not sent. */
export function captureFrame(video: HTMLVideoElement): Promise<Blob | null> {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx || canvas.width === 0) return Promise.resolve(null);
  ctx.drawImage(video, 0, 0);
  return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
}
