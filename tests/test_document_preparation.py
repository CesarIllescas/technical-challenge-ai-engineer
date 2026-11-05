"""Check rendering/orientation on generated documents, independent of challenge labels."""

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import pymupdf

from extract import load_image, rotation_to_upright


TEXT = "SYNTHETIC CREDENTIAL HOLDER NAME AND LICENSE NUMBER 00123 FOR INDEPENDENT TESTING ONLY"


class DocumentPreparationTests(unittest.TestCase):
    def test_unreadable_text_layer_keeps_existing_orientation(self):
        page = Mock()
        page.get_text.side_effect = RuntimeError("synthetic text-layer error")
        self.assertEqual(rotation_to_upright(page), 0)

    def test_all_quarter_turns_are_corrected_from_text_direction(self):
        for printed_rotation, correction in ((0, 0), (90, 90), (180, 180), (270, 270)):
            with self.subTest(printed_rotation=printed_rotation):
                with pymupdf.open() as pdf:
                    page = pdf.new_page(width=600, height=600)
                    page.insert_text((300, 300), TEXT, fontsize=5, rotate=printed_rotation)
                    self.assertEqual(rotation_to_upright(page), correction)

    def test_page_rotation_metadata_is_not_applied_twice(self):
        with pymupdf.open() as pdf:
            page = pdf.new_page(width=600, height=600)
            page.insert_text((300, 300), TEXT, fontsize=5, rotate=90)
            page.set_rotation(90)
            self.assertEqual(rotation_to_upright(page), 0)
            page.set_rotation(180)
            self.assertEqual(rotation_to_upright(page), 270)

    def test_missing_sparse_or_mixed_text_keeps_existing_orientation(self):
        with pymupdf.open() as pdf:
            page = pdf.new_page(width=600, height=600)
            page.set_rotation(90)
            self.assertEqual(rotation_to_upright(page), 0)
            page.insert_text((300, 300), "LOGO", fontsize=5, rotate=180)
            self.assertEqual(rotation_to_upright(page), 0)
        with pymupdf.open() as pdf:
            page = pdf.new_page(width=600, height=600)
            page.insert_text((300, 300), TEXT, fontsize=5)
            page.insert_text((310, 310), TEXT, fontsize=5, rotate=90)
            self.assertEqual(rotation_to_upright(page), 0)

    def test_pdf_renders_at_200_dpi_and_records_actual_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.pdf"
            with pymupdf.open() as pdf:
                pdf.new_page(width=144, height=216)
                pdf.save(path)
            preparation = {}
            mime, encoded = load_image(path, preparation=preparation)
            pixmap = pymupdf.Pixmap(base64.b64decode(encoded))
            self.assertEqual(mime, "image/png")
            self.assertEqual((pixmap.width, pixmap.height), (400, 600))
            self.assertEqual(preparation, {"format": "pdf", "page": 1, "dpi": 200,
                                           "rotation_degrees": 0, "width_px": 400, "height_px": 600})

    def test_sideways_page_is_rendered_upright_with_dimensions_swapped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rotated.pdf"
            with pymupdf.open() as pdf:
                page = pdf.new_page(width=600, height=720)
                page.insert_text((300, 300), TEXT, fontsize=5, rotate=90)
                pdf.save(path)
            preparation = {}
            _, encoded = load_image(path, preparation=preparation)
            pixmap = pymupdf.Pixmap(base64.b64decode(encoded))
            self.assertEqual(preparation["rotation_degrees"], 90)
            self.assertEqual((pixmap.width, pixmap.height), (2000, 1667))

    def test_image_bytes_are_preserved_without_rerendering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.png"
            pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 3, 2), False)
            original = pixmap.tobytes("png")
            path.write_bytes(original)
            preparation = {}
            mime, encoded = load_image(path, preparation=preparation)
            self.assertEqual(mime, "image/png")
            self.assertEqual(base64.b64decode(encoded), original)
            self.assertEqual(preparation, {"format": "png", "rendered": False})


if __name__ == "__main__":
    unittest.main()
