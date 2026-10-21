"""Generate fictional Pix receipt screenshots + an orders file for the demo.

Every name, bank, key and ID here is invented. Each image carries a
"FICTIONAL SAMPLE" footer so it can never pass as a real receipt.
"""
import csv, json, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = Path(__file__).parent
OUT = HERE / "inbox"
OUT.mkdir(exist_ok=True)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
random.seed(7)

STORE = "Loja Preguiça Feliz"
STORE_KEY = "pix@preguicafeliz.example"


def f(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def e2e(ispb, when, tail):
    # Pix end-to-end id format: E + 8-digit ISPB + yyyyMMddHHmm + 11 chars
    return f"E{ispb}{when}{tail}"


THEMES = {
    "light": dict(bg=(250, 250, 250), fg=(30, 30, 30), accent=(0, 120, 90), muted=(120, 120, 120)),
    "dark": dict(bg=(24, 24, 32), fg=(235, 235, 240), accent=(130, 90, 255), muted=(150, 150, 165)),
    "green": dict(bg=(232, 245, 236), fg=(20, 50, 30), accent=(10, 110, 60), muted=(90, 120, 100)),
}


def draw_receipt(path, theme, bank, title, amount, date, time, payer, payee, payee_key, txid,
                 status="Concluído", rotate=0, blur=0.0):
    t = THEMES[theme]
    img = Image.new("RGB", (720, 1280), t["bg"])
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 720, 110], fill=t["accent"])
    d.text((36, 34), bank, font=f(38, True), fill=(255, 255, 255))
    y = 150
    d.text((36, y), title, font=f(34, True), fill=t["fg"]); y += 70
    d.text((36, y), "Valor", font=f(26), fill=t["muted"]); y += 38
    d.text((36, y), amount, font=f(56, True), fill=t["fg"]); y += 100
    rows = [("Situação", status), ("Data", f"{date} às {time}"), ("De", payer),
            ("Para", payee), ("Chave Pix", payee_key), ("ID da transação", txid)]
    for label, value in rows:
        d.text((36, y), label, font=f(24), fill=t["muted"]); y += 34
        size = 22 if label == "ID da transação" else 30
        d.text((36, y), value, font=f(size, label != "ID da transação"), fill=t["fg"]); y += 62
        d.line([36, y - 14, 684, y - 14], fill=t["muted"], width=1)
    d.text((36, 1215), "FICTIONAL SAMPLE · sloth-receipts demo · not a real receipt",
           font=f(18), fill=t["muted"])
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    if rotate:
        img = img.rotate(rotate, expand=True, fillcolor=(200, 200, 200))
    img.save(path)


orders = [
    # id, customer, amount, created (dd/mm/yyyy)
    ("O-101", "Ana Paula Ribeiro", "149,90", "20/10/2026"),
    ("O-102", "Bruno Carvalho", "59,00", "20/10/2026"),
    ("O-103", "Camila Duarte", "212,40", "20/10/2026"),
    ("O-104", "Diego Fernandes", "98,90", "20/10/2026"),
    ("O-105", "Eduarda Lima", "35,50", "20/10/2026"),
    ("O-106", "Fábio Nogueira", "149,90", "20/10/2026"),
    ("O-107", "Gabriela Prado", "120,00", "20/10/2026"),
    ("O-108", "Heitor Queiroz", "76,30", "20/10/2026"),
    ("O-109", "Isabela Rocha", "189,00", "20/10/2026"),
    ("O-110", "João Teixeira", "64,80", "20/10/2026"),
    ("O-111", "Karina Vieira", "250,00", "20/10/2026"),
]

E = {
    "r01": e2e("10203040", "202610201914", "Ab3kP9xQ2mZ"),
    "r02": e2e("55667788", "202610201922", "Qw8nL2vB7tY"),
    "r03": e2e("10203040", "202610202005", "Zx5cV1bN6mK"),
    "r04": e2e("99887766", "202610202031", "Lp0oK9iJ8uH"),
    "r05": e2e("55667788", "202610202047", "Mn4bV3cX2zA"),
    "r07": e2e("10203040", "202610202110", "Gt6yH5uJ4iK"),
    "r08": e2e("99887766", "202609021530", "Rf3eD2wS1qA"),
    "r09": e2e("55667788", "202610202133", "Yh7uJ6iK5oL"),
    "r10": e2e("10203040", "202610202140", "Bv2nM1qW9eR"),
    "r11": e2e("99887766", "202610202151", "Tc8vB7nM6qW"),
    "r12": e2e("55667788", "202610202158", "Ui9oP8lK7jH"),
}

R = []  # (file, kwargs, expected verdict, expected order)
R.append(("r01.png", dict(theme="light", bank="Banco Aurora", title="Pix enviado", amount="R$ 149,90",
          date="20/10/2026", time="19:14", payer="Ana Paula Ribeiro", payee=STORE,
          payee_key=STORE_KEY, txid=E["r01"]), "PAID", "O-101"))
R.append(("r02.png", dict(theme="dark", bank="Capivara Bank", title="Comprovante Pix", amount="R$ 59,00",
          date="20/10/2026", time="19:22", payer="Bruno Carvalho", payee=STORE,
          payee_key=STORE_KEY, txid=E["r02"]), "PAID", "O-102"))
R.append(("r03.png", dict(theme="green", bank="Coop Ipê", title="Transferência realizada", amount="R$ 212,40",
          date="20/10/2026", time="20:05", payer="Camila Duarte", payee=STORE,
          payee_key=STORE_KEY, txid=E["r03"]), "PAID", "O-103"))
R.append(("r04.png", dict(theme="light", bank="Banco Jacarandá", title="Pix enviado", amount="R$ 89,90",
          date="20/10/2026", time="20:31", payer="Diego Fernandes", payee=STORE,
          payee_key=STORE_KEY, txid=E["r04"]), "AMOUNT_MISMATCH", "O-104"))
R.append(("r05.png", dict(theme="dark", bank="Capivara Bank", title="Comprovante Pix", amount="R$ 35,50",
          date="20/10/2026", time="20:47", payer="Eduarda Lima", payee=STORE,
          payee_key=STORE_KEY, txid=E["r05"]), "PAID", "O-105"))
# r06: Fábio sends Ana's receipt again (same transaction id, cropped/blurred copy)
R.append(("r06.png", dict(theme="light", bank="Banco Aurora", title="Pix enviado", amount="R$ 149,90",
          date="20/10/2026", time="19:14", payer="Ana Paula Ribeiro", payee=STORE,
          payee_key=STORE_KEY, txid=E["r01"], blur=0.8), "DUPLICATE", "O-106"))
R.append(("r07.png", dict(theme="green", bank="Coop Ipê", title="Transferência realizada", amount="R$ 120,00",
          date="20/10/2026", time="21:10", payer="Gabriela Prado", payee="Marcos Antunes",
          payee_key="marcos.antunes@example.com", txid=E["r07"]), "WRONG_PAYEE", "O-107"))
R.append(("r08.png", dict(theme="light", bank="Banco Jacarandá", title="Pix enviado", amount="R$ 76,30",
          date="02/09/2026", time="15:30", payer="Heitor Queiroz", payee=STORE,
          payee_key=STORE_KEY, txid=E["r08"]), "STALE_DATE", "O-108"))
R.append(("r09.png", dict(theme="dark", bank="Capivara Bank", title="Comprovante Pix", amount="R$ 189,00",
          date="20/10/2026", time="21:33", payer="Isabela Rocha", payee=STORE,
          payee_key=STORE_KEY, txid=E["r09"], rotate=7, blur=1.2), "PAID", "O-109"))
# r10: João's order paid by his wife: payer differs, still a payment
R.append(("r10.png", dict(theme="light", bank="Banco Aurora", title="Pix enviado", amount="R$ 64,80",
          date="20/10/2026", time="21:40", payer="Larissa Teixeira", payee=STORE,
          payee_key=STORE_KEY, txid=E["r10"]), "PAID_OTHER_PAYER", "O-110"))
# r11: a scheduled Pix, not a completed payment
R.append(("r11.png", dict(theme="green", bank="Coop Ipê", title="Pix agendado", amount="R$ 250,00",
          date="25/10/2026", time="08:00", payer="Karina Vieira", payee=STORE,
          payee_key=STORE_KEY, txid=E["r11"], status="Agendado"), "NOT_COMPLETED", "O-111"))
# r12: a receipt with no matching order
R.append(("r12.png", dict(theme="dark", bank="Capivara Bank", title="Comprovante Pix", amount="R$ 45,00",
          date="20/10/2026", time="21:58", payer="Mateus Barros", payee=STORE,
          payee_key=STORE_KEY, txid=E["r12"]), "NO_ORDER", None))

truth = {}
for name, kw, verdict, order in R:
    draw_receipt(OUT / name, **kw)
    truth[name] = dict(expected_verdict=verdict, expected_order=order,
                       amount=kw["amount"], date=kw["date"], time=kw["time"], payer=kw["payer"],
                       payee=kw["payee"], payee_key=kw["payee_key"], txid=kw["txid"],
                       status=kw.get("status", "Concluído"))

with open(HERE / "orders.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["order_id", "customer", "amount_brl", "created"])
    w.writerows(orders)
(HERE / "truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"{len(R)} receipts, {len(orders)} orders written to {HERE}")
