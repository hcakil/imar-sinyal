from __future__ import annotations

import unittest

from imarsinyal.sources.municipal import (
    parse_kecioren_detail,
    parse_polatli_detail,
)


class MunicipalSourceTests(unittest.TestCase):
    def test_polatli_pdf_notice_is_normalized(self) -> None:
        html = """
        <html>
          <head><meta property="og:title" content="Basri Mahallesi plan değişikliği | Polatlı Belediyesi"></head>
          <body>
            <div class="post-detail">
              Ankara İli Polatlı İlçesi Basri Mahallesi 108 Ada 1 Parsel ve
              109 Ada 1 Parsellere Ait 1/1000 Ölçekli Uygulama İmar Planı
              Değişikliği Ankara Büyükşehir Belediye Meclisinin 09.06.2026
              tarih ve 2026/750 sayılı kararı ile onaylanmıştır.
              Otuz günlük (01.07.2026 - 30.07.2026) askı ilan yapılacaktır.
              <a href="/upload/imarplanlari/plan.pdf">Plan</a>
            </div>
          </body>
        </html>
        """
        record = parse_polatli_detail(
            html,
            detail_url="https://www.polatli.bel.tr/imarplani/basri/71",
            fallback_title="Basri",
        )
        self.assertEqual(record.source_type, "POLATLI_ASKI")
        self.assertEqual(record.event_date, "2026-07-01")
        self.assertEqual(record.appeal_end_date, "2026-07-30")
        self.assertEqual(record.parcels, ["108/1", "109/1"])
        self.assertEqual(record.plan_scales, ["1/1000"])
        self.assertEqual(
            record.documents["plan_note"].url,
            "https://www.polatli.bel.tr/upload/imarplanlari/plan.pdf",
        )

    def test_kecioren_image_notice_is_normalized(self) -> None:
        html = """
        <html><body>
          <section class="subheader"><h2>91771 ada 6 ve 9 sayılı parsellere ilişkin
          1/1000 ölçekli Uygulama İmar Planı Değişikliği</h2></section>
          <div class="etext">
            Ovacık Mahallesi. Plan 08.05.2026 tarihinden itibaren 1 ay süre ile
            askıya çıkartılmıştır. Ankara Büyükşehir Belediye Meclisi'nin
            10.03.2026 tarih ve 412 sayılı kararı.
            <a href="/images/files/91771_plan.jpg">Ayrıntı</a>
          </div>
        </body></html>
        """
        record = parse_kecioren_detail(
            html,
            detail_url="https://www.kecioren.bel.tr/plan-650-duyuru.html",
            fallback_title="Plan değişikliği",
        )
        self.assertEqual(record.source_type, "KECIOREN_ASKI")
        self.assertEqual(record.event_date, "2026-05-08")
        self.assertEqual(record.appeal_end_date, "2026-06-07")
        self.assertEqual(record.parcels, ["91771/6", "91771/9"])
        self.assertEqual(record.neighborhood, "Ovacık")
        self.assertEqual(
            record.documents["plan_note"].media_type,
            "image/jpeg",
        )


if __name__ == "__main__":
    unittest.main()
