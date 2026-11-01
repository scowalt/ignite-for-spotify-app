export const canonicalSiteUrl = "https://igniteforspotify.com";

export interface PageMetadata {
  title: string;
  description: string;
  canonicalUrl: string;
}

export const pageMetadata = {
  "/": {
    title: "Ignite for Spotify | Match Playlists with Rocksmith CDLC",
    description:
      "Match your Spotify playlists with community-created Rocksmith CDLC, then discover songs and build Spotify playlists from the CustomsForge catalog.",
    canonicalUrl: `${canonicalSiteUrl}/`,
  },
  "/match": {
    title: "Match Spotify Playlists to Rocksmith CDLC | Ignite for Spotify",
    description:
      "Connect Spotify to find Rocksmith CDLC for songs in your playlists, review matches, and open community download pages.",
    canonicalUrl: `${canonicalSiteUrl}/match`,
  },
  "/discover": {
    title: "Discover Rocksmith CDLC | Ignite for Spotify",
    description:
      "Search the Rocksmith CDLC catalog, filter by arrangement, and export selected songs to a Spotify playlist.",
    canonicalUrl: `${canonicalSiteUrl}/discover`,
  },
  "/privacy": {
    title: "Privacy | Ignite for Spotify",
    description:
      "Learn how Ignite for Spotify handles Spotify account data, playlists, analytics, diagnostics, retention, and deletion requests.",
    canonicalUrl: `${canonicalSiteUrl}/privacy`,
  },
} as const satisfies Record<string, PageMetadata>;

export type PublicPagePath = keyof typeof pageMetadata;

export const websiteStructuredData = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "Ignite for Spotify",
  url: `${canonicalSiteUrl}/`,
} as const;

export function getPageMetadata(pathname: string): PageMetadata | undefined {
  const normalizedPath =
    pathname.length > 1 && pathname.endsWith("/")
      ? pathname.slice(0, -1)
      : pathname;

  return pageMetadata[normalizedPath as PublicPagePath];
}

function upsertMeta(
  documentRef: Document,
  attribute: "name" | "property",
  key: string,
  content: string,
) {
  let element = documentRef.head.querySelector<HTMLMetaElement>(
    `meta[${attribute}="${key}"]`,
  );

  if (!element) {
    element = documentRef.createElement("meta");
    element.setAttribute(attribute, key);
    documentRef.head.append(element);
  }

  element.content = content;
}

export function applyPageMetadata(
  pathname: string,
  documentRef: Document = document,
) {
  const metadata = getPageMetadata(pathname);
  if (!metadata) return;

  documentRef.title = metadata.title;
  upsertMeta(documentRef, "name", "description", metadata.description);
  upsertMeta(documentRef, "property", "og:title", metadata.title);
  upsertMeta(
    documentRef,
    "property",
    "og:description",
    metadata.description,
  );
  upsertMeta(documentRef, "property", "og:url", metadata.canonicalUrl);
  upsertMeta(documentRef, "property", "og:type", "website");
  upsertMeta(documentRef, "property", "og:site_name", "Ignite for Spotify");

  let canonicalLink =
    documentRef.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!canonicalLink) {
    canonicalLink = documentRef.createElement("link");
    canonicalLink.rel = "canonical";
    documentRef.head.append(canonicalLink);
  }
  canonicalLink.href = metadata.canonicalUrl;

  const structuredDataId = "ignite-website-structured-data";
  const existingStructuredData = documentRef.getElementById(structuredDataId);

  if (metadata.canonicalUrl === pageMetadata["/"].canonicalUrl) {
    const script =
      existingStructuredData ?? documentRef.createElement("script");
    script.id = structuredDataId;
    script.setAttribute("type", "application/ld+json");
    script.textContent = JSON.stringify(websiteStructuredData);
    if (!existingStructuredData) documentRef.head.append(script);
  } else {
    existingStructuredData?.remove();
  }
}
