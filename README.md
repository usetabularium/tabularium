# Tabularium

![tabularium. — records in caring order](.github/readme-banner.svg)

**Care for someone over time without holding it all in your head, and without losing track of
what is actually known.**

## Purpose

Tabularium turns scattered documents, conversations, medication information and open questions into
one current account per person: what is happening, what supports it, what remains uncertain, and
what needs attention next. The aim is that the caregiver has less to carry, the people involved share
a clearer picture, and important follow-up is less likely to be lost. Record integrity, privacy and
AI safeguards serve those outcomes; the checks below do not show that they have been achieved.

> **Intended purpose & limits.** Tabularium is a **personal record-keeping and care-coordination
> methodology for patients and informal caregivers** — and for the **clinicians and pharmacists**
> who advise them. It is built for anyone who wants to use agentic AI on health records **more
> safely and reliably than in a default chat**, with the AI's known limitations actively managed,
> not removed. It is **not a medical device** and is **not intended for diagnosis or treatment
> decisions** — clinical decisions belong to qualified clinicians. Outputs may contain errors and
> **must be verified against source documents**. See [NOTICE.md](NOTICE.md).

## Getting started

**You need** a Mac (the only supported system), the Claude desktop app (claude.com/download), signed
in, and a paid plan (Pro, Max, Ultra, Team or Enterprise) for its Code tab, where Tabularium runs. It
uses Claude Opus 5.5, the model its behavioural tests last passed on and the Code tab's default on
those plans.

**Set it up**
1. In the app, open the **Code** tab and click **+ New**.
2. Choose **Open folder…**, press Cmd-Shift-H for your home folder, and open it. The only change
   there is one new folder, Tabularium, kept out of iCloud's Desktop & Documents sync.
3. Under the message box, check that **Worktree** is off. Keep it off in every Tabularium session:
   records change only with it off.
4. Paste and send this prompt:

   ```text
   Set up Tabularium for me. First check that Apple's command line tools are installed (`xcode-select -p`; git alone would only open Apple's installer) and help me install them if not; then clone https://github.com/usetabularium/tabularium.git into ~/Tabularium (if that folder already exists, stop and ask me) and follow SETUP.md in it.
   ```

Claude checks your Mac, says what is missing and why, and installs it after one yes. A step that
needs your password or an Apple dialog stops for you in the app's **Terminal** panel (in the
session's title bar). Then it helps you add your first person.

**Later visits:** click **+ New**, choose **Open folder…**, open the Tabularium folder in your home
folder with **Worktree** off, and say what you need.

**Updates:** Tabularium reports when a newer minor or major release is out. Type `/update` to
adopt it (patch releases too). Nothing updates by itself.

## What it is

An **agent harness for medical records**, your own or those of people in your care, running on
Claude Code. This repository is the de-identified skeleton; real records stay on your Mac and never
enter version control.

A bare LLM chat can summarise a health situation once. Over months, facts go stale, a study's median
becomes the patient's value, one person's data drifts into another's record, citations get
mis-attributed. Each happened while this was built; each now has a written rule and, for most, a
check. Tabularium does not ask to be trusted: every claim stays one pointer from its source, so
checking stays easy.

Visit [usetabularium.com](https://usetabularium.com) for more information.

## What it gives you

- **Three layers**: unchanged originals, one current profile per person, handouts made from it.
- **A source on every fact**, graded A (original document) to D (unsourced); anything unverified gets
  a dated "confirm by". What you report is never silently overridden.
- **One person per session**, with checks for another person's handle in a record or a source in the
  wrong folder. Who a page belongs to stays your call.
- **Two handouts**: plain for the patient, cited for the clinician, in the person's language,
  fact-checked and sealed when delivered.
- **A reference library** with a two-step citation bar. It ships empty.
- **Executable checks** (`checks/`), each self-tested against a real defect, plus snapshots.
- **A firewall** keeping records, roster and references out of version control and the published
  copy.
- **A behavioural eval** (`evals/`) for the care rules no check can hold, so a model change shows up
  in a rerun, not in a handout. [What it shows and does not](evals/README.md#what-the-evidence-shows-and-does-not).
- **Private mode (experimental, opt-in)**: masks a person's national ID number on your Mac and holds
  each page for your review before any AI pass. Only Polish and US numbers are supported; any other
  you cover by hand. It can miss one, so your review is the last line.
  [Setup and limits](tools/private-mode/README.md).

## Known limitations

- The checks miss a dose line rewritten in place: read the medication list after each session.
- A file can lose text and still pass the checks; snapshots let you go back.
- A handout's seal catches accidental changes, not tampering.
- A backup in a cloud folder whose files are kept online only can't be checked; the backup tool then
  reports it as not verified.
- If a medicine's approved product information (its summary of product characteristics or patient
  leaflet) can't be opened, the handout says so, and what it says about that medicine (dose limits,
  interactions, warnings) rests on the author's own check.
- Cited papers aren't rechecked on a schedule.

## Layout

```
patients/<handle>/   profile.md · medications.md · med/{sources,analysis,handouts} · nmed/
_shared/             joint matters
reference-library/   your vetted clinical sources — the bar ships, the entries are yours
checks/              executable checks, recovery and Mac setup
tools/               private mode, ownership ledger, handout sealing, interview capture, skills
evals/               behavioural cases and their runner
adr/                 decision records
_templates/          person, profile, medications and handout scaffolds
CLAUDE.md            the care contract — the assistant reads it on its own
SETUP.md             the first run on a new Mac
CONTRIBUTING.md      the building contract
```

## Contributing

Outside code or text is not taken. If that changes, each contribution will need a sign-off line and
fall under the Apache License (section 5). To change the tool on your own copy:
`bash checks/install-instance.sh dev`, then [CONTRIBUTING.md](CONTRIBUTING.md).

## How this is offered

Free of charge, without warranty (see [LICENSE](LICENSE)), built and maintained by one person. It
does not replace an emergency call or a clinician, and no clinician or regulator has reviewed it. No
paid help is offered under its name.

The project receives none of your records, but your sessions send what they read to your AI service:
check your plan's data settings. Once a day Tabularium asks GitHub, where you cloned it from, which
releases exist. Like any web request, this shows GitHub your internet address; nothing from your
records is sent. To turn it off:
`mkdir -p ~/.config/tabularium && touch ~/.config/tabularium/release-notice-off`.

In a professional role, the data-protection duties for these records, including any agreement your
organisation needs with the AI provider, stay with you. Tabularium is independent, not affiliated
with or endorsed by Anthropic.

## Contact

Questions, corrections or clinical objections: write through the
[contact form](https://usetabularium.com/contact/). Feedback on the method counts as much as on the
code. By sending it you agree it may be used without obligation.

## License

Apache License 2.0: see [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md). It does not cover the name
"Tabularium" ([TRADEMARKS.md](TRADEMARKS.md)), the bundled handout fonts (SIL Open Font License 1.1,
beside the fonts in `_templates/handout-assets/fonts/`), or your records, in which Tabularium claims
no rights.
