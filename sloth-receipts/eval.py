"""Compare what Gemma read (out/extractions.jsonl) and what the rules decided (out/report.csv)
against the ground truth of the fictional samples (samples/truth.json)."""
import csv, json, sys
from pathlib import Path
from sloth import cents, txid_key, norm

out = Path(sys.argv[1] if len(sys.argv) > 1 else "out")
truth = json.loads(Path("samples/truth.json").read_text(encoding="utf-8"))
ext = {json.loads(l)["file"]: json.loads(l) for l in (out / "extractions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
rep = {r["file"]: r for r in csv.DictReader(open(out / "report.csv", encoding="utf-8"))}
fields = {"amount": lambda t, x: cents(t["amount"]) == cents(x.get("amount_brl")),
          "date": lambda t, x: t["date"] == (x.get("date") or "").strip(),
          "payer": lambda t, x: norm(t["payer"]) == norm(x.get("payer_name")),
          "payee_key": lambda t, x: norm(t["payee_key"]) == norm(x.get("payee_pix_key")),
          "status": lambda t, x: norm(t["status"]) == norm(x.get("status")),
          "txid_exact": lambda t, x: txid_key(t["txid"]) == txid_key(x.get("transaction_id"))}
score = {k: 0 for k in fields}
verdict_ok = 0
rows = []
for f, t in truth.items():
    x = ext[f]["fields"]
    bad = [k for k, fn in fields.items() if not fn(t, x)]
    for k in fields:
        score[k] += k not in bad
    v = rep[f]["verdict"]
    verdict_ok += v == t["expected_verdict"]
    rows.append(f"{f}: verdict {v:<17} expected {t['expected_verdict']:<17} {'OK ' if v == t['expected_verdict'] else 'XX '} misread: {', '.join(bad) or '-'}")
    if "txid_exact" in bad:
        rows.append(f"      txid truth {t['txid']} read {x.get('transaction_id')}")
print("\n".join(rows))
n = len(truth)
print("\nField accuracy:", ", ".join(f"{k} {v}/{n}" for k, v in score.items()))
print(f"Verdicts correct: {verdict_ok}/{n}")
secs = [e["seconds"] for e in ext.values() if e.get("seconds")]
print(f"Seconds per receipt: mean {sum(secs)/len(secs):.1f}, max {max(secs):.1f}")
