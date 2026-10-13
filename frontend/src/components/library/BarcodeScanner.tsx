import { useEffect, useId, useRef, useState } from "react";

import { readBarcodePhoto } from "../../api/parent";
import { isbnFromBarcode } from "../../lib/isbn";

interface DetectedBarcode {
  rawValue: string;
}

interface BarcodeDetectorLike {
  detect(source: HTMLVideoElement): Promise<DetectedBarcode[]>;
}

type BarcodeDetectorClass = new (options?: { formats: string[] }) => BarcodeDetectorLike;

function detectorClass(): BarcodeDetectorClass | null {
  const found = (window as unknown as { BarcodeDetector?: BarcodeDetectorClass }).BarcodeDetector;
  return found && typeof navigator.mediaDevices?.getUserMedia === "function" ? found : null;
}

/**
 * Scan the ISBN barcode on a book's back cover. Where the browser can read
 * barcodes (Chrome, Android), the camera reads it live; everywhere else
 * (iPhones), a photo of the barcode is read by Curiculy instead.
 */
export function BarcodeScanner({ onFound, onClose }: { onFound: (isbn: string) => void; onClose: () => void }) {
  const [live, setLive] = useState(() => detectorClass() !== null);
  const [message, setMessage] = useState("");
  const [reading, setReading] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const found = useRef(onFound);
  found.current = onFound;
  const fileId = useId();

  useEffect(() => {
    const Detector = detectorClass();
    if (!live || !Detector) return;
    let stream: MediaStream | null = null;
    let stopped = false;
    let timer = 0;
    const detector = new Detector({ formats: ["ean_13"] });

    const look = async () => {
      if (stopped || !video.current) return;
      try {
        for (const code of await detector.detect(video.current)) {
          const isbn = isbnFromBarcode(code.rawValue);
          if (isbn) {
            stopped = true;
            found.current(isbn);
            return;
          }
          if (code.rawValue) setMessage("That barcode isn't a book's ISBN. Look for the one that starts with 978 or 979.");
        }
      } catch {
        /* not ready yet: try the next frame */
      }
      timer = window.setTimeout(look, 250);
    };

    void (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
        if (stopped || !video.current) return;
        video.current.srcObject = stream;
        await video.current.play();
        void look();
      } catch {
        setMessage("The camera isn't available here (it needs your permission). Take a photo of the barcode instead.");
        setLive(false);
      }
    })();

    return () => {
      stopped = true;
      window.clearTimeout(timer);
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [live]);

  const readPhoto = async (file: File) => {
    setReading(true);
    setMessage("");
    try {
      const result = await readBarcodePhoto(file);
      if (result.isbn) found.current(result.isbn);
      else setMessage(result.message);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "That photo couldn't be read.");
    } finally {
      setReading(false);
    }
  };

  return (
    <section className="card stack" aria-label="Scan a barcode">
      {live ? (
        <div className="scanner-view">
          <video ref={video} muted playsInline aria-label="Camera view" />
          <span className="scanner-guide" aria-hidden="true" />
        </div>
      ) : null}
      <p className="step-lede">
        {live
          ? "Point the camera at the barcode on the back cover. It's read as soon as it's in focus."
          : "Take a photo of the barcode on the back cover: close up, flat and in focus."}
      </p>
      <div className="row">
        <label className="btn btn-small" htmlFor={fileId}>
          {reading ? "Reading the photo…" : "Take a photo of the barcode"}
        </label>
        <input
          id={fileId}
          className="sr-only"
          type="file"
          accept="image/*"
          capture="environment"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void readPhoto(file);
            event.target.value = "";
          }}
        />
        <button type="button" className="btn btn-quiet btn-small" onClick={onClose}>
          Close the scanner
        </button>
      </div>
      {message ? (
        <p className="notice notice-warn" role="status">
          {message}
        </p>
      ) : null}
    </section>
  );
}
