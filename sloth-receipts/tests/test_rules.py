"""Offline gates for screenshot triage; no OCR, network, payment or fixture rewriting."""
import copy
import importlib.util
import os
from datetime import datetime
from pathlib import Path
import unittest

SOURCE = Path(os.environ.get("SLOTH_SOURCE_ROOT", "/work/candidate")) / "sloth.py"
spec = importlib.util.spec_from_file_location("reviewed_sloth", SOURCE)
sloth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sloth)

KEY = "pix@preguicafeliz.example"
TXID = "E10203040202610201914Ab3kP9xQ2mZ"
FIELDS = dict(is_pix_receipt=True, status="Concluído", amount_brl="R$ 149,90",
              date="20/10/2026", time="19:14", payer_name="Ana Paula Ribeiro",
              payee_name="Loja Preguiça Feliz", payee_pix_key=KEY, transaction_id=TXID)

def order(order_id="O-101", amount=14990, customer="Ana Paula Ribeiro"):
    return dict(order_id=order_id, cents=amount, customer=customer,
                created="20/10/2026", created_dt=datetime(2026, 10, 20))

def result(changes=None, store_key=KEY, orders=None):
    fields = dict(FIELDS)
    fields.update(changes or {})
    rec = dict(file="synthetic.png", fields=fields, seconds=0)
    results, unpaid = sloth.decide([rec], orders or [order()], "Loja Preguiça Feliz", store_key)
    return results[0], unpaid

class RuleGates(unittest.TestCase):
    def test_exact_supported_status_passes(self):
        self.assertEqual(result()[0]["verdict"], "PAID")

    def test_unknown_or_embedded_status_never_paid(self):
        for status in ("", "Unknown", "Não concluído", "Concluído sem confirmação", "Concluído pendente",
                       "Concluido", "concluído", " Concluído ", None, ["Concluído"]):
            with self.subTest(status=status):
                self.assertNotEqual(result({"status": status})[0]["verdict"], "PAID")

    def test_negative_status_never_paid(self):
        for status in ("Agendado", "Em processamento", "Cancelado", "Devolvido", "Pendente"):
            with self.subTest(status=status):
                self.assertEqual(result({"status": status})[0]["verdict"], "NOT_COMPLETED")

    def test_boolean_false_is_not_receipt(self):
        self.assertEqual(result({"is_pix_receipt": False})[0]["verdict"], "NOT_A_RECEIPT")

    def test_non_boolean_receipt_flag_never_paid(self):
        for flag in ("true", "false", 1, 0, None, [], {}, ""):
            with self.subTest(flag=flag):
                self.assertEqual(result({"is_pix_receipt": flag})[0]["verdict"], "UNREADABLE")

    def test_txid_required(self):
        for txid in ("", None):
            with self.subTest(txid=txid):
                self.assertEqual(result({"transaction_id": txid})[0]["verdict"], "UNREADABLE")

    def test_malformed_txid_never_paid(self):
        for txid in ("placeholder", TXID[:-1], TXID+"X", "X"+TXID[1:], TXID.lower(),
                     TXID[:21]+"-b3kP9xQ2mZ", " "+TXID, TXID+" ", 42, [],
                     "E10203040202602301914Ab3kP9xQ2mZ", "E10203040202610202514Ab3kP9xQ2mZ"):
            with self.subTest(txid=txid):
                self.assertEqual(result({"transaction_id": txid})[0]["verdict"], "UNREADABLE")

    def test_exact_key_not_name_is_required(self):
        for key in ("", None, "pix@preguicafeliz.exsample", KEY.upper(), " "+KEY,
                    KEY+" ", "another@example.com", 123):
            with self.subTest(key=key):
                self.assertEqual(result({"payee_pix_key": key})[0]["verdict"], "WRONG_PAYEE")

    def test_payee_name_cannot_override_wrong_key(self):
        self.assertEqual(result({"payee_pix_key":"someone@example.com",
                                 "payee_name":"Loja Preguiça Feliz"})[0]["verdict"], "WRONG_PAYEE")

    def test_empty_configured_key_cannot_match_empty_field(self):
        self.assertEqual(result({"payee_pix_key":""}, store_key="")[0]["verdict"], "WRONG_PAYEE")

    def test_whitespace_only_keys_cannot_approve(self):
        for key in (" ", "\t", "\n", "\u00a0"):
            with self.subTest(key=repr(key)):
                self.assertEqual(result({"payee_pix_key":key}, store_key=key)[0]["verdict"], "WRONG_PAYEE")

    def test_configured_key_must_be_string(self):
        self.assertEqual(result({"payee_pix_key":123}, store_key=123)[0]["verdict"], "WRONG_PAYEE")

    def test_exact_key_does_not_depend_on_payee_name(self):
        self.assertEqual(result({"payee_name":""})[0]["verdict"], "PAID")

    def test_missing_amount_date_still_block(self):
        self.assertEqual(result({"amount_brl":""})[0]["verdict"], "UNREADABLE")
        self.assertEqual(result({"date":""})[0]["verdict"], "UNREADABLE")

    def test_old_date_still_blocks(self):
        self.assertEqual(result({"date":"02/09/2026"})[0]["verdict"], "STALE_DATE")

    def test_amount_mismatch_still_blocks(self):
        self.assertEqual(result({"amount_brl":"R$ 100,00"})[0]["verdict"], "AMOUNT_MISMATCH")

    def test_other_payer_still_requires_review(self):
        self.assertEqual(result({"payer_name":"Someone entirely different"})[0]["verdict"], "PAID_OTHER_PAYER")

    def test_duplicate_and_approximate_id_only_block(self):
        for txid in (TXID, TXID[:-1]+"Y"):
            with self.subTest(txid=txid):
                receipts = [dict(file="a.png", fields=dict(FIELDS)),
                            dict(file="b.png", fields=dict(FIELDS, transaction_id=txid))]
                results, _ = sloth.decide(receipts, [order()],
                                         "Loja Preguiça Feliz", KEY)
                self.assertEqual([r["verdict"] for r in results], ["PAID", "DUPLICATE"])

    def test_near_payer_name_never_paid(self):
        r, unpaid = result({"payer_name":"Ana Paula Ribeira"})
        self.assertEqual(r["verdict"], "PAID_OTHER_PAYER")
        self.assertEqual(len(unpaid), 1)

    def test_payer_case_accent_whitespace_normalization_is_exact(self):
        self.assertEqual(result({"payer_name":"  ÁNA   PAULA RIBEIRO  "})[0]["verdict"], "PAID")

    def test_payer_punctuation_is_not_removed(self):
        self.assertEqual(result({"payer_name":"Ana Paula-Ribeiro"})[0]["verdict"], "PAID_OTHER_PAYER")

    def test_same_amount_unique_exact_payer_selects_only_that_order(self):
        r, unpaid = result(orders=[order("O-OTHER", customer="Bruno Carvalho"), order()])
        self.assertEqual((r["verdict"], r["order"]), ("PAID", "O-101"))
        self.assertEqual([o["order_id"] for o in unpaid], ["O-OTHER"])

    def test_same_amount_two_exact_links_are_ambiguous(self):
        r, unpaid = result(orders=[order(), order("O-102")])
        self.assertEqual((r["verdict"], r["order"]), ("AMBIGUOUS_ORDER", None))
        self.assertEqual(len(unpaid), 2)

    def test_same_amount_no_exact_link_is_ambiguous(self):
        r, unpaid = result({"payer_name":"Third Party"},
                           orders=[order(), order("O-102", customer="Bruno Carvalho")])
        self.assertEqual((r["verdict"], r["order"]), ("AMBIGUOUS_ORDER", None))
        self.assertEqual(len(unpaid), 2)

    def test_other_payer_does_not_consume_order(self):
        _, unpaid = result({"payer_name":"Third Party"})
        self.assertEqual(len(unpaid), 1)

    def test_wrong_payer_then_right_payer_can_match(self):
        recs = [dict(file="other.png", fields=dict(FIELDS, payer_name="Third Party")),
                dict(file="exact.png", fields=dict(FIELDS, transaction_id=TXID[:-1]+"Y"))]
        # IDs must not be approximate duplicates for this order-consumption test.
        recs[1]["fields"]["transaction_id"] = "E55667788202610201922Qw8nL2vB7tY"
        rs, unpaid = sloth.decide(recs, [order()], "Loja Preguiça Feliz", KEY)
        self.assertEqual([r["verdict"] for r in rs], ["PAID_OTHER_PAYER", "PAID"])
        self.assertEqual(unpaid, [])

    def test_inputs_are_not_mutated(self):
        recs = [dict(file="a.png", fields=dict(FIELDS))]
        orders = [order()]
        before = copy.deepcopy((recs, orders))
        sloth.decide(recs, orders, "Loja Preguiça Feliz", KEY)
        self.assertEqual((recs, orders), before)

if __name__ == "__main__":
    unittest.main(verbosity=2)
