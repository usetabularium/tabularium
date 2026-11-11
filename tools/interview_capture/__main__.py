#!/usr/bin/env python3
"""CLI: `python3 -m tools.interview_capture <list|file|verify|quotes> ...` (run from the repository root).

  list   [--session ID | --transcript PATH]       the session's on-screen question calls: number,
                                                  answer time, status and headers (no answers)
  file   <handle> [--session ID | --transcript PATH] [--call N ... | --all] [--since T]
         [--until T] [--slug S] [--confirmed]                 write the answered calls not yet filed for anyone
                                                  into med/sources/interviews/ and inventory it;
                                                  completes an interrupted earlier filing first
  verify <file> [--transcript PATH]               the file still holds what was captured
  quotes <handle>                                 quotations citing an interview file are word for word

The session defaults to this one (CLAUDE_CODE_SESSION_ID). Exit 0 = done / clean, 1 = a finding,
3 = refused with nothing written.
"""
import argparse
import os
import sys

from tools import interview_capture as ic


def _transcript(a):
    if a.transcript:
        if not os.path.isfile(a.transcript):
            raise ic.CaptureError("no such transcript file")
        return a.transcript
    return ic.find_transcript(a.session or os.environ.get("CLAUDE_CODE_SESSION_ID", ""))


def _cmd_list(a):
    calls = ic.read_calls(_transcript(a))
    if not calls:
        print("no on-screen question calls in this transcript")
    for c in calls:
        heads = ", ".join(ic._one_line(q.get("header", "")) for q in c["questions"])
        print("call %d  %s  %-24s %d question(s): %s"
              % (c["n"], c["answered_at"] or "-", c["status"], len(c["questions"]), heads))
    return 0


def _cmd_file(a):
    t = _transcript(a)
    r = ic.file_interview(a.root, a.handle, t, session_id=a.session, since=a.since, until=a.until,
                          numbers=a.call, slug=a.slug, confirmed=a.confirmed,
                          take_all=a.all)
    for rp in r["recovered"]:
        print("completed an interrupted filing: %s is now inventoried, unverified" % rp)
    if r["path"]:
        print("filed word for word: %s" % os.path.relpath(r["path"], a.root))
        for c in r["calls"]:
            print("  call %d (%s): %s" % (c["n"], c["answered_at"],
                                          ", ".join(ic._one_line(q.get("header", ""))
                                                    for q in c["questions"])))
    if r["swept_in"]:
        print("this person's first ledger was created; it also took in %d other source(s) already on "
              "disk, unverified, as the filing procedure's step 3 does" % r["swept_in"])
    for c in r["skipped"]:
        print("NOT filed: call %d — %s" % (c["n"], ic.STATUS_WHY[c["status"]]))
    names = [ic.dated_name(rp) for rp in r["recovered"]] + (
        [ic.dated_name(r["path"])] if r["path"] else [])
    print("Next: quote an answer only by copying it from the file, and cite it right after the "
          "quotation exactly as %s%s; then run `python3 -m tools.interview_capture quotes %s`."
          % (" or ".join("`%s`" % ic.citation(n) for n in names),
             " (the file it comes from)" if len(names) > 1 else "", a.handle))
    return 0


def _cmd_verify(a):
    problems, notes = ic.verify(a.file, a.transcript)
    for p in problems:
        print("FAIL  " + p)
    for n in notes:
        print("ok    " + n)
    if not problems:
        print("OK  the file holds the answers as captured")
    return 1 if problems else 0


def _cmd_quotes(a):
    failures, checked, skipped, unquoted = ic.check_quotes(a.root, a.handle)
    unread = [w for w, _, _, v in ic.quotations(a.root, a.handle) if v == "unread"]
    for f in failures:
        print("FAIL  " + f)
    for w in unread:
        print("NOT READ  %s: a quotation with no citation beside it — cite the interview file right "
              "after it, or, if it quotes no answer, leave it" % w)
    extra = []
    if skipped:
        extra.append("%d citing a sheet-era interview not checked" % skipped)
    if unquoted - len(unread):
        extra.append("%d citing paragraph(s) with no quotation of the file (a paraphrase is fine)"
                     % (unquoted - len(unread)))
    print("%d quotation(s) citing an on-screen interview checked, %d failed%s"
          % (checked, len(failures), "".join("; " + e for e in extra)))
    return 1 if failures else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m tools.interview_capture",
                                 description="Copy on-screen interview answers word for word")
    ap.add_argument("--root", default=os.getcwd(), help="repository root (default: cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def source(p):
        g = p.add_mutually_exclusive_group()
        g.add_argument("--session", help="session id (default: this session)")
        g.add_argument("--transcript", help="path to the session's .jsonl transcript")

    source(sub.add_parser("list"))
    f = sub.add_parser("file")
    f.add_argument("handle")
    source(f)
    f.add_argument("--call", type=int, action="append", help="call number from `list` (repeatable)")
    f.add_argument("--all", action="store_true",
                   help="every unfiled call, when the record holds more than one person and every "
                        "question in this session was about this one")
    f.add_argument("--since", help="only calls answered at or after this time (ISO; local if no zone)")
    f.add_argument("--until", help="only calls answered at or before this time")
    f.add_argument("--slug", default="on-screen", help="short name for the file (default on-screen)")
    f.add_argument("--confirmed", action="store_true",
                   help="the operator has attested whose answers these are (recorded on both ledger paths)")
    v = sub.add_parser("verify")
    v.add_argument("file")
    v.add_argument("--transcript")
    q = sub.add_parser("quotes")
    q.add_argument("handle")
    a = ap.parse_args(argv)
    try:
        return {"list": _cmd_list, "file": _cmd_file, "verify": _cmd_verify,
                "quotes": _cmd_quotes}[a.cmd](a)
    except (ic.LedgerKept, ic.LedgerInterrupted) as e:
        print("PARTLY DONE: %s" % e)
        return 3
    except ic.LedgerRefused as e:
        print("REFUSED (nothing written; the new file was removed again): %s" % e)
        print("Next: inventory any other file named above by the filing procedure, then run `file` "
              "again.")
        return 3
    except ic.CaptureError as e:
        print("REFUSED (nothing written): %s" % e)
        return 3
    except Exception as e:  # the ownership tool's stop, or a filesystem error
        print("REFUSED (nothing written): %s: %s" % (type(e).__name__, e))
        return 3


if __name__ == "__main__":
    sys.exit(main())
