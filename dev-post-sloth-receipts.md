---
title: "Gemma 4 checks my Pix receipts while I sleep: 12 of 12 verdicts right, even when it misreads"
published: false
tags: devchallenge, hf26challenge, opensource, ai
---

*This is a submission for the [Hacktoberfest 2026 Open-Source AI Challenge, Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19).*

## What I Built

**sloth-receipts** is a small command-line tool. Before bed, you drop the day's Pix payment screenshots into a folder next to a CSV of open orders. Overnight, Gemma 4 reads them one at a time on your own laptop. In the morning there is one short list of what needs you.

I live in Pedro Juan Caballero, on the Paraguay–Brazil border, and I build payment software for small shops that sell to Brazilian customers. Pix is how those customers pay. The proof usually arrives as a screenshot in the WhatsApp chat, and someone has to check every one of them:

- Is the amount right?
- Did the money go to *our* Pix key?
- Is it a finished payment, or only a scheduled one?
- Is this the same screenshot someone sent yesterday?

It is boring, it piles up at night, and it is easy to get wrong when you are tired.

sloth-receipts takes that chore. The person who gets to be lazier is the shop owner who used to do it by hand before closing. The tool only marks a receipt **PAID** when every check agrees. Anything doubtful goes to a short "needs you" list with the reason in plain words: *paid R$ 89,90, order is R$ 98,90 (short R$ 9,00)*, or *same transaction as r01.png*.

## Demo

![sloth-receipts demo: inbox at night, slow overnight run, morning report](https://raw.githubusercontent.com/rafaorlando3/sloth-receipts/main/docs/demo.gif)

The morning report from the real run:

![morning report](https://raw.githubusercontent.com/rafaorlando3/sloth-receipts/main/docs/report.png)

All 12 receipts are **fictional**, and each image carries a "FICTIONAL SAMPLE" footer. I wrote them to cover the cases that actually go wrong:

- a short payment
- a reused screenshot sent by a different customer
- money sent to the wrong person
- an old receipt
- a scheduled (*agendado*) Pix that is not a payment yet
- an order paid by a relative
- one receipt that is rotated and blurred
- one receipt with no matching order

## Code

{% github rafaorlando3/sloth-receipts %}

## How I Built It

It is two parts that do very different jobs.

**1. Gemma reads.** `gemma4:e2b` runs locally through Ollama: open weights, 4-bit quantized, about 4 GB, with vision. Each screenshot goes in with a prompt and a JSON schema (Ollama's `format`), so the answer is always the same nine fields: `is_pix_receipt`, `status`, `amount_brl`, `date`, `time`, `payer_name`, `payee_name`, `payee_pix_key`, `transaction_id`. Temperature is 0 and thinking is off. Each result is written to a JSONL file right away, so if the laptop goes to sleep at 3 am the next run picks up where it stopped.

**2. Rules decide.** About 60 lines of plain Python, standard library only, turn those fields into a verdict. The order of the checks matters:

1. Not completed? A scheduled or pending Pix stops here.
2. Paid to someone else? The payee key or name is compared with the store's.
3. Seen this transaction id before? That makes it a duplicate.
4. Find an open order with the same amount, preferring the closest payer name.
5. No amount match, but the payer clearly is a customer? That is an amount mismatch.
6. Receipt older than the order? It is stale.
7. Someone else paid? It is paid, but flagged for a look.

I kept the model out of the decision on purpose. A language model is a great reader and a bad accountant.

That split paid off once I measured it. There is an `eval.py` that scores everything against the ground truth of the samples:

| On 12 fictional receipts, 2 vCPU / 7 GB RAM, no GPU | |
|---|---|
| Amount, date, payer, status read exactly | **12/12** each |
| Pix key read exactly | 8/12 |
| 32-character transaction id read exactly | 8/12 |
| Final verdicts correct | **12/12** |
| Time per receipt | 52 s average |

Gemma never got an amount or a name wrong. It did slip characters in long ids: `Lp0oK9iJ8uH` became `Lp00K9ij8uH`, and the blurred one gained an extra `8`. If the rules had demanded an exact id match, the reused screenshot would have passed as a new payment. So ids and keys are compared with a small edit tolerance, and that tolerance is only ever used to *raise* a flag, never to confirm a payment.

## Why Does Open Innovation Matter?

Look at what is on one of these screenshots: a customer's full name, how much they paid, to whom, and a transaction id. That is exactly the data a small shop should not be uploading to a third-party API every night.

With an open-weight model:

- **The data stays on the counter.** The screenshots never leave the shop's computer.
- **The cost does not grow with sales.** There is no per-image bill, so a busy week costs the same as a quiet one.
- **It works when the internet doesn't.** On the border, that is not a hypothetical.
- **Slow is fine.** At 52 seconds a receipt, a no-GPU laptop gets through about 500 screenshots in an 8-hour night. Nobody needs the answer at 2 am, only by 7 am. Open weights let me trade speed for privacy and zero cost, a trade a closed API does not offer.

And because the model is open, anyone can run the same `eval.py` on their own bank's layouts and see the real error rate before trusting it.

## The Lazy Payoff

- **Before:** open a chat, open the image, find the order, compare, repeat.
- **After:** read seven lines with a coffee.

On the sample night the tool cleared 5 receipts on its own. The other 7 went to the list, each with its reason; six were real problems, and the seventh was a relative paying for a customer. The duplicate and the payment to the wrong person are exactly the two that cost money when you check by hand at midnight.

## Prize Categories

- **Gemma:** the whole tool runs on `gemma4:e2b` locally through Ollama, with vision and structured JSON output.

---

*Limits, honestly:* the samples are fictional, and real bank layouts vary more. A screenshot is evidence, not settlement, so the real confirmation is still the bank statement or the PSP webhook. This tool sorts the pile and points at the suspicious ones.
