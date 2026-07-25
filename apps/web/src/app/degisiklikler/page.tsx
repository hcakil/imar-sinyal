import type { Metadata } from "next";
import { EventFilter } from "@/components/event-filter";
import { eventDistricts, listEvents } from "@/lib/events";

export const metadata: Metadata = {
  title: "İmar değişiklikleri",
  description:
    "Ankara'daki güncel meclis kararları ve imar askılarını ilçe, aşama ve değişiklik türüne göre filtreleyin.",
};

export const dynamic = "force-dynamic";

export default async function EventsPage() {
  const [events, districts] = await Promise.all([
    listEvents({}, 200),
    eventDistricts(),
  ]);

  return (
    <section className="page-section">
      <div className="shell">
        <div className="page-heading">
          <span className="section-kicker">ANKARA DEĞİŞİKLİK AKIŞI</span>
          <h1>İmar kararları, tek ve aranabilir bir akışta.</h1>
          <p>
            Resmî kaynaklardan bulunan kayıtları ilçe, aşama ve etki seviyesine
            göre süzün. Yapılaşma verileri yalnızca kanıt bulunduğunda gösterilir.
          </p>
        </div>
        <EventFilter events={events} districts={districts} />
      </div>
    </section>
  );
}
