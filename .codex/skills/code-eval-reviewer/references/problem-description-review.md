# Problem Description Review

Use this file when reviewing `Problem-Description.txt`.

## What good looks like
- Sound like a developer asking for a change in the repo.
- Stay concise and only mention behavior the solver actually needs.
- Describe user-visible behavior, constraints, and edge cases in plain English.
- Leave discoverable repo details in the repo unless they are necessary to remove ambiguity.

## Failures to flag
- Repo-external framing such as "`repo` currently supports X but lacks Y".
- Bullet-list or checklist style requests that read like instructions instead of a natural prompt.
- Rigid sections or headings such as `Requirements`, `Test assumptions`, `Acceptance criteria`, `Implementation notes`, or similar.
- Implementation prescription: exact class names, exact files, exact schema layout, exact helper names, or “implement using ...” unless required.
- Inline code fragments where plain English is enough.
- AI-slop wording, filler, or repetitive “make it robust / comprehensive / seamless” phrasing.
- Discoverable implementation details that were copied into the prompt without needing to be there.

## Reviewer questions
- If I removed the repo name, would this still read like a normal engineer request?
- Does the prompt tell the solver what behavior matters without telling them how to wire it internally?
- Is every explicit requirement reflected in plain English rather than code fragments?
- If I cut 20 percent of the words, would any required behavior be lost? If not, it is too long.
