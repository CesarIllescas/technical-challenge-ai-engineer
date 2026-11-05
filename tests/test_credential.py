"""Offline behavioral checks for deterministic credential rules."""

import unittest

from credential import FIELDS, finalize_credential, normalize_date, schema_errors


def credential(**changes):
    return {
        "is_credential": True, "holder_name": "Example Name JR.",
        "credential_type": "Example Certification", "license_number": "00123-AB.9",
        "issuing_authority": "Example Board", "issue_date": "2020-01-01",
        "expiration_date": "2026-12-31", "expiration_status": "valid", **changes,
    }


class CredentialRuleTests(unittest.TestCase):
    def test_expiration_boundaries_override_model_status(self):
        cases = [
            ("2026-10-31", "expired"),
            ("2026-11-01", "expiring_soon"),
            ("2026-11-02", "expiring_soon"),
            ("2026-12-31", "expiring_soon"),
            ("2027-01-01", "valid"),
            (None, "no_expiration"),
        ]
        for expiration, expected in cases:
            with self.subTest(expiration=expiration):
                result = finalize_credential(credential(expiration_date=expiration, expiration_status="wrong"),
                                             "2026-11-01", 60)
                self.assertEqual(result["expiration_status"], expected)
                self.assertEqual(schema_errors(result), {})

    def test_window_and_reference_changes_are_applied(self):
        same_day = credential(expiration_date="2030-02-03")
        self.assertEqual(finalize_credential(same_day, "2030-02-03", 0)["expiration_status"], "expiring_soon")
        self.assertEqual(finalize_credential(same_day, "2030-02-02", 0)["expiration_status"], "valid")
        self.assertEqual(finalize_credential(same_day, "2030-02-02", 1)["expiration_status"], "expiring_soon")
        self.assertEqual(finalize_credential(same_day, "2030-02-04", 1)["expiration_status"], "expired")
        leap_day = credential(expiration_date="2028-02-29")
        self.assertEqual(finalize_credential(leap_day, "2028-02-28", 1)["expiration_status"], "expiring_soon")

    def test_non_credentials_clear_mentioned_data_even_when_dates_are_invalid(self):
        prediction = credential(is_credential=False, issue_date="not a date", expiration_date="02/03/26")
        expected = {field: False if field == "is_credential" else None for field in FIELDS}
        self.assertEqual(finalize_credential(prediction, "2026-11-01", 60), expected)
        self.assertEqual(finalize_credential({"is_credential": False}, "2026-11-01", 60), expected)

    def test_normalizes_only_unambiguous_dates_with_explicit_century(self):
        cases = [
            ("2028-02-29", "2028-02-29"),
            ("12/31/2026", "2026-12-31"),
            ("31/12/2026", "2026-12-31"),
            ("4/4/2026", "2026-04-04"),
            (" 2026-11-01 ", "2026-11-01"),
            (None, None),
        ]
        for printed, expected in cases:
            with self.subTest(printed=printed):
                self.assertEqual(normalize_date(printed), expected)
        result = finalize_credential(credential(issue_date="03/14/2012", expiration_date="31/12/2026"),
                                     "2026-11-01", 60)
        self.assertEqual(result["issue_date"], "2012-03-14")
        self.assertEqual(result["expiration_date"], "2026-12-31")

    def test_bad_dates_are_errors_instead_of_no_expiration(self):
        for invalid in ["03/04/2026", "12/15/26", "2026-02-30", "02/30/2026",
                        "", "null", "20261101", "2026-11-01T00:00:00", 20261101]:
            for field in ("issue_date", "expiration_date"):
                with self.subTest(invalid=invalid, field=field):
                    with self.assertRaises(ValueError):
                        finalize_credential(credential(**{field: invalid}), "2026-11-01", 60)

    def test_names_and_identifier_punctuation_are_preserved_without_mutating_input(self):
        original = credential(holder_name="Example JR", license_number="00012-34.5")
        snapshot = dict(original)
        result = finalize_credential(original, "2026-11-01", 60)
        self.assertEqual(result["holder_name"], "Example JR")
        self.assertEqual(result["license_number"], "00012-34.5")
        self.assertEqual(original, snapshot)

    def test_malformed_fields_are_rejected_without_type_coercion(self):
        cases = [None, [], {"is_credential": 1}, credential(license_number=123),
                 credential(holder_name=False), {**credential(), "summary": "extra"}]
        missing_expiration = credential()
        del missing_expiration["expiration_date"]
        cases.append(missing_expiration)
        for invalid in cases:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    finalize_credential(invalid, "2026-11-01", 60)

    def test_derived_status_does_not_require_a_valid_model_status(self):
        for supplied in (None, 1, "active"):
            self.assertEqual(finalize_credential(credential(expiration_status=supplied), "2026-11-01", 60)
                             ["expiration_status"], "expiring_soon")
        prediction = credential()
        del prediction["expiration_status"]
        self.assertEqual(finalize_credential(prediction, "2026-11-01", 60)["expiration_status"], "expiring_soon")


if __name__ == "__main__":
    unittest.main()
