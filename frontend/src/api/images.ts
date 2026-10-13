import { useQuery } from "@tanstack/react-query";

import { readToken } from "./client";

/**
 * An image the API serves only to a signed-in family (an uploaded cover, a
 * catalog cover). `<img>` can't send the sign-in token, so it's fetched with
 * it and shown from memory. Other URLs (the book lookup's covers) pass through.
 */
export function useImageSource(url: string | null | undefined): string | null {
  const protectedUrl = Boolean(url?.startsWith("/api/"));
  const query = useQuery({
    queryKey: ["image", url],
    enabled: protectedUrl && typeof URL.createObjectURL === "function",
    staleTime: Infinity,
    retry: false,
    queryFn: async () => {
      const token = readToken();
      const response = await fetch(url as string, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      if (!response.ok) throw new Error(`Image ${response.status}`);
      return URL.createObjectURL(await response.blob());
    },
  });
  if (!url) return null;
  return protectedUrl ? (query.data ?? null) : url;
}
