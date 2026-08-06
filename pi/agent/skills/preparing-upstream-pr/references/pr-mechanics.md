# PR Mechanics and Handoff

Use only after candidate, evidence, and body are stable.

## Remote approval packet

Before fork creation, force-push, upstream draft/PR creation, or any remote action outside standing user-fork staging authorization, present:

- authenticated public account;
- upstream and user-fork URLs;
- base/head branches and exact commit IDs;
- diffstat and changed files;
- title and separate reviewer-facing body path/content;
- verification and unresolved failures;
- public visibility and likely notification consequences;
- actions excluded: reviewers, Ready state, merge, release, package publication, cleanup.

Use the available informed approval mechanism. Approval for one exact remote step does not authorize later history rewrites or upstream draft creation.

## Standing-authorized fork staging

A normal new or fast-forward feature-branch push plus fork-local draft creation and iterative updates need no per-action approval only when all conditions hold:

- destination is the user's verified existing fork;
- source is a clean, already reviewed task feature branch for an upstream PR candidate;
- exact local head and intended remote branch are known;
- remote destination is absent or an ancestor of the reviewed head;
- push uses no force and contains no unrelated commits;
- draft targets the fork default branch, or the reviewed predecessor feature branch for a stacked sequence;
- draft contains reviewer-facing prose only and adds no reviewers or maintainer/team mentions.

Verify before and after:

```bash
git status --short
git remote get-url --push <fork-remote>
git log --oneline <reviewed-base>..HEAD
remote_sha=$(git ls-remote --heads <fork-remote> refs/heads/<feature-branch> | awk '{print $1}')
if [ -n "$remote_sha" ]; then
  git fetch --no-tags <fork-remote> refs/heads/<feature-branch>
  git merge-base --is-ancestor "$remote_sha" HEAD
fi
git push -u <fork-remote> <feature-branch>
git ls-remote --heads <fork-remote> refs/heads/<feature-branch>
```

The final remote SHA must equal reviewed `HEAD`. Stop on ambiguous ownership, dirty scope, an unexpected remote ref, non-fast-forward rejection, or any need for history rewrite. Standing authorization includes creating and iteratively updating only the fork-local draft described below. It does not include fork creation, upstream-repository pushes or PRs, reviewer requests, Ready state, merge, release, deletion, or force-push.

## Fork-local staging draft

Check permissions and fork state; do not assume names:

```bash
gh repo view <upstream> --json defaultBranchRef,viewerPermission
gh repo view <user>/<repo> --json nameWithOwner,defaultBranchRef 2>/dev/null || true
git remote -v
git status --short
git log --oneline <base>..HEAD
```

Ensure the reviewed branch is present on the user's fork through the standing-authorized path above or separate approval. Use HTTPS or the user's configured remote; never expose credentials.

Without another approval, create the staging draft **in the fork**. Target the fork default branch, or the reviewed predecessor feature branch when staging a stacked sequence. The body file must contain only reviewer-facing PR prose—never the internal evidence/approval packet:

```bash
gh pr create \
  --repo <user>/<repo> \
  --base <fork-default-or-reviewed-predecessor-branch> \
  --head <feature-branch> \
  --draft \
  --title '<title>' \
  --body-file <body-file>
```

Verify:

```bash
gh pr view <url> --json url,state,isDraft,title,body,baseRefName,headRefName,commits,files,reviewRequests
```

Required state:

- open and draft;
- target is user's fork;
- no reviewer requests or maintainer/team mentions;
- exact reviewed commits/files;
- no private session links, secrets, local paths, or stale evidence.

Public forks and their draft PRs are public. The benefit is separation from upstream review/notification history, not privacy.

## Human revision

The staging draft is the user-agent review surface. The user may edit title/body and request code changes; normal branch pushes and fork-local draft updates remain standing-authorized during this iteration.

Before any agent copyedit:

```bash
gh pr view <staging-url> --json title,body,commits,files
```

Treat current GitHub text as source. Preserve intentional edits. Show material meaning changes before applying them.

PR edit history is visible to readers. Authors can delete revision content, but editor/timestamp history remains. Do not depend on cleanup; create a fresh upstream draft instead.

## Fresh upstream draft

Only after the user says the staging draft is ready and approves upstream draft creation, prepare a new body file from the current staging body. Do not copy staging comments or link internal/private artifacts.

Recheck upstream head, permissions, profile freshness, commits, and invalidated tests. If clean history requires force-push, request separate approval and use exact `--force-with-lease` protection.

Before creation, warn:

- upstream draft is public immediately;
- repository watchers may receive GitHub/email notifications according to their settings;
- CODEOWNERS are normally not automatically requested until Ready for review;
- edit and force-push history cannot be made as though it never happened.

After express authorization:

```bash
gh pr create \
  --repo <upstream-owner>/<repo> \
  --base <upstream-default-branch> \
  --head <user>:<feature-branch> \
  --draft \
  --title '<final-title>' \
  --body-file <final-body-file>
```

Verify open/draft state and exact refs/files/commits. Do not add reviewers or mentions.

## Human-only publication

Only the human marks the upstream draft Ready for review. Agent must not run `gh pr ready`, request reviewers, merge, or release.

If human asks for later revisions, use `receiving-code-review`; re-run affected checks and fetch current GitHub body before edits.

## GitHub behavior sources

- Draft stage and CODEOWNER request timing: <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/changing-the-stage-of-a-pull-request>
- CODEOWNERS and drafts: <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners>
- Edit-history visibility and revision deletion limits: <https://docs.github.com/en/communities/moderating-comments-and-conversations/tracking-changes-in-a-comment>
- Notification subscriptions and email settings: <https://docs.github.com/en/account-and-profile/managing-subscriptions-and-notifications-on-github/setting-up-notifications/about-notifications>
