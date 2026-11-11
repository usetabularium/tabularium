---
name: private
description: Declare a private-mode care session early — one person whose identifier must never transit the AI API.
disable-model-invocation: true
---

# Private-mode session

The operator has opened a **private-mode session**: a care session about one person whose
`profile.md` → Identity marks an identifier ⟨never-API⟩ (ADR-0029). Same session kind as any care
session; stricter posture, loaded now, before any file arrives.

1. **Before any ingestion for this person, read `tools/private-mode/README.md`** — what may reach a
   model, the mandatory operator eyeball gate, the fail-closed rules — and, before running the
   masking tools, `tools/private-mode/topics/pipeline.md`. No page of theirs — image
   or extracted text — reaches a model until that gate is passed. Never inspect an unredacted page
   "just to check".
2. **Chat attachments are refused in this session.** The client reads a file sent into the chat at
   once when it can display it; nothing done afterwards un-sends it. If one arrives anyway: say what
   reached the AI service (what you were shown, or, for a file passed only as a path, its name and
   location), never open or copy it, file nothing from it, link the tray for the operator to move it
   there, record the occurrence in that person's change log and, on an install with a development
   side, relay it as abstract prose (the revisit trigger lives there). The person's `med/_inbox/` is the only intake path.
3. **Check the marker.** If this person's profile does not mark private mode, ask — the operator may
   be enabling the setting (their profile edit, declared in their own words), or the declaration was
   a slip. Never enable or assume it on your own inference.
4. **Kept details.** If their private-mode line carries the sign `⟨withheld:details-kept⟩`, details
   besides the number stay on the Mac: `identity.py status <handle>` names which. Write placeholders,
   never ask for those details in the chat, and take the age from the identity command when the date
   of birth is kept (`tools/private-mode/topics/kept-details.md`).

Pointer only — the protocol's home is `tools/private-mode/README.md` → *Opening a private-mode
session* (decision record: ADR-0029); `CLAUDE.md` → *Context* points there too. The copy under `.claude/skills/` is refreshed byte-identical from
`tools/claude-skills/private/SKILL.md` by `checks/install-instance.sh` (every instance); edit the
source, never the copy.
