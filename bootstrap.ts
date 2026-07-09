#!/usr/bin/env bun
/**
 * Hephaestus — generic bootstrap
 * Idempotent: safe to re-run after editing templates or adapters.
 *
 * Usage:
 *   bun bootstrap.ts --help
 *   bun bootstrap.ts --dry-run <repo-dir> --adapter <name>
 *   bun bootstrap.ts <repo-dir> --adapter <name>
 */

import { existsSync, mkdirSync, cpSync, readdirSync } from "fs";
import { join, dirname, resolve } from "path";
import { fileURLToPath } from "url";
import { load as yamlLoad, dump as yamlDump } from "js-yaml";

// ─── Paths ──────────────────────────────────────────────────────────────────

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const TEMPLATES_DIR = join(SCRIPT_DIR, "templates");
const ADAPTERS_DIR = join(SCRIPT_DIR, "adapters");
const HERMES_SCRIPTS = join(
  process.env.HOME || process.env.USERPROFILE || "~",
  ".hermes",
  "scripts",
);

const HEPHAESTUS_DIR = join(
  process.env.HOME || process.env.USERPROFILE || "~",
  ".hephaestus",
);
const REGISTRY_PATH = join(HEPHAESTUS_DIR, "registry.yaml");

// ─── Types ──────────────────────────────────────────────────────────────────

interface AdapterConfig {
  project: {
    name: string;
    objective: string;
    board_name: string;
    board_desc: string;
  };
  hermes: {
    profile_orchestrator: string;
    profile_worker_prefix: string;
    worker_count: number;
    tick_name: string;
    tick_schedule: string;
    delivery: string;
    provider: {
      orchestrator: string;
      orchestrator_model: string;
      worker: string;
      worker_model: string;
      // Provider chains for LiteLLM fallback ("never-dies" guarantee)
      // Each chain ends with a local model (Ollama/LM Studio)
      orchestrator_chain?: string[];
      worker_chain?: string[];
      challenger_model?: string;
      challenger_chain?: string[];
      arbiter_model?: string;
      arbiter_chain?: string[];
    };
  };
  paths: { ledger: string };
  boundaries: {
    allowed: string[];
    forbidden: string[];
  };
  merge_policy: string;
  max_parallel_workers: number;
  max_llm_spend_per_day_usd: number;
  runner?: { command?: string };
  evidence?: { required_fields?: string[] };
}

// ─── Built-in defaults ──────────────────────────────────────────────────────

const DEFAULTS: AdapterConfig = {
  project: {
    name: "HermesProject",
    objective: "Improve the project through evidence-backed iteration.",
    board_name: "hermes-board",
    board_desc: "Hermes orchestration board",
  },
  hermes: {
    profile_orchestrator: "orchestrator",
    profile_worker_prefix: "worker",
    worker_count: 2,
    tick_name: "orchestrator-tick",
    tick_schedule: "every 1h",
    delivery: "local",
    provider: {
      orchestrator: "anthropic",
      orchestrator_model: "__NEEDS_LOCAL_VERIFICATION__",
      worker: "openrouter",
      worker_model: "__NEEDS_LOCAL_VERIFICATION__",
      orchestrator_chain: [
        "claude-sonnet-4-20250514",
        "deepseek/deepseek-chat",
        "ollama/llama3",
      ],
      worker_chain: [
        "deepseek/deepseek-chat",
        "ollama/llama3",
      ],
      challenger_model: "openrouter/deepseek/deepseek-chat",
      challenger_chain: [
        "deepseek/deepseek-chat",
        "ollama/llama3",
      ],
      arbiter_model: "anthropic/claude-sonnet-4-20250514",
      arbiter_chain: [
        "claude-sonnet-4-20250514",
        "deepseek/deepseek-chat",
        "ollama/llama3",
      ],
    },
  },
  paths: { ledger: ".orchestrator" },
  boundaries: {
    allowed: ["src/"],
    forbidden: ["vendor/"],
  },
  merge_policy: "pr_only",
  max_parallel_workers: 3,
  max_llm_spend_per_day_usd: 25,
};

// ─── Helpers ────────────────────────────────────────────────────────────────

function say(msg: string) {
  console.log(`\x1b[1;32m[hermes-setup]\x1b[0m ${msg}`);
}
function warn(msg: string) {
  console.log(`\x1b[1;33m[hermes-setup] WARN:\x1b[0m ${msg}`);
}
function die(msg: string): never {
  console.error(`\x1b[1;31m[hermes-setup] FATAL:\x1b[0m ${msg}`);
  process.exit(1);
}
function dry(msg: string) {
  console.log(`\x1b[1;34m[hermes-setup] DRY-RUN:\x1b[0m ${msg}`);
}
function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function toYamlList(items: string[]): string {
  return items.map((i) => `  - ${i}`).join("\n");
}

// ─── CLI args ───────────────────────────────────────────────────────────────

interface CliArgs {
  dryRun: boolean;
  adapter: string;
  repoDir: string;
}

function printHelp() {
  console.log(`
Hermes Orchestrator Pack — bootstrap

Usage:
  bun bootstrap.ts [--dry-run] [--adapter <name>] <repo-dir>

Options:
  --dry-run         Print actions without executing them
  --adapter <name>  Use project adapter from adapters/<name>/
  --help, -h        Show this help

Environment variables (override adapter config):
  HERMES_ORCH_PROVIDER   e.g. anthropic
  HERMES_ORCH_MODEL      e.g. claude-opus-4
  HERMES_WORKER_PROVIDER e.g. openrouter
  HERMES_WORKER_MODEL    e.g. deepseek/deepseek-v4-flash

Available adapters:
${(() => {
  try {
    return readdirSync(ADAPTERS_DIR, { withFileTypes: true })
      .filter((d: any) => d.isDirectory())
      .map((d: any) => `  ${d.name}`)
      .join("\n");
  } catch {
    return "  (none installed)";
  }
})()}

Examples:
  bun bootstrap.ts --help
  bun bootstrap.ts --dry-run /path/to/repo --adapter v7-alphaforge
  bun bootstrap.ts /path/to/repo --adapter v7-alphaforge
`);
}

function parseArgs(argv: string[]): CliArgs {
  const result: CliArgs = { dryRun: false, adapter: "", repoDir: "" };
  const positional: string[] = [];

  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else if (arg === "--dry-run") {
      result.dryRun = true;
    } else if (arg === "--adapter") {
      result.adapter = argv[++i];
      if (!result.adapter) die("--adapter requires a name argument");
    } else if (arg === "--") {
      // skip separator
    } else {
      positional.push(arg);
    }
  }

  result.repoDir = positional[0] || "";
  if (!result.repoDir && !result.adapter) {
    // no repo dir given and no adapter → could be just --help which we already handled
    die("Usage: bun bootstrap.ts [--dry-run] [--adapter <name>] <repo-dir>");
  }
  if (!existsSync(result.repoDir))
    die(`Directory not found: ${result.repoDir}`);

  result.repoDir = resolve(result.repoDir);
  return result;
}

// ─── Adapter loading ────────────────────────────────────────────────────────

async function loadAdapter(name: string): Promise<{ config: AdapterConfig; dir: string }> {
  const dir = join(ADAPTERS_DIR, name);
  if (!existsSync(dir)) die(`Adapter '${name}' not found at ${dir}`);

  const yamlFile = join(dir, "project.yaml");
  if (!existsSync(yamlFile)) die(`Adapter '${name}' has no project.yaml`);

  const raw = yamlLoad(await Bun.file(yamlFile).text()) as any;
  say(`loaded adapter: ${name} (${yamlFile})`);

  const c = raw.project || {};
  const h = raw.hermes || {};
  const p = h.provider || {};
  const paths = raw.paths || {};
  const bounds = raw.boundaries || {};

  const config: AdapterConfig = {
    project: {
      name: c.name || DEFAULTS.project.name,
      objective: c.objective || DEFAULTS.project.objective,
      board_name: c.board_name || DEFAULTS.project.board_name,
      board_desc: c.board_desc || DEFAULTS.project.board_desc,
    },
    hermes: {
      profile_orchestrator:
        h.profile_orchestrator || DEFAULTS.hermes.profile_orchestrator,
      profile_worker_prefix:
        h.profile_worker_prefix || DEFAULTS.hermes.profile_worker_prefix,
      worker_count: h.worker_count ?? DEFAULTS.hermes.worker_count,
      tick_name: h.tick_name || DEFAULTS.hermes.tick_name,
      tick_schedule: h.tick_schedule || DEFAULTS.hermes.tick_schedule,
      delivery: h.delivery || DEFAULTS.hermes.delivery,
      provider: {
        orchestrator: p.orchestrator || DEFAULTS.hermes.provider.orchestrator,
        orchestrator_model:
          p.orchestrator_model ||
          DEFAULTS.hermes.provider.orchestrator_model,
        worker: p.worker || DEFAULTS.hermes.provider.worker,
        worker_model: p.worker_model || DEFAULTS.hermes.provider.worker_model,
        orchestrator_chain: p.orchestrator_chain ?? DEFAULTS.hermes.provider.orchestrator_chain,
        worker_chain: p.worker_chain ?? DEFAULTS.hermes.provider.worker_chain,
        challenger_model: p.challenger_model ?? DEFAULTS.hermes.provider.challenger_model,
        challenger_chain: p.challenger_chain ?? DEFAULTS.hermes.provider.challenger_chain,
        arbiter_model: p.arbiter_model ?? DEFAULTS.hermes.provider.arbiter_model,
        arbiter_chain: p.arbiter_chain ?? DEFAULTS.hermes.provider.arbiter_chain,
      },
    },
    paths: {
      ledger: paths.ledger || DEFAULTS.paths.ledger,
    },
    boundaries: {
      allowed: bounds.allowed?.length
        ? bounds.allowed
        : DEFAULTS.boundaries.allowed,
      forbidden: bounds.forbidden?.length
        ? bounds.forbidden
        : DEFAULTS.boundaries.forbidden,
    },
    merge_policy: raw.merge_policy || DEFAULTS.merge_policy,
    max_parallel_workers:
      raw.max_parallel_workers ?? DEFAULTS.max_parallel_workers,
    max_llm_spend_per_day_usd:
      raw.max_llm_spend_per_day_usd ?? DEFAULTS.max_llm_spend_per_day_usd,
  };

  validateChainDecorrelation(config, name);

  return { config, dir };
}

// ─── Provider-chain decorrelation validation (#22) ─────────────────────────

function getModelFamily(modelId: string | undefined): string {
  if (!modelId) return "";
  // Strip provider prefix (e.g. "openrouter/deepseek/deepseek-chat" → "deepseek/deepseek-chat")
  let stripped = modelId;
  if (stripped.includes("/")) {
    const firstSlash = stripped.indexOf("/");
    const rest = stripped.slice(firstSlash + 1);
    // If rest has another slash, treat first segment as provider, second as family
    if (rest.includes("/")) {
      stripped = rest;
    }
  }
  // Family = first segment before any slash
  return stripped.split("/")[0] || "";
}

function validateChainDecorrelation(config: AdapterConfig, adapterName: string): void {
  const p = config.hermes.provider;
  const w0 = getModelFamily(p.worker_chain?.[0]);
  const c0 = getModelFamily(p.challenger_chain?.[0]);
  const o0 = getModelFamily(p.orchestrator_chain?.[0]);
  const a0 = getModelFamily(p.arbiter_chain?.[0]);

  if (w0 && c0 && w0 === c0) {
    die(
      `Adapter '${adapterName}': worker_chain[0] and challenger_chain[0] have the same model family "${w0}". ` +
      `They MUST be different for adversarial council decorrelation (issue #22).`,
    );
  }
  if (o0 && a0 && o0 === a0) {
    die(
      `Adapter '${adapterName}': orchestrator_chain[0] and arbiter_chain[0] have the same model family "${o0}". ` +
      `They MUST be different for adversarial council decorrelation (issue #22).`,
    );
  }
}

// ─── Template substitution ──────────────────────────────────────────────────

function makeSubstVars(
  config: AdapterConfig,
  repoDir: string,
  opts: {
    orchProvider: string;
    orchModel: string;
    workerProvider: string;
    workerModel: string;
  },
): Record<string, string> {
  const p = config.hermes.provider;
  return {
    __HERMES_PROJECT_NAME__: config.project.name,
    __HERMES_OBJECTIVE__: config.project.objective,
    __HERMES_BOARD_NAME__: config.project.board_name,
    __HERMES_BOARD_DESC__: config.project.board_desc,
    __HERMES_PROFILE_ORCHESTRATOR__: config.hermes.profile_orchestrator,
    __HERMES_PROFILE_WORKER_PREFIX__: config.hermes.profile_worker_prefix,
    __HERMES_WORKER_COUNT__: String(config.hermes.worker_count),
    __HERMES_TICK_NAME__: config.hermes.tick_name,
    __HERMES_TICK_SCHEDULE__: config.hermes.tick_schedule,
    __HERMES_DELIVERY__: config.hermes.delivery,
    __HERMES_ORCH_PROVIDER__: opts.orchProvider,
    __HERMES_ORCH_MODEL__: opts.orchModel,
    __HERMES_WORKER_PROVIDER__: opts.workerProvider,
    __HERMES_WORKER_MODEL__: opts.workerModel,
    __HERMES_LEDGER_DIR__: config.paths.ledger,
    __HERMES_MERGE_POLICY__: config.merge_policy,
    __HERMES_MAX_PARALLEL_WORKERS__: String(config.max_parallel_workers),
    __HERMES_MAX_SPEND_PER_DAY__: String(config.max_llm_spend_per_day_usd),
    __HERMES_REPO_DIR__: repoDir,
    __HERMES_ALLOWED_PATHS_YAML__: toYamlList(config.boundaries.allowed),
    __HERMES_FORBIDDEN_PATHS_YAML__: toYamlList(config.boundaries.forbidden),
    // LiteLLM provider chain vars
    __HERMES_ORCH_CHAIN_0__: (p.orchestrator_chain ?? [])[0] ?? opts.orchModel,
    __HERMES_ORCH_CHAIN_1__: (p.orchestrator_chain ?? [])[1] ?? (p.orchestrator_chain ?? [])[0] ?? opts.orchModel,
    __HERMES_ORCH_CHAIN_2__: (p.orchestrator_chain ?? [])[2] ?? (p.orchestrator_chain ?? [])[0] ?? opts.orchModel,
    __HERMES_WORKER_CHAIN_0__: (p.worker_chain ?? [])[0] ?? opts.workerModel,
    __HERMES_WORKER_CHAIN_1__: (p.worker_chain ?? [])[1] ?? (p.worker_chain ?? [])[0] ?? opts.workerModel,
    __HERMES_CHALLENGER_MODEL__: p.challenger_model ?? (p.worker_chain ?? [])[0] ?? opts.workerModel,
    __HERMES_CHALLENGER_CHAIN_0__: (p.challenger_chain ?? [])[0] ?? p.challenger_model ?? (p.worker_chain ?? [])[0] ?? opts.workerModel,
    __HERMES_CHALLENGER_CHAIN_1__: (p.challenger_chain ?? [])[1] ?? (p.challenger_chain ?? [])[0] ?? (p.worker_chain ?? [])[0] ?? opts.workerModel,
    __HERMES_ARBITER_MODEL__: p.arbiter_model ?? opts.orchModel,
    __HERMES_ARBITER_CHAIN_0__: (p.arbiter_chain ?? [])[0] ?? p.arbiter_model ?? opts.orchModel,
    __HERMES_ARBITER_CHAIN_1__: (p.arbiter_chain ?? [])[1] ?? (p.arbiter_chain ?? [])[0] ?? opts.orchModel,
    __HERMES_ARBITER_CHAIN_2__: (p.arbiter_chain ?? [])[2] ?? (p.arbiter_chain ?? [])[0] ?? opts.orchModel,
  };
}

function substitute(content: string, vars: Record<string, string>): string {
  let result = content;
  for (const [key, value] of Object.entries(vars)) {
    result = result.replaceAll(key, value);
  }
  return result;
}

async function subFile(
  filePath: string,
  vars: Record<string, string>,
): Promise<string> {
  const content = await Bun.file(filePath).text();
  return substitute(content, vars);
}

// ─── Hermes root detection ──────────────────────────────────────────────────

function findHermesBinary(): string {
  // Try PATH first
  const pathsToTry = [
    "hermes",
    join(
      process.env.HOME || "",
      "AppData/Local/hermes/hermes-agent/venv/Scripts/hermes.exe",
    ),
    "/c/Users/dresden/AppData/Local/hermes/hermes-agent/venv/Scripts/hermes.exe",
    join(
      process.env.USERPROFILE || "",
      "AppData/Local/hermes/hermes-agent/venv/Scripts/hermes.exe",
    ),
  ];

  for (const p of pathsToTry) {
    try {
      const r = Bun.spawnSync([p, "--version"], { shell: true });
      if (r.exitCode === 0) return p;
    } catch {
      // continue
    }
  }
  return "";
}

function detectHermesRoot(hermesBin: string): string {
  // Try HERMES_HOME env var
  if (
    process.env.HERMES_HOME &&
    existsSync(join(process.env.HERMES_HOME, "profiles"))
  ) {
    return process.env.HERMES_HOME;
  }

  // Parse from `hermes profile show default`
  try {
    const r = Bun.spawnSync([hermesBin, "profile", "show", "default"], {
      shell: true,
    });
    if (r.exitCode === 0) {
      const out = r.stdout.toString();
      const m = out.match(/Path:\s+(.+)/);
      if (m) return m[1].trim();
    }
  } catch {
    // fall through
  }

  // Fallback: known locations
  const home = process.env.HOME || process.env.USERPROFILE || "";
  for (const c of [
    join(home, ".hermes"),
    join(home, "AppData/Local/hermes"),
    "/c/Users/dresden/AppData/Local/hermes",
  ]) {
    if (existsSync(join(c, "profiles"))) return c;
  }

  return "";
}

// ─── Profile installation ───────────────────────────────────────────────────

async function installProfile(
  hermesBin: string,
  hermesRoot: string,
  name: string,
  configTpl: string,
  soulTpl: string,
  vars: Record<string, string>,
  isDryRun: boolean,
) {
  const dir = join(hermesRoot, "profiles", name);
  if (isDryRun) {
    dry(`install profile '${name}':`);
    dry(`  hermes profile create ${name} (if missing)`);
    dry(`  sub ${configTpl} > ${dir}/config.yaml`);
    dry(`  cp ${soulTpl} > ${dir}/SOUL.md`);
    return;
  }

  if (!existsSync(dir)) {
    const r = Bun.spawnSync(
      [
        hermesBin,
        "profile",
        "create",
        name,
        "--description",
        `Hermes profile: ${name}`,
      ],
      { shell: true },
    );
    if (r.exitCode !== 0) {
      warn(`hermes profile create ${name} failed — creating directory manually`);
    }
  }

  mkdirSync(dir, { recursive: true });
  const configYaml = await subFile(join(TEMPLATES_DIR, configTpl), vars);
  const soulMd = await subFile(join(TEMPLATES_DIR, soulTpl), vars);
  Bun.write(join(dir, "config.yaml"), configYaml);
  Bun.write(join(dir, "SOUL.md"), soulMd);
  say(`profile installed: ${name}`);
}

// ─── Registry update ──────────────────────────────────────────────────────────

interface RegistryEntry {
  name: string;
  adapter: string;
  repo: string;
  ledger: string;
  board: string;
  tick: string;
  profiles: string[];
  status: string;
  goal_status: string;
  registered_at: string;
  updated_at: string;
}

interface RegistryData {
  schema_version: number;
  projects: RegistryEntry[];
}

async function updateRegistry(
  config: AdapterConfig,
  repoDir: string,
  adapterName: string,
  profileNames: string[],
  isDryRun: boolean,
) {
  const now = new Date().toISOString();

  if (isDryRun) {
    dry(`update registry at ${REGISTRY_PATH}`);
    dry(`  register: ${config.project.name} (${repoDir})`);
    return;
  }

  mkdirSync(HEPHAESTUS_DIR, { recursive: true });

  // Read existing registry
  let registry: RegistryData = { schema_version: 1, projects: [] };
  if (existsSync(REGISTRY_PATH)) {
    try {
      const raw = yamlLoad(await Bun.file(REGISTRY_PATH).text()) as RegistryData;
      if (raw && Array.isArray(raw.projects)) registry = raw;
    } catch {
      warn(`Failed to parse existing registry at ${REGISTRY_PATH} — will overwrite`);
    }
  }

  // Find existing entry by repo path (idempotent)
  const existingIdx = registry.projects.findIndex((p) => p.repo === repoDir);

  const entry: RegistryEntry = {
    name: config.project.name,
    adapter: adapterName,
    repo: repoDir,
    ledger: config.paths.ledger,
    board: config.project.board_name,
    tick: config.hermes.tick_name,
    profiles: profileNames,
    status: "active",
    goal_status: "none",
    registered_at: existingIdx >= 0 ? registry.projects[existingIdx].registered_at : now,
    updated_at: now,
  };

  if (existingIdx >= 0) {
    registry.projects[existingIdx] = entry;
    say(`registry updated: ${config.project.name} (existing entry)`);
  } else {
    registry.projects.push(entry);
    say(`registry written: ${config.project.name} -> ${REGISTRY_PATH}`);
  }

  const yaml = yamlDump(registry, { indent: 2, lineWidth: -1, noRefs: true });
  Bun.write(REGISTRY_PATH, yaml);
}

// ─── Main ───────────────────────────────────────────────────────────────────

async function main() {
  const args = parseArgs(process.argv);
  const repoDir = args.repoDir;

  // Load adapter or use defaults
  let config: AdapterConfig;
  let adapterDir = "";
  if (args.adapter) {
    const loaded = await loadAdapter(args.adapter);
    config = loaded.config;
    adapterDir = loaded.dir;
  } else {
    config = DEFAULTS;
  }

  // Apply env overrides
  const orchProvider =
    process.env.HERMES_ORCH_PROVIDER || config.hermes.provider.orchestrator;
  const orchModel =
    process.env.HERMES_ORCH_MODEL || config.hermes.provider.orchestrator_model;
  const workerProvider =
    process.env.HERMES_WORKER_PROVIDER || config.hermes.provider.worker;
  const workerModel =
    process.env.HERMES_WORKER_MODEL || config.hermes.provider.worker_model;

  // Build template vars
  const opts = { orchProvider, orchModel, workerProvider, workerModel };
  const vars = makeSubstVars(config, repoDir, opts);

  say(`project: ${config.project.name}`);
  say(`repo:    ${repoDir}`);
  say(`ledger:  ${config.paths.ledger}`);
  say(`adapter: ${args.adapter || "default"}`);

  if (args.dryRun) {
    dry("mode: dry-run (no files will be written, no Hermes calls)");

    // ── Dry-run output ──
    const dr = (msg: string) => dry(msg);

    // Profile dry-runs
    const pOrch = config.hermes.profile_orchestrator;
    const pWkr = config.hermes.profile_worker_prefix;
    const pCnt = config.hermes.worker_count;

    dr(`install profile '${pOrch}':`);
    dr(`  hermes profile create ${pOrch} (if missing)`);
    dr(`  sub templates/config.orchestrator.yaml > profiles/${pOrch}/config.yaml`);
    dr(`  sub templates/SOUL.orchestrator.md > profiles/${pOrch}/SOUL.md`);

    for (let i = 1; i <= pCnt; i++) {
      dr(`install profile '${pWkr}-${i}':`);
      dr(`  hermes profile create ${pWkr}-${i} (if missing)`);
      dr(`  sub templates/config.worker.yaml > profiles/${pWkr}-${i}/config.yaml`);
      dr(`  sub templates/SOUL.worker.md > profiles/${pWkr}-${i}/SOUL.md`);
    }
    dr(`install profile '${pWkr}-challenger':`);
    dr(`  hermes profile create ${pWkr}-challenger (if missing) — read-only, blind evaluation`);
    dr(`  sub templates/config.worker.yaml > profiles/${pWkr}-challenger/config.yaml`);
    dr(`  sub templates/SOUL.worker.md > profiles/${pWkr}-challenger/SOUL.md`);
    dr(`install profile '${pWkr}-arbiter':`);
    dr(`  hermes profile create ${pWkr}-arbiter (if missing) — binding decision, premium model`);
    dr(`  sub templates/config.worker.yaml > profiles/${pWkr}-arbiter/config.yaml`);
    dr(`  sub templates/SOUL.worker.md > profiles/${pWkr}-arbiter/SOUL.md`);

    dr(`mkdir -p ${HERMES_SCRIPTS}`);
    dr(`sub templates/scripts/tick-gate.sh > ${HERMES_SCRIPTS}/${config.hermes.tick_name}-gate.sh`);

    // LiteLLM proxy config (dry-run)
    dr(`sub templates/litellm-config.yaml > ${HERMES_SCRIPTS}/litellm-config.yaml`);
    dr("LiteLLM proxy config generated — each profile has fallback chain ending in local model");

    const ledgerDir = join(repoDir, config.paths.ledger);
    dr(`mkdir -p ${ledgerDir}/{hypotheses,runs,reports}`);
    dr(`sub templates/control.yaml > ${ledgerDir}/control.yaml (only if missing)`);
    dr(`sub templates/state.json > ${ledgerDir}/state.json (only if missing)`);

    if (args.adapter) {
      const hypFile = join(ADAPTERS_DIR, args.adapter, "hypotheses.seed.yaml");
      if (existsSync(hypFile)) dr(`cp hypotheses.seed.yaml > ${ledgerDir}/hypotheses/`);
      const agFile = join(ADAPTERS_DIR, args.adapter, "AGENTS.adapter.md");
      if (existsSync(agFile)) dr(`cp AGENTS.adapter.md > ${join(repoDir, "AGENTS.md")} (only if missing)`);
    } else {
      dr(`sub templates/AGENTS.md > ${join(repoDir, "AGENTS.md")} (only if missing)`);
    }

    // Registry update (dry-run)
    const dryProfiles = [
      pOrch,
      ...Array.from({ length: pCnt }, (_, i) => `${pWkr}-${i + 1}`),
    ];
    await updateRegistry(config, repoDir, args.adapter || "default", dryProfiles, true);
  }

  // ── Preflight ──
  if (!args.dryRun) {
    const hermesBin = findHermesBinary();
    if (!hermesBin) {
      die("hermes not found on PATH. Install it first: https://github.com/NousResearch/hermes-agent");
    }
    const ver = Bun.spawnSync([hermesBin, "--version"], { shell: true });
    say(`hermes: ${ver.stdout.toString().trim() || "version unknown"}`);

    const hermesRoot = detectHermesRoot(hermesBin);
    if (!hermesRoot) {
      die("Could not detect Hermes home directory. Try setting HERMES_HOME env var.");
    }
    say(`hermes root: ${hermesRoot}`);

    // Check .env
    const envFile = join(hermesRoot, ".env");
    if (!existsSync(envFile)) {
      cpSync(join(SCRIPT_DIR, "env.example"), envFile);
      warn(`Created ${envFile} from template — EDIT IT and add real API keys, then re-run.`);
      process.exit(0);
    }
    const envContent = await Bun.file(envFile).text();
    if (envContent.includes("REPLACE_ME")) {
      die(`${envFile} still contains REPLACE_ME placeholders. Fill in keys first.`);
    }

    mkdirSync(join(hermesRoot, "profiles"), { recursive: true });

    // ── Profiles ──
    await installProfile(
      hermesBin, hermesRoot,
      config.hermes.profile_orchestrator,
      "config.orchestrator.yaml",
      "SOUL.orchestrator.md",
      vars,
      false,
    );
    for (let i = 1; i <= config.hermes.worker_count; i++) {
      await installProfile(
        hermesBin, hermesRoot,
        `${config.hermes.profile_worker_prefix}-${i}`,
        "config.worker.yaml",
        "SOUL.worker.md",
        vars,
        false,
      );
    }

    // Challenger profile (read-only, different model from orchestrator/worker)
    const challengerName = `${config.hermes.profile_worker_prefix}-challenger`;
    await installProfile(
      hermesBin, hermesRoot,
      challengerName,
      "config.worker.yaml",
      "SOUL.worker.md",
      vars,
      false,
    );
    say(`challenger profile: ${challengerName} (read-only, blind evaluation)`);

    // Arbiter profile (binding decision, premium model)
    const arbiterName = `${config.hermes.profile_worker_prefix}-arbiter`;
    await installProfile(
      hermesBin, hermesRoot,
      arbiterName,
      "config.worker.yaml",
      "SOUL.worker.md",
      vars,
      false,
    );
    say(`arbiter profile: ${arbiterName} (binding decision, premium model)`);

    // ── Gate script ──
    mkdirSync(HERMES_SCRIPTS, { recursive: true });
    const gateContent = await subFile(
      join(TEMPLATES_DIR, "scripts", "tick-gate.sh"),
      vars,
    );
    Bun.write(join(HERMES_SCRIPTS, `${config.hermes.tick_name}-gate.sh`), gateContent);
    say(`gate script installed: ${HERMES_SCRIPTS}/${config.hermes.tick_name}-gate.sh`);

    // ── LiteLLM proxy config ──
    const litellmContent = await subFile(join(TEMPLATES_DIR, "litellm-config.yaml"), vars);
    Bun.write(join(HERMES_SCRIPTS, "litellm-config.yaml"), litellmContent);
    say(`LiteLLM proxy config: ${HERMES_SCRIPTS}/litellm-config.yaml`);
    say("  Each profile has a fallback chain ending in a local model (never-dies guarantee)");
    say("  Start proxy: litellm --config ~/.hermes/scripts/litellm-config.yaml");

    // ── Ledger ──
    const ledgerDir = join(repoDir, config.paths.ledger);
    mkdirSync(join(ledgerDir, "hypotheses"), { recursive: true });
    mkdirSync(join(ledgerDir, "runs"), { recursive: true });
    mkdirSync(join(ledgerDir, "reports"), { recursive: true });
    mkdirSync(join(ledgerDir, "ideas"), { recursive: true });
    if (!existsSync(join(ledgerDir, "events.jsonl"))) {
      Bun.write(join(ledgerDir, "events.jsonl"), "");
      say(`events log: ${ledgerDir}/events.jsonl`);
    }

    if (!existsSync(join(ledgerDir, "control.yaml"))) {
      const ctrl = await subFile(join(TEMPLATES_DIR, "control.yaml"), vars);
      Bun.write(join(ledgerDir, "control.yaml"), ctrl);
    }
    if (!existsSync(join(ledgerDir, "state.json"))) {
      const state = await subFile(join(TEMPLATES_DIR, "state.json"), vars);
      Bun.write(join(ledgerDir, "state.json"), state);
    }
    if (!existsSync(join(ledgerDir, "goal.yaml"))) {
      const goalContent = await subFile(join(TEMPLATES_DIR, "goal.yaml"), vars);
      Bun.write(join(ledgerDir, "goal.yaml"), goalContent);
      say(`goal config: ${ledgerDir}/goal.yaml`);
    }

    // Seed hypotheses from adapter
    if (args.adapter) {
      const hypFile = join(adapterDir, "hypotheses.seed.yaml");
      if (existsSync(hypFile) && !existsSync(join(ledgerDir, "hypotheses", "seed.yaml"))) {
        cpSync(hypFile, join(ledgerDir, "hypotheses", "seed.yaml"));
        say(`seed hypotheses: ${ledgerDir}/hypotheses/seed.yaml`);
      }
      const agentsFile = join(adapterDir, "AGENTS.adapter.md");
      const repoAgents = join(repoDir, "AGENTS.md");
      if (existsSync(agentsFile) && !existsSync(repoAgents)) {
        cpSync(agentsFile, repoAgents);
        say("AGENTS.md copied from adapter");
      }
    } else {
      const repoAgents = join(repoDir, "AGENTS.md");
      if (!existsSync(repoAgents)) {
        const agents = await subFile(join(TEMPLATES_DIR, "AGENTS.md"), vars);
        Bun.write(repoAgents, agents);
      }
    }
    say(`ledger ready: ${ledgerDir}`);

    // ── Hermes runtime ──
    // Gateway
    const cronStatus = Bun.spawnSync([hermesBin, "cron", "status"], { shell: true });
    if (cronStatus.exitCode === 0) {
      say("gateway already responding");
    } else {
      say("installing gateway service");
      const gw = Bun.spawnSync([hermesBin, "gateway", "install"], { shell: true });
      if (gw.exitCode !== 0) die("gateway install failed");
    }

    // Kanban board
    const boardList = Bun.spawnSync([hermesBin, "kanban", "boards", "list"], {
      shell: true,
    });
    if (boardList.stdout.toString().includes(config.project.board_name)) {
      say(`kanban board '${config.project.board_name}' exists`);
    } else {
      const bc = Bun.spawnSync(
        [
          hermesBin,
          "kanban",
          "boards",
          "create",
          config.project.board_name,
          "--name",
          config.project.name,
          "--description",
          config.project.board_desc,
          "--switch",
        ],
        { shell: true },
      );
      if (bc.exitCode === 0) {
        say(`kanban board '${config.project.board_name}' created and set current`);
      } else {
        warn(`kanban board create failed: ${bc.stderr.toString().trim()}`);
      }
    }

    // Cron tick
    const tickPrompt = await subFile(join(TEMPLATES_DIR, "prompts", "tick.md"), vars);
    const cronList = Bun.spawnSync([hermesBin, "cron", "list"], { shell: true });
    if (cronList.stdout.toString().includes(config.hermes.tick_name)) {
      say(`cron job '${config.hermes.tick_name}' exists — updating`);
      Bun.spawnSync(
        [
          hermesBin,
          "cron",
          "edit",
          config.hermes.tick_name,
          "--schedule",
          config.hermes.tick_schedule,
          "--prompt",
          tickPrompt,
        ],
        { shell: true },
      );
    } else {
      const cc = Bun.spawnSync(
        [
          hermesBin,
          "cron",
          "create",
          config.hermes.tick_schedule,
          tickPrompt,
          "--name",
          config.hermes.tick_name,
          "--workdir",
          repoDir,
          "--script",
          `${config.hermes.tick_name}-gate.sh`,
          "--deliver",
          config.hermes.delivery,
        ],
        { shell: true },
      );
      if (cc.exitCode === 0) {
        say(`cron job '${config.hermes.tick_name}' created (${config.hermes.tick_schedule})`);
      } else {
        die(`cron create failed: ${cc.stderr.toString().trim()}`);
      }
    }

    // ── Registry update ──
    const registryProfiles = [
      config.hermes.profile_orchestrator,
      ...Array.from({ length: config.hermes.worker_count }, (_, i) => `${config.hermes.profile_worker_prefix}-${i + 1}`),
    ];
    await updateRegistry(config, repoDir, args.adapter || "default", registryProfiles, false);

    // Verification
    say("--- verification ---");
    const vs = Bun.spawnSync([hermesBin, "cron", "status"], { shell: true });
    console.log(vs.stdout.toString());
    const vb = Bun.spawnSync([hermesBin, "kanban", "boards", "show"], { shell: true });
    console.log(vb.stdout.toString());
  }

  // ── Summary ──
  console.log("");
  say(`========== ${config.project.name} — Hermes Orchestrator Pack ==========`);
  say(`repo:       ${repoDir}`);
  say(`ledger:     ${config.paths.ledger}/`);
  say(`profiles:   ${config.hermes.profile_orchestrator}, ${config.hermes.profile_worker_prefix}-1..${config.hermes.worker_count}`);
  say(`tick:       ${config.hermes.tick_name} (${config.hermes.tick_schedule})`);
  say(`board:      ${config.project.board_name}`);

  if (args.dryRun) {
    console.log("");
    dry("Dry-run complete. No files were written.");
    dry("Run without --dry-run to execute the bootstrap.");
    console.log(`\nNext step after dry-run looks good:\n  bun bootstrap.ts "${repoDir}" --adapter ${args.adapter || "<name>"}`);
  } else {
    console.log(`
Next steps:
  1. Review ${join(repoDir, config.paths.ledger, "control.yaml")}  (mode is 'paused' by default)
  2. Fill AGENTS.md with real boundaries + runner commands
  3. Dry-run one tick:        hermes cron run ${config.hermes.tick_name}
  4. When ready, set          mode: running  in control.yaml
  5. Pause:                   hermes cron pause ${config.hermes.tick_name}
  6. Resume:                  hermes cron resume ${config.hermes.tick_name}`);
    say("done.");
  }
}

main().catch((err) => die(err instanceof Error ? err.message : String(err)));
