import { useImageSource } from "../../api/images";

/**
 * A work sample from an activity. Photos show small and open full size; a PDF
 * shows as a tile. Files are fetched with the family's sign-in, like covers.
 */
export function ActivityPhoto({ filePath, label }: { filePath: string; label: string }) {
  const pdf = filePath.toLowerCase().endsWith(".pdf");
  const source = useImageSource(`/api/evidence/files/${filePath}`);
  if (!source) return <span className="photo-thumb photo-loading" aria-label={`${label}: loading`} />;
  return (
    <a className="photo-thumb" href={source} target="_blank" rel="noreferrer" aria-label={`Open ${pdf ? "the PDF" : "the photo"} from ${label}`}>
      {pdf ? <span className="photo-pdf">PDF</span> : <img src={source} alt="" loading="lazy" />}
    </a>
  );
}
