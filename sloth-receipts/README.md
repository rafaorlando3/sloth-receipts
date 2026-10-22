# 🦥 sloth-receipts

**Advisory triage of Pix receipt screenshots against open orders, using extracted fields.**

Gemma 4 through Ollama can read images; Python rules produce a review report. A screenshot, an OCR field or a `PAID` label is **not bank settlement confirmation**. Use a bank statement or an authenticated PSP event for that.

This version corrects unsafe acceptance in public commit `b43f4773e2bc86438f3b6706e27e342b98ec2891`. It has not been deployed or tested with real payments. No model was run for this correction.

## Rules for an advisory PAID match

All gates must pass together:

1. `is_pix_receipt` is the real JSON boolean `true`; strings and numbers are unreadable.
2. The amount and date can be parsed by the existing parsers.
3. Status is exactly the explicitly supported literal `Concluído`. Empty, negated, unknown, padded or other status text requires review.
4. The transaction ID matches the supported E2E syntax: uppercase `E`, eight digits, a valid `YYYYMMDDHHMM` timestamp, and eleven ASCII alphanumeric characters. It is not repaired, case-folded or stripped before acceptance. A well-formed ID is not proof that OCR read it correctly or that it exists at a bank.
5. The extracted Pix key is byte-for-byte equal to the nonempty configured key. Payee-name similarity never substitutes for the key.
6. The ID is not an exact or approximate duplicate in this batch. Approximation can only block a match; it cannot approve one.
7. There is exactly one open order with the same amount and exact payer name after documented case, accent and whitespace normalization. Punctuation is preserved. An approximate name never approves `PAID`.
8. The existing date gate passes (default one-day tolerance before the order date).

Only a `PAID` rule match removes its order from this in-memory batch. A different payer or ambiguous order keeps the orders open. No payment, bank update or order-system write is performed.

The status and E2E policy is intentionally narrow. Legitimate receipts outside this supported format may require review. These checks do not detect forged screenshots, establish settlement, or establish that OCR output matches the image.

| Verdict | Meaning |
|---|---|
| `PAID` | Advisory screenshot-field match, not payment confirmation |
| `AMOUNT_MISMATCH` | Exact payer text has an order with another amount |
| `DUPLICATE` | Exact or approximate ID collision; review rather than approval |
| `WRONG_PAYEE` | Extracted key differs from configured key, possibly an OCR error |
| `STALE_DATE` | Receipt date fails the existing order-date tolerance |
| `NOT_COMPLETED` | Status is not the explicitly supported completed literal |
| `AMBIGUOUS_ORDER` | No unique exact payer-and-amount link; orders stay open |
| `PAID_OTHER_PAYER` | Amount matches a single order but payer text differs; order stays open |
| `NO_ORDER` | No supported open-order match |
| `NOT_A_RECEIPT` / `UNREADABLE` | False receipt flag, invalid type or missing/malformed required fields |

## Corrected offline reassessment of the 12 saved examples

The original fictional images, `samples/truth.json`, orders and `out/extractions.jsonl` are unchanged. The new rules were applied to the saved extractions, **without new OCR, Ollama, a GPU, network access or bank access**.

| Measure | Result |
|---|---|
| Old rules versus original truth verdict labels | 12/12 |
| Corrected rules versus the same unchanged labels | **7/12** |
| Advisory PAID rule matches | **1/12** |
| Receipts needing review | **11/12** |
| Orders still open after the corrected rules | 10/11 |

This is a small team-authored sample comparison, not independent accuracy, a production guarantee, or a new model benchmark. The five label changes are preserved rather than relabelled to recover 12/12:

| File | Old verdict | Corrected verdict | Reason |
|---|---|---|---|
| r02.png | PAID | UNREADABLE | Malformed saved E2E |
| r03.png | PAID | WRONG_PAYEE | OCR key differs from configured key |
| r05.png | PAID | UNREADABLE | Malformed saved E2E |
| r06.png | DUPLICATE | WRONG_PAYEE | Nonmatching OCR key blocks earlier than duplicate classification |
| r09.png | PAID | UNREADABLE | Malformed saved E2E |

The unchanged saved extractions retain the old evaluator's matches: amount/date/payer/status 12/12 each, Pix key 8/12, transaction ID 8/12. The saved extraction durations average 52.1 seconds (maximum 61.5); they are historical values, not timings from this correction. The original claim of 2 vCPU / 7 GB / no GPU was not independently reproduced here. No 500-image or eight-hour run was performed.

`out/report.csv`, `out/report.html` and `docs/run.log` now describe the offline reassessment. The previous log, report, PNG and GIF are preserved under `historical/public-b43f477/`. The old log says 6 paid / 6 review and labels r10 PAID, which disagrees with its old report/truth. The old GIF was generated from historical artifacts and is **retired from current documentation**, not presented as a corrected run. No replacement GIF or new screenshot capture is claimed.

## Offline regression tests (no OCR)

From the public repository root:

```bash
cd sloth-receipts
SLOTH_SOURCE_ROOT="$PWD" python -I -B tests/test_rules.py
```

The 27 standard-library tests call only the rules, not Ollama or the network. The environment variable points to this repository directory; the test default `/work/candidate` is only for the isolated review package.

## Running the image reader separately

This correction does not install or run Ollama or a model. If already installed, the existing reader accepts Python 3.9+ and standard-library dependencies:

```bash
python sloth.py --inbox samples/inbox --orders samples/orders.csv \
  --store-name "Loja Preguiça Feliz" --store-key pix@preguicafeliz.example --out out
python eval.py out
```

`orders.csv` has `order_id,customer,amount_brl,created` (e.g. `149,90`, `20/10/2026`). `eval.py` compares verdict labels, not full order-link correctness, and uses legacy field normalizations. Preserve the sample inputs if comparing results.

The reader sends image bytes to the configured `--host` (`http://127.0.0.1:11434` by default). Privacy and offline operation require a trusted local endpoint; the program accepts other hosts. Model download, licensing and runtime setup are separate from this correction.

## Cache and other limits

- The cache is keyed **only by filename**, not image bytes, model, prompt or rule version. Replacing an image under the same name can reuse stale extraction.
- Failed extractions are cached too. There is no automatic retry, content-addressed validation, atomic JSONL write or guaranteed crash recovery. A truncated final line can prevent loading. Do not treat this as a safe unattended resume mechanism.
- Duplicate detection is only within the current `decide` batch. There is no persistent cross-day payment ledger.
- Amount parsing, date tolerance and screenshot authenticity remain limited; this is not a general financial validation engine.
- The twelve images are explicitly fictional. No real-customer or bank verification was done.
- No current GIF, overnight-throughput claim or 12/12 corrected-verdict claim is made.

## License

Code: MIT. Model terms are separate.
