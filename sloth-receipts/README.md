# 🦥 sloth-receipts

**Check the day's Pix payment screenshots against your orders while you sleep, on your own laptop.**

Small shops in Brazil that sell over WhatsApp get paid by Pix, and the proof usually arrives as a screenshot in the chat. Someone has to open each one, find the order, compare the amount, look at who was paid, and notice the screenshot that was already used yesterday. sloth-receipts does that overnight and leaves a short list in the morning of only what needs a human.

![demo](docs/demo.gif)

## How it works

1. Put the screenshots in a folder and export your open orders as a CSV.
2. Gemma 4 (`gemma4:e2b`, open weights, through Ollama) reads each image and returns the fields as JSON: status, amount, date, payer, payee, Pix key, transaction id.
3. Plain Python rules decide. The model never decides what is paid.
4. In the morning you get `out/report.html` and `out/report.csv`.

A receipt is marked **PAID** only when the payment is completed, went to your Pix key, has a new transaction id, matches an open order's amount, is not older than the order, and was paid by the customer. Everything else goes to "needs you":

| Verdict | Meaning |
|---|---|
| `AMOUNT_MISMATCH` | Paid a different amount than the order (shows how much short or over) |
| `DUPLICATE` | Same transaction id as an earlier receipt (a reused screenshot) |
| `WRONG_PAYEE` | Money went to someone else's Pix key |
| `STALE_DATE` | Receipt is older than the order |
| `NOT_COMPLETED` | Scheduled (*agendado*) or pending, not a finished payment |
| `NO_ORDER` | No open order matches |
| `PAID_OTHER_PAYER` | Amount matches but another person paid (often family; worth a look) |
| `NOT_A_RECEIPT` / `UNREADABLE` | Not a Pix receipt, or the key fields could not be read |

It is slow on purpose. It reads one image at a time and saves each result as it goes. If the laptop sleeps or the run is stopped, the next run continues where it stopped.

## Run it

```bash
# 1. Ollama + the model (about 4 GB on disk)
ollama pull gemma4:e2b

# 2. Fictional sample data (12 receipts, 11 orders, ground truth; needs Pillow)
python samples/make_samples.py

# 3. The overnight run (Python 3.9+, standard library only)
python sloth.py --inbox samples/inbox --orders samples/orders.csv \
  --store-name "Loja Preguiça Feliz" --store-key pix@preguicafeliz.example --out out

# 4. Score what Gemma read and what the rules decided against the ground truth
python eval.py out
```

`orders.csv` needs four columns: `order_id,customer,amount_brl,created` (amount like `149,90`, date `dd/mm/yyyy`).

## Results on the sample set

These come from one run of `gemma4:e2b` (Q4_K_M) on a 2 vCPU, 7 GB RAM cloud VM with no GPU.

| | |
|---|---|
| Time per receipt | 52 s on average (max 61.5 s, the rotated and blurred one) |
| Amount, date, payer name, status read exactly | 12/12 each |
| Pix key read exactly | 8/12 |
| Transaction id read exactly (32 characters) | 8/12 |
| **Final verdicts correct** | **12/12** |

The model reads amounts and names very well, and it slips one or two characters in long ids (`Lp0oK9iJ8uH` became `Lp00K9ij8uH`). For that reason the rules compare Pix keys and ids with a small tolerance, and they never treat a near-miss as proof of payment. The duplicate check still caught the reused screenshot, and the wrong-payee check still caught the payment sent to another person's key.

At about 70 receipts an hour, an 8-hour night covers roughly 500 screenshots on a laptop with no GPU.

## Why local and open

The screenshots show customers' names, amounts and transaction ids. With an open-weight model they never leave the shop's computer, there is no per-image bill, and the check keeps working when the internet is down.

## Limits

- The samples are fictional and every image is labelled as such. Real banks' layouts vary more, so test on your own screenshots (they stay on your machine) before trusting the verdicts.
- A screenshot is evidence, not settlement. The real confirmation is your bank statement or your PSP's webhook. This tool sorts the pile and points at the suspicious ones.

## License

MIT
