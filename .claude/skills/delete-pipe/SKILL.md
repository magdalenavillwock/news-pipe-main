---
name: delete-pipe
description: This skill should be used when the user asks to "delete pipe", "pipe loeschen", "remove subscription", "abo entfernen", "subscription loeschen", "pipe entfernen", or wants to remove a notification pipeline completely.
---

# Delete Pipe

Remove a News Pipe subscription completely — config entry, workflow files, and optionally all output data.

## Overview

Safely delete a pipe by removing its config block from `config.yaml`, deleting its GitHub Actions workflow files, and optionally cleaning up generated output and data files. Always confirm with the user before destructive actions.

## Workflow

### Step 1: List Available Pipes

Read `config.yaml` and extract all entries under `subscriptions:`.

Present to the user with AskUserQuestion showing:

- Pipe ID
- Display name
- Number of sources
- Ntfy topic

### Step 2: Confirm Deletion

Use AskUserQuestion to confirm:

1. **Which pipe to delete?** (selection from the list)
2. **Delete output data too?** (`output/{pipe-id}/` and `data/{pipe-id}/`)

Show a warning: "This permanently removes the pipe. Ntfy subscribers will stop receiving updates."

### Step 3: Execute Deletion

#### Remove from config.yaml

Delete the entire `subscriptions.{pipe-id}` block from `config.yaml`. Preserve all other subscriptions and formatting.

#### Remove workflow files

```bash
git rm .github/workflows/{pipe-id}.yml
git rm .github/workflows/{pipe-id}-weekly.yml
```

Skip silently if a file does not exist (not every pipe has a weekly workflow).

#### Remove output data (if requested)

```bash
git rm -r output/{pipe-id}/
git rm -r data/{pipe-id}/
```

Skip silently if directories do not exist.

### Step 4: Commit and Report

Commit with message: `chore: remove {pipe-id} subscription`

Report to user:

- What was removed (config, workflows, data)
- Reminder: "The Ntfy topic `news-pipe-{pipe-id}` still exists on ntfy.sh but will no longer receive messages."
- If this was the last subscription, note that the system is now idle until a new pipe is created
