# Training modules

Participant-facing lab workbooks for the Barangay Malinaw BIMS CTF. These are
**different from `facilitator/SOLUTIONS.md`** — that file is your private answer key;
these are written for the trainees.

| File | For | Use in |
|------|-----|--------|
| `01-RED-TEAM.md` | Attackers | Round 1 (attack), Round 3 (finale) |
| `02-BLUE-TEAM.md` | Defenders | Round 2 (patch & defend), Round 3 (finale) |
| `03-BURP-SUITE.md` | Everyone | Morning hands-on — intercept/tamper the BIMS with Burp before the CTF |

`03-BURP-SUITE.md` teaches Burp Suite (Proxy → Repeater → Intruder) against the BIMS,
fully offline. Its appendix maps PortSwigger Web Security Academy apprentice labs to the
four bugs for extra practice if the venue has internet. The brute-force task uses the
wordlist in `burp/passwords.txt`.

## How to hand them out

- **Round 1 (attack only):** give everyone the **Red** guide. Blue watches and reads
  along.
- **Round 2 (patch & defend):** give the **Blue** guide. The Blue guide intentionally
  contains the patches — it's a defender's workbook, so distribute it when defending
  begins, not before.
- **Round 3 (finale):** both guides are in play.

Both guides use progressive `<details>` spoilers: participants try first, then expand the
hint, then the full walkthrough. They render as click-to-expand in Markdown viewers
(VS Code, GitHub, most Markdown apps) and simply print in full on paper.

## Printing / converting

To hand these out as PDF, convert from the Pi or your Mac (needs `pandoc`):

```bash
pandoc modules/01-RED-TEAM.md  -o Red-Team-Guide.pdf
pandoc modules/02-BLUE-TEAM.md -o Blue-Team-Guide.pdf
```

The `<range-ip>` placeholder appears throughout — tell participants the live address, or
find-and-replace it before printing.
