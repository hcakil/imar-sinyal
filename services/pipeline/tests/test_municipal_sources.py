from __future__ import annotations

import unittest

from imarsinyal.sources.municipal import (
    parse_cankaya_list,
    parse_cankaya_notice,
    parse_kecioren_detail,
    parse_mamak_detail,
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

    def test_cankaya_only_reads_imar_table_and_pdf_metadata(self) -> None:
        html = """
        <div id="belgeler">
          <div>
            <h3>İmar İlanları <span>1</span></h3>
            <table><tbody><tr>
              <td>
                <div>Kırkkonaklar Mahallesi</div>
                <div>Kırkkonaklar Mahallesi 26374 Ada 5 Sayılı parselde
                1/1000 Ölçekli Uygulama İmar Planı Değişikliği</div>
              </td>
              <td>
                <a href="/uploads/kirkkonaklar.pdf" download>İndir</a>
                <a href="/uploads/kirkkonaklar.pdf">Görüntüle</a>
              </td>
            </tr></tbody></table>
          </div>
          <div>
            <h3>Yapı Kontrol İlanları <span>1</span></h3>
            <table><tbody><tr>
              <td>29398 Ada 2 Parseldeki Yapı Hakkında İlan</td>
              <td><a href="/uploads/yapi.pdf">Görüntüle</a></td>
            </tr></tbody></table>
          </div>
        </div>
        """
        candidates = parse_cankaya_list(html)
        self.assertEqual(len(candidates), 1)
        title, attachment = candidates[0]
        self.assertEqual(
            attachment,
            "https://www.cankaya.bel.tr/uploads/kirkkonaklar.pdf",
        )
        record = parse_cankaya_notice(
            title=title,
            attachment_url=attachment,
            pdf_text="""
            İLANIN ASKIYA ÇIKIŞ TARİHİ: 25.06.2026
            İLANIN ASKIDAN İNİŞ TARİHİ: 24.07.2026
            Ankara Büyükşehir Belediye Meclis Kararı:
            10.03.2026 gün ve 384 sayılı karar
            """,
        )
        self.assertEqual(record.source_type, "CANKAYA_ASKI")
        self.assertEqual(record.parcels, ["26374/5"])
        self.assertEqual(record.plan_scales, ["1/1000"])
        self.assertEqual(record.appeal_start_date, "2026-06-25")
        self.assertEqual(record.appeal_end_date, "2026-07-24")
        self.assertEqual(record.decision_number, "384")

    def test_mamak_text_notice_and_attachment_are_normalized(self) -> None:
        html = """
        <html><body>
          <div class="section-header">
            <h2>ASKI İLAN TUTANAĞI - 86230/1 NPP (LALAHAN TOPALAK SİT ALANI)</h2>
          </div>
          <div id="aski-bilgileri">
            <div id="aski-icerik">
              Karşıyaka/Lalahan Mahallesi 798 ada 1, 2 ve 3 numaralı
              parseller ile 799 ada 1 numaralı parseli kapsayan 86230/1
              numaralı parselasyon planı Ankara Büyükşehir Belediye
              Encümeninin 18.06.2026 tarih ve 1338/1482 sayılı kararı ile
              onaylanmıştır. 06.07.2026 - 06.08.2026 tarihleri arasında
              askıya çıkarılacaktır.
              <a href="/uploads/durum-haritasi.pdf">Durum haritası</a>
            </div>
            <strong>Askıya Alınma Tarihi:</strong><span>6.7.2026</span>
            <strong>Askı Bitim Tarihi:</strong><span>6.8.2026</span>
          </div>
        </body></html>
        """
        record = parse_mamak_detail(
            html,
            detail_url=(
                "https://www.mamak.bel.tr/aski_ilan/"
                "862301-npp-lalahan-topalak-sit-alani/"
            ),
            fallback_title="86230/1 NPP",
            published_text="Yayın Tarihi: 06 Temmuz 2026",
        )
        self.assertEqual(record.source_type, "MAMAK_ASKI")
        self.assertEqual(record.event_date, "2026-07-06")
        self.assertEqual(record.appeal_end_date, "2026-08-06")
        self.assertEqual(
            record.parcels,
            ["798/1", "798/2", "798/3", "799/1"],
        )
        self.assertNotIn("86230/1", record.parcels)
        self.assertEqual(record.decision_number, "1338/1482")
        self.assertEqual(
            record.documents["plan_note"].url,
            "https://www.mamak.bel.tr/uploads/durum-haritasi.pdf",
        )


if __name__ == "__main__":
    unittest.main()
