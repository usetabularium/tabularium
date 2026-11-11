# How sure a green is

Read when: you say what a green run means, choose a trial count, or weigh whether a lapse could
have slipped through.

A trial is a sample. The table gives the chance that a lapse happening at a given rate is caught
by at least one of *n* trials:

| Lapse rate | ×1 (core EV-17a, EV-18a; six full-suite care twins) | ×2 (core) | ×3 (core EV-04, full) | ×5 (`--safety-trials 5`) | ×10 (targeted) |
|---|---|---|---|---|---|
| 1 in 2 | 50% | 75% | 88% | 97% | >99% |
| 1 in 5 | 20% | 36% | 49% | 67% | 89% |
| 1 in 10 | 10% | 19% | 27% | 41% | 65% |

The core catches **frequent** regressions well. The keystone regression EV-04b found ran at 4 in
10, and three trials catch that 78% of the time. It catches **rare** lapses poorly. That trade is
deliberate: a small run that actually happens beats a full one nobody can afford (ADR-0049
element 14).

The track record through September 2026: four genuine lapses in about 350 trials, all in EV-04 or in the
open-the-original check (EV-05b, which EV-02a now carries in the core). Every other failure was
the grader misreading a correct answer, fixed and re-judged without new sessions.

**What a green does not mean.** It holds for synthetic fixtures, at this trial count, for these
exact instruction bytes and this model. The eval runs headless, so it stands in for live
behaviour, with a known gap (the top-level `README.md` → *Limits*). A model that changes between runs goes unseen until the next
run. Tone is not judged, and no case covers build sessions. Rules outside the core are
checked only by a full run.
