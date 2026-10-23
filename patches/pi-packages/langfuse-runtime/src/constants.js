import { homedir } from "node:os";
import { resolve } from "node:path";
const selectedAgentDir = process.env.PI_CODING_AGENT_DIR;
const agentDir = selectedAgentDir === "~" ? homedir() : selectedAgentDir?.startsWith("~/") ? resolve(homedir(), selectedAgentDir.slice(2)) : selectedAgentDir || resolve(homedir(), ".pi", "agent");
const CONFIG_DIR = resolve(agentDir, "pi-langfuse");
const CONFIG_PATH = resolve(CONFIG_DIR, "config.json");
const DEFAULT_LANGFUSE_HOST = "https://cloud.langfuse.com";
const MAX_STRING_LENGTH = 12e3;
const MAX_TOOL_PAYLOAD_LENGTH = 24e3;
const MAX_DEPTH = 6;
const MAX_ARRAY_ITEMS = 50;
const MAX_OBJECT_KEYS = 80;
const MAX_PAYLOAD_NODES = 2e3;
export {
  CONFIG_DIR,
  CONFIG_PATH,
  DEFAULT_LANGFUSE_HOST,
  MAX_ARRAY_ITEMS,
  MAX_DEPTH,
  MAX_OBJECT_KEYS,
  MAX_PAYLOAD_NODES,
  MAX_STRING_LENGTH,
  MAX_TOOL_PAYLOAD_LENGTH
};
