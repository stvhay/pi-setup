import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { stripFrontmatter, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

const PACKAGE_SOURCE = "git:github.com/DietrichGebert/ponytail";
const SKILLS = new Set([
  "ponytail",
  "ponytail-review",
  "ponytail-audit",
  "ponytail-debt",
  "ponytail-gain",
  "ponytail-help",
]);

export default function ponytailSkillInput(pi: ExtensionAPI): void {
  pi.on("input", async (event) => {
    if (!event.text.startsWith("/skill:")) return { action: "continue" };

    const space = event.text.indexOf(" ");
    const name = space === -1 ? event.text.slice(7) : event.text.slice(7, space);
    if (!SKILLS.has(name)) return { action: "continue" };

    const packageRoot = pi.getCommands().find((command) =>
      command.source === "extension"
      && command.sourceInfo.origin === "package"
      && (command.sourceInfo.source === PACKAGE_SOURCE || command.sourceInfo.source.startsWith(`${PACKAGE_SOURCE}@`))
    )?.sourceInfo.baseDir;
    if (!packageRoot) return { action: "continue" };

    const skillDir = join(packageRoot, "skills", name);
    const skillPath = join(skillDir, "SKILL.md");
    const body = stripFrontmatter(await readFile(skillPath, "utf8")).trim();
    const block = `<skill name="${name}" location="${skillPath}">\nReferences are relative to ${skillDir}.\n\n${body}\n</skill>`;
    const args = space === -1 ? "" : event.text.slice(space + 1).trim();
    return { action: "transform", text: args ? `${block}\n\n${args}` : block };
  });
}
