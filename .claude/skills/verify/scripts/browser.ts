import { appendFileSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, isAbsolute, join } from "node:path";
import type * as Playwright from "playwright-core";

type LocatorSpec =
  | { kind: "role"; role: string; name: string | undefined; exact: boolean }
  | { kind: "text"; text: string; exact: boolean }
  | { kind: "placeholder"; placeholder: string; exact: boolean }
  | { kind: "label"; label: string; exact: boolean };

type Flags = Map<string, string | true>;

const HELP = `Usage: ignite-verify browser <action> [locator] [options]

Actions:
  goto <path|url>                     Navigate; a path is resolved against WEB_URL
  click <locator>                     Click the element
  fill <locator> --value <text>       Replace the input's value
  check <locator> | uncheck <locator> Set a checkbox
  press --key <key> [locator]         Press a key (on the element, else the page)
  wait <locator>                      Wait until the element is visible
  wait-gone <locator>                 Wait until the element is hidden or detached
  wait-url <regex>                    Wait until the page URL matches
  text <locator>                      Print the element's innerText
  count <locator>                     Print how many elements match
  url                                 Print the current URL
  snapshot --path <file> [locator]    Write an ARIA snapshot (page or element) under EVIDENCE_DIR
  screenshot --path <file> [--full]   Write a PNG under EVIDENCE_DIR

Locator (exactly one):
  --role <role> [--name <accessible name>]
  --text <visible text>
  --placeholder <placeholder text>
  --label <associated label text>
  add --exact for exact, case-sensitive matching; add --nth <n> to pick one of several matches

Options:
  --timeout <ms>   default 10000
`;

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set; run through 'ignite-verify browser'`);
  return value;
}

function parseArgs(argv: string[]): { positional: string[]; flags: Flags } {
  const positional: string[] = [];
  const flags: Flags = new Map();
  for (let index = 0; index < argv.length; index++) {
    const arg = argv[index];
    if (!arg.startsWith("--")) {
      positional.push(arg);
      continue;
    }
    const key = arg.slice(2);
    const next = argv[index + 1];
    if (key === "exact" || key === "full") {
      flags.set(key, true);
    } else if (next === undefined) {
      throw new Error(`--${key} needs a value`);
    } else {
      flags.set(key, next);
      index++;
    }
  }
  return { positional, flags };
}

function stringFlag(flags: Flags, key: string): string | undefined {
  const value = flags.get(key);
  return typeof value === "string" ? value : undefined;
}

function parseLocator(flags: Flags): LocatorSpec | undefined {
  const exact = flags.get("exact") === true;
  const role = stringFlag(flags, "role");
  const text = stringFlag(flags, "text");
  const placeholder = stringFlag(flags, "placeholder");
  const label = stringFlag(flags, "label");
  const given = [role, text, placeholder, label].filter((value) => value !== undefined);
  if (given.length > 1) throw new Error("give exactly one of --role, --text, --placeholder, --label");
  if (role !== undefined) return { kind: "role", role, name: stringFlag(flags, "name"), exact };
  if (text !== undefined) return { kind: "text", text, exact };
  if (placeholder !== undefined) return { kind: "placeholder", placeholder, exact };
  if (label !== undefined) return { kind: "label", label, exact };
  return undefined;
}

function describe(spec: LocatorSpec): string {
  switch (spec.kind) {
    case "role":
      return spec.name === undefined ? `role=${spec.role}` : `role=${spec.role} name="${spec.name}"`;
    case "text":
      return `text="${spec.text}"`;
    case "placeholder":
      return `placeholder="${spec.placeholder}"`;
    case "label":
      return `label="${spec.label}"`;
    default: {
      const _exhaustive: never = spec;
      return _exhaustive;
    }
  }
}

function toLocator(page: Playwright.Page, spec: LocatorSpec, nth: string | undefined): Playwright.Locator {
  const locator = (() => {
    switch (spec.kind) {
      case "role":
        return page.getByRole(spec.role as Parameters<Playwright.Page["getByRole"]>[0], {
          name: spec.name,
          exact: spec.exact,
        });
      case "text":
        return page.getByText(spec.text, { exact: spec.exact });
      case "placeholder":
        return page.getByPlaceholder(spec.placeholder, { exact: spec.exact });
      case "label":
        return page.getByLabel(spec.label, { exact: spec.exact });
      default: {
        const _exhaustive: never = spec;
        return _exhaustive;
      }
    }
  })();
  return nth === undefined ? locator : locator.nth(Number(nth));
}

function evidencePath(evidenceDir: string, path: string): string {
  const resolved = isAbsolute(path) ? path : join(evidenceDir, path);
  mkdirSync(dirname(resolved), { recursive: true });
  return resolved;
}

async function run(): Promise<string> {
  const { positional, flags } = parseArgs(process.argv.slice(2));
  const [action, target] = positional;
  if (action === undefined || action === "help") return HELP;

  const webUrl = requireEnv("WEB_URL");
  const evidenceDir = requireEnv("EVIDENCE_DIR");
  const cdpPort = requireEnv("CDP_PORT");
  const tools = requireEnv("IGNITE_VERIFY_TOOLS");
  const timeout = Number(stringFlag(flags, "timeout") ?? "10000");
  const spec = parseLocator(flags);
  const nth = stringFlag(flags, "nth");

  const { chromium } = createRequire(join(tools, "package.json"))("playwright-core") as typeof Playwright;
  const browser = await chromium.connectOverCDP(`http://127.0.0.1:${cdpPort}`);
  try {
    const context = browser.contexts()[0] ?? (await browser.newContext());
    const page = context.pages()[0] ?? (await context.newPage());
    page.setDefaultTimeout(timeout);

    const locate = (): Playwright.Locator => {
      if (spec === undefined) throw new Error(`${action} needs a locator (--role/--text/--placeholder/--label)`);
      return toLocator(page, spec, nth);
    };
    const subject = spec === undefined ? "" : ` ${describe(spec)}${nth === undefined ? "" : ` nth=${nth}`}`;

    switch (action) {
      case "goto": {
        if (target === undefined) throw new Error("goto needs a path or URL");
        const response = await page.goto(new URL(target, webUrl).toString(), { waitUntil: "load" });
        return `goto ${page.url()} -> HTTP ${response?.status() ?? "none"}`;
      }
      case "click":
        await locate().click();
        await page.waitForLoadState("load");
        return `clicked${subject}; url ${page.url()}`;
      case "fill": {
        const value = stringFlag(flags, "value");
        if (value === undefined) throw new Error("fill needs --value");
        await locate().fill(value);
        return `filled${subject} with "${value}"`;
      }
      case "check":
        await locate().check();
        return `checked${subject}`;
      case "uncheck":
        await locate().uncheck();
        return `unchecked${subject}`;
      case "press": {
        const key = stringFlag(flags, "key");
        if (key === undefined) throw new Error("press needs --key");
        if (spec === undefined) await page.keyboard.press(key);
        else await locate().press(key);
        return `pressed ${key}${subject}`;
      }
      case "wait":
        await locate().first().waitFor({ state: "visible" });
        return `visible${subject}`;
      case "wait-gone":
        await locate().first().waitFor({ state: "hidden" });
        return `gone${subject}`;
      case "wait-url": {
        if (target === undefined) throw new Error("wait-url needs a regex");
        await page.waitForURL(new RegExp(target), { waitUntil: "commit" });
        return `url ${page.url()}`;
      }
      case "text":
        return (await locate().first().innerText()).trim();
      case "count":
        return String(await locate().count());
      case "url":
        return page.url();
      case "snapshot": {
        const path = stringFlag(flags, "path");
        if (path === undefined) throw new Error("snapshot needs --path");
        const root = spec === undefined ? page.locator("body") : locate();
        const snapshot = await root.ariaSnapshot();
        const file = evidencePath(evidenceDir, path);
        writeFileSync(file, `# ${page.url()}\n${snapshot}\n`);
        return `${snapshot}\nwrote ${file}`;
      }
      case "screenshot": {
        const path = stringFlag(flags, "path");
        if (path === undefined) throw new Error("screenshot needs --path");
        const file = evidencePath(evidenceDir, path);
        await page.screenshot({ path: file, fullPage: flags.get("full") === true });
        return `wrote ${file} (${page.url()})`;
      }
      default:
        throw new Error(`unknown action '${action}'\n\n${HELP}`);
    }
  } finally {
    await browser.close();
  }
}

function logAction(outcome: string): void {
  const evidenceDir = process.env.EVIDENCE_DIR;
  if (!evidenceDir) return;
  mkdirSync(evidenceDir, { recursive: true });
  const summary = outcome.split("\n").at(-1) ?? "";
  appendFileSync(
    join(evidenceDir, "actions.log"),
    `${new Date().toISOString()}\tbrowser ${process.argv.slice(2).join(" ")}\t${summary}\n`,
  );
}

try {
  const output = await run();
  logAction(output);
  console.log(output);
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  logAction(`FAILED: ${message.split("\n")[0]}`);
  console.error(`browser: ${message}`);
  process.exit(1);
}
