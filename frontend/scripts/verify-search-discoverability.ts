import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import {
  canonicalSiteUrl,
  pageMetadata,
  websiteStructuredData,
  type PublicPagePath,
} from "../src/lib/pageMetadata";

const args = process.argv.slice(2);
const distIndex = args.indexOf("--dist");
const urlIndex = args.indexOf("--url");

if ((distIndex === -1) === (urlIndex === -1)) {
  throw new Error("Use exactly one of --dist <directory> or --url <base-url>.");
}

const errors: string[] = [];

function check(condition: boolean, message: string) {
  if (!condition) errors.push(message);
}

function parseAttributes(tag: string) {
  const attributes = new Map<string, string>();
  const pattern = /([:\w-]+)="([^"]*)"/g;

  for (const match of tag.matchAll(pattern)) {
    attributes.set(match[1], match[2]);
  }

  return attributes;
}

function tagsNamed(html: string, tagName: string) {
  return html.match(new RegExp(`<${tagName}\\b[^>]*>`, "gi")) ?? [];
}

function metadataContent(
  html: string,
  attribute: "name" | "property",
  key: string,
) {
  return tagsNamed(html, "meta")
    .map(parseAttributes)
    .filter((attributes) => attributes.get(attribute) === key)
    .map((attributes) => attributes.get("content") ?? "");
}

function linkHref(html: string, relationship: string) {
  return tagsNamed(html, "link")
    .map(parseAttributes)
    .filter((attributes) => attributes.get("rel") === relationship)
    .map((attributes) => attributes.get("href") ?? "");
}

function titleContent(html: string) {
  return [...html.matchAll(/<title>([^<]*)<\/title>/gi)].map(
    (match) => match[1],
  );
}

function structuredDataContent(html: string) {
  const match = html.match(
    /<script\b[^>]*id="ignite-website-structured-data"[^>]*>([^<]*)<\/script>/i,
  );
  return match?.[1];
}

function verifyPageHtml(route: PublicPagePath, html: string) {
  const expected = pageMetadata[route];
  const label = route === "/" ? "home" : route;
  const titles = titleContent(html);
  const descriptions = metadataContent(html, "name", "description");
  const canonicals = linkHref(html, "canonical");

  check(
    titles.length === 1 && titles[0] === expected.title,
    `${label}: expected exactly one matching title`,
  );
  check(
    descriptions.length === 1 && descriptions[0] === expected.description,
    `${label}: expected exactly one matching description`,
  );
  check(
    canonicals.length === 1 && canonicals[0] === expected.canonicalUrl,
    `${label}: expected exactly one matching canonical`,
  );
  check(
    metadataContent(html, "property", "og:title")[0] === expected.title,
    `${label}: Open Graph title does not match`,
  );
  check(
    metadataContent(html, "property", "og:description")[0] ===
      expected.description,
    `${label}: Open Graph description does not match`,
  );
  check(
    metadataContent(html, "property", "og:url")[0] ===
      expected.canonicalUrl,
    `${label}: Open Graph URL does not match`,
  );
  check(
    metadataContent(html, "property", "og:site_name")[0] ===
      "Ignite for Spotify",
    `${label}: Open Graph site name is missing`,
  );
  check(!/\bnoindex\b/i.test(html), `${label}: unexpectedly blocks indexing`);

  const structuredData = structuredDataContent(html);
  if (route === "/") {
    try {
      check(
        JSON.stringify(JSON.parse(structuredData ?? "")) ===
          JSON.stringify(websiteStructuredData),
        "home: WebSite structured data does not match",
      );
    } catch {
      errors.push("home: WebSite structured data is not valid JSON");
    }
  } else {
    check(!structuredData, `${label}: unexpected WebSite structured data`);
  }
}

function verifyCrawlerFiles(robots: string, sitemap: string) {
  check(/^User-agent:\s*\*$/im.test(robots), "robots.txt has no wildcard agent");
  check(/^Allow:\s*\/$/im.test(robots), "robots.txt does not allow the site");
  check(
    new RegExp(
      `^Sitemap:\\s*${canonicalSiteUrl.replace(/\./g, "\\.")}/sitemap\\.xml$`,
      "im",
    ).test(robots),
    "robots.txt does not reference the canonical sitemap",
  );

  const locations = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map(
    (match) => match[1],
  );
  const expectedLocations = Object.values(pageMetadata).map(
    (metadata) => metadata.canonicalUrl,
  );
  check(
    JSON.stringify(locations) === JSON.stringify(expectedLocations),
    "sitemap.xml does not contain exactly the canonical public routes",
  );
  check(
    sitemap.includes('xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'),
    "sitemap.xml is missing the sitemap protocol namespace",
  );
}

function routeFile(route: PublicPagePath) {
  return route === "/" ? "index.html" : `${route.slice(1)}/index.html`;
}

async function verifyDist(directory: string) {
  const resolvedDirectory = resolve(directory);
  for (const route of Object.keys(pageMetadata) as PublicPagePath[]) {
    const html = await readFile(resolve(resolvedDirectory, routeFile(route)), "utf8");
    verifyPageHtml(route, html);
  }

  const robots = await readFile(resolve(resolvedDirectory, "robots.txt"), "utf8");
  const sitemap = await readFile(resolve(resolvedDirectory, "sitemap.xml"), "utf8");
  verifyCrawlerFiles(robots, sitemap);
}

async function fetchText(
  url: string,
  expectedStatus: number,
  expectedContentType: string,
) {
  const response = await fetch(url, { redirect: "manual" });
  check(response.status === expectedStatus, `${url}: returned ${response.status}`);
  check(
    response.headers.get("content-type")?.includes(expectedContentType) ?? false,
    `${url}: expected content type containing ${expectedContentType}`,
  );
  return response.text();
}

async function verifyRedirect(from: string, expectedLocation: string) {
  const response = await fetch(from, { redirect: "manual" });
  const location = response.headers.get("location");
  check(
    response.status === 301 || response.status === 308,
    `${from}: expected a permanent redirect, received ${response.status}`,
  );
  check(
    location !== null && new URL(location, from).href === expectedLocation,
    `${from}: expected redirect to ${expectedLocation}`,
  );
}

async function verifyUrl(baseUrl: string) {
  const base = new URL(baseUrl);
  base.pathname = "/";
  base.search = "";
  base.hash = "";

  for (const route of Object.keys(pageMetadata) as PublicPagePath[]) {
    const url = new URL(route, base);
    const html = await fetchText(url.href, 200, "text/html");
    verifyPageHtml(route, html);
  }

  const robotsUrl = new URL("/robots.txt", base).href;
  const sitemapUrl = new URL("/sitemap.xml", base).href;
  const robots = await fetchText(robotsUrl, 200, "text/plain");
  const sitemap = await fetchText(sitemapUrl, 200, "xml");
  verifyCrawlerFiles(robots, sitemap);

  const notFound = await fetch(new URL("/__ignite_indexability_check__", base), {
    redirect: "manual",
  });
  check(notFound.status === 404, `unknown path returned ${notFound.status}, not 404`);

  await verifyRedirect(new URL("/match/", base).href, `${base.origin}/match`);
  await verifyRedirect(
    new URL("/spotify-to-ignition", base).href,
    `${base.origin}/match`,
  );
  await verifyRedirect(
    new URL("/ignition-to-spotify", base).href,
    `${base.origin}/discover`,
  );

  if (base.origin === canonicalSiteUrl) {
    await verifyRedirect(`http://${base.host}/`, `${canonicalSiteUrl}/`);
    await verifyRedirect(`https://www.${base.host}/`, `${canonicalSiteUrl}/`);
  }
}

if (distIndex !== -1) {
  const directory = args[distIndex + 1];
  if (!directory) throw new Error("--dist requires a directory.");
  await verifyDist(directory);
} else {
  const baseUrl = args[urlIndex + 1];
  if (!baseUrl) throw new Error("--url requires a base URL.");
  await verifyUrl(baseUrl);
}

const titles = Object.values(pageMetadata).map((metadata) => metadata.title);
const descriptions = Object.values(pageMetadata).map(
  (metadata) => metadata.description,
);
check(new Set(titles).size === titles.length, "page titles are not unique");
check(
  new Set(descriptions).size === descriptions.length,
  "page descriptions are not unique",
);

if (errors.length > 0) {
  throw new Error(`Search discoverability verification failed:\n- ${errors.join("\n- ")}`);
}

console.log(
  `Search discoverability verification passed for ${
    distIndex !== -1 ? resolve(args[distIndex + 1]) : args[urlIndex + 1]
  }`,
);
