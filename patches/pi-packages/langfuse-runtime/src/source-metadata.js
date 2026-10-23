import { execFileSync } from "node:child_process";
function sourceStatus(status) {
  return {
    source_type: status,
    metadata_source: status
  };
}
function runGit(cwd, args, env) {
  try {
    return {
      status: "ok",
      value: execFileSync("git", args, {
        cwd,
        encoding: "utf8",
        env,
        stdio: ["ignore", "pipe", "ignore"],
        timeout: 2e3
      }).trim()
    };
  } catch (error) {
    const failure = error;
    return typeof failure.status === "number" ? { status: "failed" } : { status: "unavailable" };
  }
}
function collectSourceMetadata(cwd, enabled, env = process.env) {
  if (!enabled) {
    return sourceStatus("disabled");
  }
  const inside = runGit(cwd, ["rev-parse", "--is-inside-work-tree"], env);
  if (inside.status === "unavailable") {
    return sourceStatus("unavailable");
  }
  if (inside.status !== "ok" || inside.value !== "true") {
    return sourceStatus("non-git");
  }
  const revision = runGit(cwd, ["rev-parse", "--verify", "HEAD"], env);
  const ref = runGit(cwd, ["symbolic-ref", "--quiet", "--short", "HEAD"], env);
  const workingTree = runGit(cwd, ["status", "--porcelain=v1", "--untracked-files=normal"], env);
  if (revision.status !== "ok" || !/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/i.test(revision.value) || workingTree.status !== "ok" || ref.status === "unavailable") {
    return sourceStatus("unavailable");
  }
  return {
    source_type: "git-repo",
    "vcs.ref.head.revision": revision.value,
    git_detached: String(ref.status !== "ok"),
    git_dirty: String(Boolean(workingTree.value)),
    metadata_source: "git-detection"
  };
}
export {
  collectSourceMetadata
};
