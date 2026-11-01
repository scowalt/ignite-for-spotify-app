import { describe, expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import {
  canonicalSiteUrl,
  getPageMetadata,
  pageMetadata,
  websiteStructuredData,
} from "../src/lib/pageMetadata";

describe("public page metadata", () => {
  test("uses unique, branded titles and unique descriptions", () => {
    const metadata = Object.values(pageMetadata);
    const titles = metadata.map((page) => page.title);
    const descriptions = metadata.map((page) => page.description);

    expect(new Set(titles).size).toBe(titles.length);
    expect(new Set(descriptions).size).toBe(descriptions.length);

    for (const page of metadata) {
      expect(page.title).toContain("Ignite for Spotify");
      expect(page.description.length).toBeGreaterThan(70);
      expect(page.description.length).toBeLessThanOrEqual(160);
    }
  });

  test("uses self-consistent canonical production URLs", () => {
    expect(pageMetadata["/"].canonicalUrl).toBe(`${canonicalSiteUrl}/`);

    for (const [route, metadata] of Object.entries(pageMetadata)) {
      expect(metadata.canonicalUrl).toBe(
        route === "/" ? `${canonicalSiteUrl}/` : `${canonicalSiteUrl}${route}`,
      );
    }
  });

  test("normalizes route trailing slashes", () => {
    expect(getPageMetadata("/privacy/")).toEqual(pageMetadata["/privacy"]);
    expect(getPageMetadata("/missing")).toBeUndefined();
  });

  test("identifies the canonical site with WebSite structured data", () => {
    expect(websiteStructuredData).toEqual({
      "@context": "https://schema.org",
      "@type": "WebSite",
      name: "Ignite for Spotify",
      url: `${canonicalSiteUrl}/`,
    });
  });
});

describe("crawler discovery files", () => {
  test("robots allows crawling and advertises the canonical sitemap", async () => {
    const robots = await readFile(
      resolve(import.meta.dir, "../public/robots.txt"),
      "utf8",
    );

    expect(robots).toContain("User-agent: *");
    expect(robots).toContain("Allow: /");
    expect(robots).toContain(
      `Sitemap: ${canonicalSiteUrl}/sitemap.xml`,
    );
  });

  test("sitemap contains exactly the canonical public routes", async () => {
    const sitemap = await readFile(
      resolve(import.meta.dir, "../public/sitemap.xml"),
      "utf8",
    );
    const locations = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map(
      (match) => match[1],
    );

    expect(locations).toEqual(
      Object.values(pageMetadata).map((metadata) => metadata.canonicalUrl),
    );
  });
});
