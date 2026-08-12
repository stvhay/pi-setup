# PR Mechanics and Handoff

Use only after candidate, evidence, and body are stable.

## Remote approval packet

Before fork creation, force-push, upstream draft/PR creation, or any remote action outside exact initial-scope user-fork staging authorization, present:

- authenticated public account;
- upstream and user-fork URLs;
- base/head branches and exact commit IDs;
- diffstat and changed files;
- title and separate reviewer-facing body path/content;
- verification and unresolved failures;
- public visibility and likely notification consequences;
- actions excluded: reviewers, Ready state, merge, release, package publication, cleanup.

Use the available informed approval mechanism. Approval for one exact remote step does not authorize later history rewrites or upstream draft creation.

## Initially authorized fork staging

One exact initial implementation approval may cover a normal new or fast-forward feature-branch push after successful Bead closeout only when all conditions hold:

- approval binds the Bead, repository, canonical fork push URL, local/remote branches, approved base SHA, candidate-selection rule limited to the task-owned implementation commit plus portable closeout commit, expected remote ref state, final gates, exclusions, and stop policy;
- destination is the user's verified existing fork and is neither protected nor production;
- source is a clean, already reviewed task feature branch for an upstream PR candidate;
- task commit and successful final gate precede direct closeout, and portable Beads state is committed;
- the candidate-selection rule resolves to immutable push `HEAD`, the range after approved base contains only those two commits, and the intended remote branch is known;
- remote destination still matches the approved absent/SHA state;
- remote destination is absent or an ancestor of the reviewed head;
- push uses one explicit branch refspec, no force, no tags, and no unrelated commits;
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
git push <fork-remote> HEAD:refs/heads/<feature-branch>
git ls-remote --heads <fork-remote> refs/heads/<feature-branch>
```

The first push attempt consumes the authority. The final remote SHA must equal reviewed `HEAD`. Stop on ambiguous ownership, dirty scope, changed resolved push `HEAD`, failed gate/closeout, an unexpected remote ref, non-fast-forward rejection, uncertain post-state, or any need for history rewrite; do not retry or mutate remote state as rollback. Initial push authorization does not include fork creation, any PR creation/update, upstream-repository pushes or PRs, protected/production branches, reviewer requests, Ready state, merge, tag, release, deletion, or force-push.

## Fork-local staging draft

Check permissions and fork state; do not assume names:

```bash
gh repo view <upstream> --json defaultBranchRef,viewerPermission
gh repo view <user>/<repo> --json nameWithOwner,defaultBranchRef 2>/dev/null || true
git remote -v
git status --short
git log --oneline <base>..HEAD
```

Ensure the reviewed branch is present on the user's fork through the initially authorized push path above or separate approval. Use HTTPS or the user's configured remote; never expose credentials.

Creating the staging draft **in the fork** requires separate exact approval. Target the fork default branch, or the reviewed predecessor feature branch when staging a stacked sequence. The body file must contain only reviewer-facing PR prose—never the internal evidence/approval packet:

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

The staging draft is the user-agent review surface. The user may edit title/body and request code changes; later branch pushes and fork-local draft text updates require exact authority for those actions.

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
