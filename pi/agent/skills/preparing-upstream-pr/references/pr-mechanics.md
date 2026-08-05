# PR Mechanics and Handoff

Use only after candidate, evidence, and body are stable.

## Remote approval packet

Before fork creation, push, force-push, or draft creation, present:

- authenticated public account;
- upstream and user-fork URLs;
- base/head branches and exact commit IDs;
- diffstat and changed files;
- title and separate reviewer-facing body path/content;
- verification and unresolved failures;
- public visibility and likely notification consequences;
- actions excluded: reviewers, Ready state, merge, release, package publication, cleanup.

Use the available informed approval mechanism. Approval for one exact remote step does not authorize later history rewrites or upstream draft creation.

## Fork-local staging draft

Check permissions and fork state; do not assume names:

```bash
gh repo view <upstream> --json defaultBranchRef,viewerPermission
gh repo view <user>/<repo> --json nameWithOwner,defaultBranchRef 2>/dev/null || true
git remote -v
git status --short
git log --oneline <base>..HEAD
```

After approval, push the reviewed branch to the user's fork. Use HTTPS or the user's configured remote; never expose credentials.

Create staging draft **in the fork**. The body file must contain only reviewer-facing PR prose—never the internal evidence/approval packet:

```bash
gh pr create \
  --repo <user>/<repo> \
  --base <fork-default-branch> \
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

The staging draft is a review surface. Human may edit title/body and request code changes.

Before any agent copyedit:

```bash
gh pr view <staging-url> --json title,body,commits,files
```

Treat current GitHub text as source. Preserve intentional edits. Show material meaning changes before applying them.

PR edit history is visible to readers. Authors can delete revision content, but editor/timestamp history remains. Do not depend on cleanup; create a fresh upstream draft instead.

## Fresh upstream draft

After full human review, prepare a new body file from the current staging body. Do not copy staging comments or link internal/private artifacts.

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
