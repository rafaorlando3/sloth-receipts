#!/usr/bin/env python3
"""sloth-receipts: check Pix payment screenshots against your orders, overnight, on your own laptop.

Gemma reads each screenshot (locally, through Ollama). Plain Python rules decide.
PAID is an advisory screenshot-rule match, never a bank settlement confirmation;
everything else lands in a short "needs you" list for the morning.

Usage:
  python sloth.py --inbox samples/inbox --orders samples/orders.csv \
      --store-name "Loja Preguiça Feliz" --store-key pix@preguicafeliz.example --out out
"""
import argparse, base64, csv, html, json, re, sys, time, unicodedata, urllib.request
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

PROMPT = (
    "Read this Brazilian Pix payment screenshot. Copy each field exactly as printed. "
    "is_pix_receipt = true only if this is a Pix transfer receipt or Pix confirmation screen. "
    "status = the word shown for the transfer status (e.g. Concluído, Agendado, Em processamento); "
    "if no explicit transfer status is shown, use an empty string; do not infer completion. "
    "amount_brl as printed, like 'R$ 149,90'. date as dd/mm/yyyy. time as HH:MM. "
    "transaction_id = the full 'ID da transação' / end-to-end id, character by character. "
    "If a field is missing use an empty string."
)
SCHEMA = {
    "type": "object",
    "properties": {k: {"type": "string"} for k in (
        "status", "amount_brl", "date", "time", "payer_name", "payee_name", "payee_pix_key", "transaction_id")},
    "required": ["is_pix_receipt", "status", "amount_brl", "date", "time", "payer_name",
                 "payee_name", "payee_pix_key", "transaction_id"],
}
SCHEMA["properties"]["is_pix_receipt"] = {"type": "boolean"}

NEEDS_YOU = {
    "AMOUNT_MISMATCH": "Paid a different amount than the order",
    "DUPLICATE": "Same transaction id as an earlier receipt (reused screenshot?)",
    "WRONG_PAYEE": "Extracted Pix key does not exactly match the configured key",
    "STALE_DATE": "Receipt is older than the order",
    "NOT_COMPLETED": "Status is not an explicitly supported completed status",
    "NO_ORDER": "No open order matches this receipt",
    "AMBIGUOUS_ORDER": "No unique exact payer-and-amount link; orders remain open",
    "NOT_A_RECEIPT": "This image is not a Pix receipt",
    "PAID_OTHER_PAYER": "Amount matches, but payer text differs; order remains open",
    "UNREADABLE": "Gemma could not read the key fields",
}


# ---------- helpers ----------
def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9@.]+", " ", s).strip()


def sim(a, b):
    a, b = norm(a), norm(b)
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def cents(txt):
    if not isinstance(txt, str):
        return None
    m = re.search(r"(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})", txt or "")
    if not m:
        return None
    return int(m.group(1).replace(".", "")) * 100 + int(m.group(2))


def brl(c):
    return "R$ " + f"{c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_date(txt):
    if not isinstance(txt, str):
        return None
    try:
        return datetime.strptime((txt or "").strip()[:10], "%d/%m/%Y")
    except ValueError:
        return None


def txid_key(t):
    return re.sub(r"[^A-Z0-9]", "", (t or "").upper())


def same_txid(a, b):
    """E2E ids are 32 chars; Gemma sometimes slips one character on blurry images,
    so a normalized similarity ratio >= 0.94 blocks a possible duplicate; it cannot approve payment."""
    a, b = txid_key(a), txid_key(b)
    if len(a) < 20 or len(b) < 20:
        return False
    if a == b:
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.94



# This is an intentionally narrow accepted screenshot status, not bank verification.
COMPLETED_STATUSES = frozenset({"Concluído"})
E2E_PATTERN = re.compile(r"E[0-9]{8}[0-9]{12}[A-Za-z0-9]{11}")

def valid_txid(value):
    """Accept only the supported E2E shape and a real YYYYMMDDHHMM timestamp.
    Do not repair OCR, strip whitespace, or authenticate the transaction.
    """
    if not isinstance(value, str) or E2E_PATTERN.fullmatch(value) is None:
        return False
    try:
        datetime.strptime(value[9:21], "%Y%m%d%H%M")
    except ValueError:
        return False
    return True

def payer_key(value):
    """Exact name comparison after case/accent/whitespace normalization only."""
    if not isinstance(value, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_accents.casefold().split())

# ---------- extraction (the only part that uses the model) ----------
def extract(image_path, model, host):
    body = {
        "model": model, "stream": False, "think": False, "format": SCHEMA,
        "options": {"temperature": 0},
        "messages": [{"role": "user", "content": PROMPT,
                      "images": [base64.b64encode(image_path.read_bytes()).decode()]}],
    }
    req = urllib.request.Request(f"{host}/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        resp = json.load(r)
    fields = json.loads(resp["message"]["content"])
    return fields, round(time.time() - t0, 1)


def load_cache(path):
    done = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["file"]] = rec
    return done


# ---------- rules ----------
def decide(receipts, orders, store_name, store_key, tolerance_days=1):
    open_orders = {o["order_id"]: o for o in orders}
    seen = []  # (file, txid); approximate duplicates can only block a match
    results = []
    for rec in receipts:
        x = rec.get("fields")
        x = x if isinstance(x, dict) else {}
        r = dict(file=rec["file"], seconds=rec.get("seconds"), fields=x, order=None, verdict=None, note="")
        amount = cents(x.get("amount_brl"))
        rdate = parse_date(x.get("date"))
        status = x.get("status")
        if rec.get("error"):
            r.update(verdict="UNREADABLE", note=rec["error"])
        elif type(x.get("is_pix_receipt")) is not bool:
            r.update(verdict="UNREADABLE", note="is_pix_receipt must be a JSON boolean")
        elif x["is_pix_receipt"] is False:
            r["verdict"] = "NOT_A_RECEIPT"
        elif amount is None or rdate is None:
            r.update(verdict="UNREADABLE", note="amount or date missing")
        elif not isinstance(status, str) or status not in COMPLETED_STATUSES:
            r.update(verdict="NOT_COMPLETED", note=f"unsupported or incomplete status: {status}")
        elif not valid_txid(x.get("transaction_id")):
            r.update(verdict="UNREADABLE", note="missing or malformed supported E2E transaction id")
        elif (not isinstance(store_key, str) or not store_key.strip()
              or not isinstance(x.get("payee_pix_key"), str)
              or x["payee_pix_key"] != store_key):
            r.update(verdict="WRONG_PAYEE", note="extracted Pix key does not exactly match configured key")
        else:
            dup = next((f for f, t in seen if same_txid(t, x["transaction_id"])), None)
            if dup:
                r.update(verdict="DUPLICATE", note=f"same or approximate transaction id as {dup}; review required")
        if r["verdict"] is None:
            cands = [o for o in open_orders.values() if o["cents"] == amount]
            payer = payer_key(x.get("payer_name"))
            exact = [o for o in cands if payer and payer_key(o["customer"]) == payer]
            if len(exact) > 1 or (not exact and len(cands) > 1):
                r.update(verdict="AMBIGUOUS_ORDER", note="no unique exact payer-and-amount link; orders preserved")
            elif cands:
                o = exact[0] if exact else cands[0]
                r["order"] = o["order_id"]
                if rdate < o["created_dt"] - timedelta(days=tolerance_days):
                    r.update(verdict="STALE_DATE", note=f"receipt {x.get('date')}, order {o['created']}")
                elif not exact:
                    r.update(verdict="PAID_OTHER_PAYER",
                             note="payer text does not exactly match this customer; order preserved")
                else:
                    r["verdict"] = "PAID"
                    open_orders.pop(o["order_id"])
            else:
                by_name = [o for o in open_orders.values()
                           if payer and payer_key(o["customer"]) == payer]
                if len(by_name) > 1:
                    r.update(verdict="AMBIGUOUS_ORDER", note="multiple orders for exact payer; orders preserved")
                elif by_name:
                    o = by_name[0]
                    diff = amount - o["cents"]
                    r.update(order=o["order_id"], verdict="AMOUNT_MISMATCH",
                             note=f"receipt {brl(amount)}, order is {brl(o['cents'])} "
                                  f"({'short' if diff < 0 else 'over'} {brl(abs(diff))})")
                else:
                    r["verdict"] = "NO_ORDER"
        if valid_txid(x.get("transaction_id")) and r["verdict"] not in ("NOT_A_RECEIPT", "UNREADABLE"):
            seen.append((rec["file"], x["transaction_id"]))
        results.append(r)
    return results, list(open_orders.values())


# ---------- report ----------
def write_report(out, results, unpaid, total_seconds, model):
    paid = [r for r in results if r["verdict"] == "PAID"]
    needs = [r for r in results if r["verdict"] != "PAID"]
    with open(out / "report.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "verdict", "order", "amount", "payer", "date", "transaction_id", "note"])
        for r in results:
            x = r["fields"]
            w.writerow([r["file"], r["verdict"], r["order"] or "", x.get("amount_brl", ""), x.get("payer_name", ""),
                        x.get("date", ""), x.get("transaction_id", ""), r["note"]])
    mins = total_seconds / 60
    summary = (f"Reviewed {len(results)} extracted receipts. {len(paid)} meet PAID screenshot rules (advisory). "
               f"{len(needs)} need review. {len(unpaid)} orders remain open. "
               f"Recorded extraction time: {mins:.1f} min; this is not a new OCR benchmark.")
    rows = []
    for r in needs:
        x = r["fields"]
        rows.append(
            f"<tr><td><img src='../{html.escape(r['img'])}' loading='lazy'></td><td><b>{r['verdict']}</b>"
            f"<br><span class='why'>{html.escape(NEEDS_YOU.get(r['verdict'], ''))}</span></td>"
            f"<td>{html.escape(r['order'] or '-')}</td><td>{html.escape(x.get('amount_brl', ''))}</td>"
            f"<td>{html.escape(x.get('payer_name', ''))}</td><td>{html.escape(r['note'])}</td></tr>")
    ok = "".join(f"<li>{html.escape(r['order'])}: {html.escape(r['fields'].get('amount_brl', ''))} from "
                 f"{html.escape(r['fields'].get('payer_name', ''))}</li>" for r in paid)
    left = "".join(f"<li>{html.escape(o['order_id'])} {html.escape(o['customer'])} {brl(o['cents'])}</li>"
                   for o in unpaid)
    page = f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>sloth-receipts morning report</title>
<style>body{{font:16px system-ui;margin:24px;max-width:1000px;color:#222}} h1{{font-size:22px}}
.sum{{background:#eef6f0;padding:14px 16px;border-radius:10px}} table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}} img{{width:90px;border-radius:6px}}
.why{{color:#666;font-size:13px}} small{{color:#777}}</style>
<h1>🦥 sloth-receipts: morning report</h1><p class="sum">{html.escape(summary)}</p>
<h2>Needs you ({len(needs)})</h2><table><tr><th></th><th>Verdict</th><th>Order</th><th>Amount</th><th>Payer</th><th>Detail</th></tr>
{''.join(rows)}</table>
<h2>PAID screenshot-rule matches, not settlement ({len(paid)})</h2><ul>{ok}</ul>
<h2>Orders still open in this batch ({len(unpaid)})</h2><ul>{left}</ul>
<p><small>Extraction model label: {html.escape(model)}. Rules evaluate extracted screenshot fields;
PAID does not confirm bank settlement. Images are sent to the configured --host; local privacy requires a trusted local host.</small></p>"""
    (out / "report.html").write_text(page, encoding="utf-8")
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inbox", required=True, type=Path)
    ap.add_argument("--orders", required=True, type=Path)
    ap.add_argument("--store-name", required=True)
    ap.add_argument("--store-key", required=True)
    ap.add_argument("--out", default=Path("out"), type=Path)
    ap.add_argument("--model", default="gemma4:e2b")
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    orders = []
    with open(a.orders, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            row["cents"] = cents(row["amount_brl"])
            row["created_dt"] = parse_date(row["created"])
            orders.append(row)

    cache_path = a.out / "extractions.jsonl"
    cache = load_cache(cache_path)
    images = sorted(p for p in a.inbox.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
    for i, img in enumerate(images, 1):
        if img.name in cache:
            continue  # filename-only cache; see documented limitations
        try:
            fields, secs = extract(img, a.model, a.host)
            rec = dict(file=img.name, fields=fields, seconds=secs)
        except Exception as e:  # keep going; the failure is reported, never hidden
            rec = dict(file=img.name, fields={}, seconds=None, error=f"{type(e).__name__}: {e}")
        cache[img.name] = rec
        with open(cache_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[{i}/{len(images)}] {img.name} {rec.get('seconds')}s {rec.get('error', '')}", flush=True)

    receipts = [cache[p.name] for p in images]
    results, unpaid = decide(receipts, orders, a.store_name, a.store_key)
    for r in results:
        r["img"] = str((a.inbox / r["file"]).relative_to(a.out.parent)) if a.out.parent in (a.inbox / r["file"]).parents else str(a.inbox / r["file"])
    total = sum(r["seconds"] or 0 for r in receipts)
    summary = write_report(a.out, results, unpaid, total, a.model)
    print(summary)
    for r in results:
        print(f"  {r['file']}: {r['verdict']:<17} {r['order'] or '-':<6} {r['note']}")


if __name__ == "__main__":
    sys.exit(main())
