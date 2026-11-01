import { defineConfig, type HtmlTagDescriptor, type Plugin } from "vite";
import solid from "vite-plugin-solid";
import path from "path";
import {
  pageMetadata,
  type PublicPagePath,
  websiteStructuredData,
} from "./src/lib/pageMetadata";

const htmlEntryPathByRoute: Record<PublicPagePath, string> = {
  "/": path.resolve(__dirname, "index.html"),
  "/match": path.resolve(__dirname, "match/index.html"),
  "/discover": path.resolve(__dirname, "discover/index.html"),
  "/privacy": path.resolve(__dirname, "privacy/index.html"),
};

const htmlInputs = Object.fromEntries(
  Object.entries(htmlEntryPathByRoute).map(([route, filename]) => [
    route === "/" ? "home" : route.slice(1),
    filename,
  ]),
);

function metadataForHtmlFile(filename: string) {
  const resolvedFilename = path.resolve(filename);
  const route = Object.entries(htmlEntryPathByRoute).find(
    ([, entryFilename]) => entryFilename === resolvedFilename,
  )?.[0] as PublicPagePath | undefined;

  return route ? { route, metadata: pageMetadata[route] } : undefined;
}

function routeMetadataPlugin(): Plugin {
  return {
    name: "ignite-route-metadata",
    transformIndexHtml: {
      order: "pre",
      handler(html, context) {
        const page = metadataForHtmlFile(context.filename);
        if (!page) return html;

        const tags: HtmlTagDescriptor[] = [
          {
            tag: "title",
            children: page.metadata.title,
            injectTo: "head",
          },
          {
            tag: "meta",
            attrs: {
              name: "description",
              content: page.metadata.description,
            },
            injectTo: "head",
          },
          {
            tag: "link",
            attrs: { rel: "canonical", href: page.metadata.canonicalUrl },
            injectTo: "head",
          },
          {
            tag: "meta",
            attrs: { property: "og:title", content: page.metadata.title },
            injectTo: "head",
          },
          {
            tag: "meta",
            attrs: {
              property: "og:description",
              content: page.metadata.description,
            },
            injectTo: "head",
          },
          {
            tag: "meta",
            attrs: {
              property: "og:url",
              content: page.metadata.canonicalUrl,
            },
            injectTo: "head",
          },
          {
            tag: "meta",
            attrs: { property: "og:type", content: "website" },
            injectTo: "head",
          },
          {
            tag: "meta",
            attrs: {
              property: "og:site_name",
              content: "Ignite for Spotify",
            },
            injectTo: "head",
          },
        ];

        if (page.route === "/") {
          tags.push({
            tag: "script",
            attrs: {
              id: "ignite-website-structured-data",
              type: "application/ld+json",
            },
            children: JSON.stringify(websiteStructuredData),
            injectTo: "head",
          });
        }

        return { html, tags };
      },
    },
  };
}

export default defineConfig({
  plugins: [solid(), routeMetadataPlugin()],
  build: {
    sourcemap: "hidden",
    rollupOptions: {
      input: htmlInputs,
      output: {
        manualChunks: {
          sentry: ["@sentry/browser"],
          posthog: ["posthog-js"],
        },
      },
    },
  },
  resolve: {
    alias: {
      "~": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:5000",
        changeOrigin: true,
      },
      "/hubs": {
        target: "http://localhost:5000",
        ws: true,
      },
    },
  },
});
