import type { Sticker } from "../lib/stickers";
import { StickerBadge } from "./StickerIcon";

/** Shown once every stop is done: the day's seasonal sticker. */
export function CampBanner({ prize }: { prize: Sticker }) {
  return (
    <section className="kid-card camp-banner" aria-live="polite">
      <StickerBadge sticker={prize} size={88} tilt={-8} />
      <div>
        <h2 className="kid-card-title">You reached camp!</h2>
        <p className="camp-banner-line">You earned the {prize.label} sticker. Great work today.</p>
      </div>
    </section>
  );
}
