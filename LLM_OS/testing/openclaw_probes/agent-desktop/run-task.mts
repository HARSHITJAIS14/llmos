/**
 * Single-file agentic run: a real LLM brain driving the agent-desktop provider.
 *
 * No Gateway, no node pairing, no registry. Just: model -> tool_use -> provider.act()
 * -> result -> model. Reuses the exact provider from index.ts, so everything proven
 * here ports to the openclaw harness later.
 *
 * Because we own the schema here (openclaw's contract sets additionalProperties:false
 * and has no `app` field), type/key can scope keystrokes to an app — which is what
 * stops keystrokes leaking into whatever happens to be frontmost.
 *
 * Run: ANTHROPIC_API_KEY=... node --import tsx extensions/agent-desktop/run-task.mts "<goal>"
 */
import entry from "./index.ts";
import { readFileSync } from "node:fs";

// The operator's accumulated, hard-won knowledge. This is the brain's context —
// app archetypes, per-app quirks, safety rules, what has already been learned the
// hard way. Without it the model rediscovers documented failures at real cost.
const KNOWLEDGE_FILES = [
  "/Users/harshit/Desktop/YC/LLM_OS/.agents/AGENTS.md",
  "/Users/harshit/Desktop/YC/LLM_OS/ATree_tool/learnings/learnings.md",
];
const KNOWLEDGE = KNOWLEDGE_FILES.map((f) => {
  try {
    return `\n\n===== ${f.split("/").slice(-1)[0]} =====\n${readFileSync(f, "utf8")}`;
  } catch {
    return "";
  }
}).join("");

const MODEL = process.env.CLAW_MODEL ?? "claude-sonnet-5";
const MAX_TURNS = Number(process.env.CLAW_MAX_TURNS ?? 20);
const GOAL =
  process.argv.slice(2).join(" ") ||
  "Open the 'cursor for che' page in Notion and type: it's done bro";

const API_KEY = process.env.ANTHROPIC_API_KEY;
if (!API_KEY) {
  console.error("ANTHROPIC_API_KEY is required");
  process.exit(1);
}

// ---- wire up the provider (same stub trick as smoke.mts) --------------------
const handlers = new Map<string, (p: string | null) => Promise<string>>();
entry.register({
  registerNodeHostCommand(spec: any) {
    handlers.set(spec.command, async (p) => await spec.handle(p, undefined, {}));
  },
  registerNodeInvokePolicy() {},
  logger: { error: console.error, warn: console.warn, info: () => {} },
  pluginConfig: {},
} as any);

const EXEC_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301";
async function act(input: Record<string, unknown>) {
  const raw = await handlers.get("computer.act")!(JSON.stringify({ executionId: EXEC_ID, ...input }));
  return JSON.parse(raw);
}

// ---- one tool, action enum: fewer schema tokens than 12 separate tools ------
const TOOL = {
  name: "computer",
  description:
    "Control this macOS desktop through the accessibility tree. Observe with get_window_state " +
    "to get elementRefs, then act on them. No screenshots exist; perception is text-only. " +
    "Always pass `app` when typing or pressing keys so input goes to the right application.",
  input_schema: {
    type: "object",
    properties: {
      action: {
        type: "string",
        enum: [
          "list_windows", "list_apps", "launch_app", "bring_to_front",
          "get_window_state", "left_click", "right_click", "double_click",
          "type", "key", "set_value",
        ],
      },
      method: {
        type: "string",
        enum: ["semantic", "physical"],
        description:
          "Click dispatch for left_click/right_click/double_click. 'semantic' = AXPress " +
          "(background, no focus steal). 'physical' = real cursor click at the element's " +
          "bounds via stealth_click. Consult your knowledge base for which apps need which.",
      },
      app: { type: "string", description: "App name. Required for type/key/launch_app." },
      windowRef: { type: "string", description: "Window id from list_windows; scopes observation." },
      elementRef: { type: "string", description: "Element ref from a get_window_state observation." },
      text: { type: "string", description: "Text for `type`." },
      keys: { type: "string", description: "Combo for `key`, e.g. cmd+p, return, escape." },
      value: { type: "string", description: "Value for `set_value`." },
      depth: { type: "integer", description: "AX depth for get_window_state (default 20)." },
    },
    required: ["action"],
  },
};

const SYSTEM =
  "You are LLM_OS, an autonomous macOS desktop agent. You perceive only through the " +
  "accessibility tree — there are no screenshots.\n\n" +
  "Below is your operator's accumulated knowledge base: app archetypes, per-app quirks, " +
  "interaction strategies, and safety rules learned from prior runs. TREAT IT AS " +
  "AUTHORITATIVE. It already records which techniques fail in which applications — do not " +
  "rediscover them. In particular, check it before choosing how to click or type in a given " +
  "app.\n\n" +
  "Operating principles:\n" +
  "- Observe, reason about candidates, act, then verify the state actually changed.\n" +
  "- elementRefs come from get_window_state and go stale after the tree changes.\n" +
  "- effect:\"confirmed\" only means the tree changed; effect:\"unverifiable\" means the tree " +
  "looks identical, which is normal for caret/focus moves and is NOT failure. Neither proves " +
  "your goal succeeded — re-observe to judge that.\n" +
  "- On ok:false, read the hint and adapt. Never blindly repeat an action.\n" +
  "- If a target is ambiguous, stop and say so rather than guessing.\n" +
  "- When the goal is genuinely done, reply in plain text with no tool call.\n" +
  KNOWLEDGE;

// ---- ReAct loop -------------------------------------------------------------
const messages: any[] = [{ role: "user", content: GOAL }];
let turns = 0, inTok = 0, outTok = 0;
const t0 = Date.now();

console.log(`\nGOAL: ${GOAL}\nMODEL: ${MODEL}\n${"=".repeat(70)}`);

while (turns < MAX_TURNS) {
  turns++;
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": API_KEY,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({ model: MODEL, max_tokens: 2048, system: SYSTEM, messages, tools: [TOOL] }),
  });
  if (!res.ok) {
    console.error(`API ${res.status}: ${(await res.text()).slice(0, 400)}`);
    process.exit(1);
  }
  const data: any = await res.json();
  inTok += data.usage?.input_tokens ?? 0;
  outTok += data.usage?.output_tokens ?? 0;

  for (const b of data.content ?? []) {
    if (b.type === "text" && b.text.trim()) console.log(`\n[${turns}] 💭 ${b.text.trim()}`);
  }

  const calls = (data.content ?? []).filter((b: any) => b.type === "tool_use");
  if (!calls.length) break;

  messages.push({ role: "assistant", content: data.content });
  const results: any[] = [];
  for (const c of calls) {
    const started = Date.now();
    let out: any;
    try {
      out = await act(c.input);
    } catch (e: any) {
      out = { ok: false, details: { code: "PROVIDER_THREW", hint: e.message } };
    }
    const ms = Date.now() - started;
    const n = out?.observation?.elements?.length;
    console.log(
      `[${turns}] ⚡ ${c.input.action}(${JSON.stringify(c.input).slice(0, 90)})` +
        `\n     ${ms} ms ok=${out.ok} effect=${out.effect ?? "-"}${n !== undefined ? ` elements=${n}` : ""}`,
    );
    results.push({
      type: "tool_result",
      tool_use_id: c.id,
      content: JSON.stringify(out).slice(0, 30000),
      is_error: out?.ok === false,
    });
  }
  messages.push({ role: "user", content: results });
}

const secs = ((Date.now() - t0) / 1000).toFixed(1);
console.log(
  `\n${"=".repeat(70)}\nturns=${turns}  wall=${secs}s  tokens in=${inTok} out=${outTok}` +
    `\n(verify the result yourself — nothing here inspects the screen)`,
);
