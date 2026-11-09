"use client";
/**
 * One Canon remedy in the time machine (experience Req 30.3; time-machine design §10.2): the
 * molecules with why they were chosen, ADMET predictions labelled as predictions, measured
 * activity with assay names (a screening result is not an effect), interaction pointers, today's
 * medicines, and the exposure card: the historical amount (never as a dose to take), the modelled
 * peak as a band with the validation table next to it, and the verdict or the reason there is none.
 */
import { BackLink, Disclosure, LargeTitle } from "@/components/cards";
import { StateView } from "@/components/StateView";
import type { Result } from "@/api/client";
import { useCall } from "@/flow/useCall";
import type { TimeMachineClient } from "@/timemachine/client";
import type {
  Catalogue,
  Constituent,
  Exposure,
  SubstanceOut,
} from "@/timemachine/model";
import { englishShownFor, logAxis, reasonCode } from "@/timemachine/view";
import { useT, type Translate } from "@/theme/words";

import {
  English,
  IntervalChart,
  References,
  Section,
  TmLabels,
  useHashId,
  useNum,
  useTimeMachineClient,
  ValidationBlock,
} from "./common";

const ADMET_NAMED = ["PPBR_AZ", "Half_Life_Obach", "VDss_Lombardo"];
const ACTIVITIES_SHOWN = 8;

/**
 * An ADMET-AI prediction outside the possible range (binding above 100 %, a negative half-life or
 * volume, a probability outside 0–1) is not shown as a number (pharmacologist review A5).
 */
export function admetUsable(name: string, v: number): boolean {
  if (name === "PPBR_AZ") return v >= 0 && v <= 100;
  // A half-life or a volume of zero or below is physically impossible; ADMET-AI returns one for
  // 20.7 % / 35.4 % of predictions (PK-1 calibration): never shown (owner decision 2026-11-09).
  if (name === "Half_Life_Obach" || name === "VDss_Lombardo") return v > 0;
  return v >= 0 && v <= 1;
}

async function load(
  c: TimeMachineClient,
  id: string,
): Promise<Result<{ s: SubstanceOut; catalogue: Catalogue }>> {
  const [s, cat] = await Promise.all([c.substance(id), c.catalogue()]);
  if (!s.ok) return s;
  if (!cat.ok) return cat;
  return { ok: true, data: { s: s.data, catalogue: cat.data } };
}

export function reasonText(t: Translate, text: string | null | undefined) {
  const r = reasonCode(text);
  if (r)
    return t(
      `TimeMachine.reasons.${r.code}`,
      r.n !== undefined ? { n: r.n } : {},
    );
  return text || null;
}

export function SubstanceView() {
  const t = useT();
  const id = useHashId();
  const { client, recorded } = useTimeMachineClient();
  const call = useCall(client && id ? () => load(client, id) : null, [
    client,
    id,
  ]);

  const known = id && call.status === "ok";
  return (
    <>
      <BackLink href="/research/time-machine">{t("TimeMachine.back")}</BackLink>
      <LargeTitle
        eyebrow={t("TimeMachine.title")}
        title={
          known ? t(`TimeMachine.substances.${id}`) : t("TimeMachine.title")
        }
      />
      <TmLabels recorded={recorded} />
      {id === null ? (
        <StateView state="error" messageKey="TimeMachine.errors.unknown" />
      ) : call.status === "error" ? (
        <StateView
          state="error"
          messageKey={call.error.messageKey}
          retry={call.retry}
        />
      ) : call.status !== "ok" ? (
        <StateView state="loading" label={t("TimeMachine.loading")} />
      ) : (
        <Body s={call.data.s} catalogue={call.data.catalogue} />
      )}
    </>
  );
}

function Body({ s, catalogue }: { s: SubstanceOut; catalogue: Catalogue }) {
  const t = useT();
  const modelled = s.exposure.some((e) => e.model);
  return (
    <div className="grid gap-group lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-start">
      <div className="flex min-w-0 flex-col gap-group">
        <Section
          id="tm-constituents"
          title={t("TimeMachine.substance.constituents")}
          testId="tm-constituents"
        >
          {s.substance.constituents.length === 0 ? (
            <p>{t("TimeMachine.substance.none")}</p>
          ) : (
            <ul className="grouped-plain">
              {s.substance.constituents.map((c) => (
                <ConstituentRow key={c.compound} c={c} refs={s.references} />
              ))}
            </ul>
          )}
        </Section>
        <Section
          id="tm-todays"
          title={t("TimeMachine.substance.todays")}
          testId="tm-todays"
        >
          <ul className="grouped-plain">
            {s.substance.todays_drugs.map((d, i) => (
              <li
                key={`${d.drug}-${d.condition_key}-${i}`}
                className="flex flex-col gap-1"
              >
                <span className="font-bold">
                  {d.drug}{" "}
                  <span className="font-normal text-muted">
                    · {d.indication_term}
                  </span>
                </span>
                {d.label_set_id ? (
                  <a
                    className="inline-flex min-h-11 items-center self-start text-sm"
                    href={`https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=${encodeURIComponent(d.label_set_id)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {t("TimeMachine.substance.label")}
                  </a>
                ) : null}
                <English>{d.bridge_note}</English>
              </li>
            ))}
          </ul>
        </Section>
      </div>
      <div className="flex min-w-0 flex-col gap-group">
        <Section
          id="tm-exposure"
          title={t("TimeMachine.substance.exposure")}
          testId="tm-exposure"
        >
          {s.exposure.length === 0 ? (
            <p>{t("TimeMachine.substance.noExposure")}</p>
          ) : (
            s.exposure.map((e) => <ExposureCard key={e.constituent} e={e} />)
          )}
        </Section>
        {modelled ? (
          <ValidationBlock
            validation={catalogue.validation}
            open
            only="compartmental"
          />
        ) : null}
        <References refs={s.references} folded />
      </div>
    </div>
  );
}

function ConstituentRow({
  c,
  refs,
}: {
  c: Constituent;
  refs: SubstanceOut["references"];
}) {
  const t = useT();
  const n = useNum();
  const admet = c.admet ? Object.entries(c.admet) : [];
  return (
    <li className="flex min-w-0 flex-col gap-2" data-testid="tm-constituent">
      <span className="text-lg font-bold">{c.compound}</span>
      <span className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
        {c.pubchem_cid ? (
          <a
            href={`https://pubchem.ncbi.nlm.nih.gov/compound/${encodeURIComponent(c.pubchem_cid)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="mono inline-flex min-h-11 items-center"
          >
            PubChem {c.pubchem_cid}
          </a>
        ) : null}
        {c.wikidata_qid ? (
          <a
            href={`https://www.wikidata.org/wiki/${encodeURIComponent(c.wikidata_qid)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="mono inline-flex min-h-11 items-center"
          >
            Wikidata {c.wikidata_qid}
          </a>
        ) : null}
        {c.molecular_weight !== null ? (
          <span>
            {t("TimeMachine.substance.mw", { mw: n.sig(c.molecular_weight) })}
          </span>
        ) : null}
      </span>
      <p className="text-sm">
        <span className="font-bold">{t("TimeMachine.substance.why")}: </span>
        <span lang="en">{c.why_selected}</span>
      </p>
      {admet.length ? (
        <Disclosure summary={t("TimeMachine.substance.admet")}>
          <div
            className="overflow-x-auto"
            tabIndex={0}
            role="region"
            aria-label={t("TimeMachine.tableRegion")}
          >
            <table className="tm-table">
              <tbody>
                {admet.map(([k, v]) => (
                  <tr key={k}>
                    <th scope="row">
                      {ADMET_NAMED.includes(k)
                        ? t(`TimeMachine.substance.admetNames.${k}`)
                        : t("TimeMachine.substance.admetNames.probability", {
                            name: k,
                          })}
                    </th>
                    <td>
                      {admetUsable(k, v) ? (
                        n.sig(v)
                      ) : (
                        <span>
                          —{" "}
                          <span className="text-muted">
                            (
                            {t(
                              k === "Half_Life_Obach" || k === "VDss_Lombardo"
                                ? "TimeMachine.substance.invalidValue"
                                : "TimeMachine.substance.outOfRange",
                            )}
                            )
                          </span>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Disclosure>
      ) : null}
      {c.measured_activities.length ? (
        <Disclosure summary={t("TimeMachine.substance.activities")}>
          <p className="text-sm font-bold">
            {t("TimeMachine.substance.screening")}
          </p>
          <div
            className="overflow-x-auto"
            tabIndex={0}
            role="region"
            aria-label={t("TimeMachine.tableRegion")}
          >
            <table className="tm-table" data-testid="tm-activities">
              <thead>
                <tr>
                  <th scope="col">{t("TimeMachine.substance.assay")}</th>
                  <th scope="col">{t("TimeMachine.substance.target")}</th>
                  <th scope="col">{t("TimeMachine.substance.measure")}</th>
                  <th scope="col">{t("TimeMachine.substance.value")}</th>
                  <th scope="col">{t("TimeMachine.substance.outcome")}</th>
                  <th scope="col">{t("TimeMachine.substance.depositor")}</th>
                </tr>
              </thead>
              <tbody>
                {c.measured_activities.slice(0, ACTIVITIES_SHOWN).map((a) => (
                  <tr key={`${a.aid}-${a.target}-${a.measure}`}>
                    <td lang="en" className="min-w-[14rem]">
                      {a.assay}{" "}
                      <span className="mono text-xs text-muted">
                        AID {a.aid}
                      </span>
                    </td>
                    <td className="mono">{a.gene ?? a.target ?? "—"}</td>
                    <td>{a.measure}</td>
                    <td>{a.value_um === null ? "—" : n.sig(a.value_um)}</td>
                    <td lang="en">{a.outcome}</td>
                    <td>{a.depositor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-sm text-muted">
            {t("TimeMachine.substance.activitiesCount", {
              shown: Math.min(ACTIVITIES_SHOWN, c.measured_activities.length),
              total: c.measured_activity_count,
            })}
          </p>
        </Disclosure>
      ) : null}
      {c.interaction_flags.length ? (
        <Disclosure
          summary={`${t("TimeMachine.substance.flags")} (${c.interaction_flags.length})`}
        >
          <ul className="flex flex-col gap-2">
            {c.interaction_flags.map((f) => (
              <li
                key={`${f.gene}-${f.pubchem_aid}`}
                className="tile gap-1"
                data-testid="tm-flag"
              >
                <span className="mono font-bold">
                  {f.gene} · {f.measure}
                </span>
                <span className="text-sm">
                  {f.established
                    ? t("TimeMachine.substance.established")
                    : t("TimeMachine.substance.screeningFlag")}
                </span>
                {f.established && f.evidence_reference_key ? (
                  <span className="text-sm" lang="en">
                    {t("TimeMachine.substance.evidence", {
                      citation:
                        refs.find((r) => r.key === f.evidence_reference_key)
                          ?.citation ?? f.evidence_reference_key,
                    })}
                  </span>
                ) : null}
                {f.value_withheld_licence ? (
                  <span className="text-xs text-muted">
                    {f.value_withheld_licence === "unverified"
                      ? t("TimeMachine.substance.withheldUnverified")
                      : t("TimeMachine.substance.withheld", {
                          licence: f.value_withheld_licence,
                        })}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </Disclosure>
      ) : null}
    </li>
  );
}

function ExposureCard({ e }: { e: Exposure }) {
  const t = useT();
  const n = useNum();
  const h = e.historical_dose;
  const model = e.model;
  const notValidated = !e.model_validated
    ? reasonText(t, e.not_validated_reason)
    : null;
  const noPotency = e.comparison ? null : reasonText(t, e.no_potency_reason);
  const note = model ? englishShownFor(model.kind, e.note) : e.note;
  return (
    <article
      className="flex min-w-0 flex-col gap-3"
      data-testid="tm-exposure-card"
    >
      <h3 className="font-body font-bold">{e.constituent}</h3>
      <p className="text-sm">
        {t("TimeMachine.substance.historical", {
          amount: n.sig(h.amount),
          unit: h.unit,
          low: n.sig(h.grams_low),
          high: n.sig(h.grams_high),
        })}
      </p>
      <p className="text-sm">
        {t("TimeMachine.substance.constituentDose", {
          compound: e.constituent,
          low: n.sig(e.constituent_dose_mg.low),
          high: n.sig(e.constituent_dose_mg.high),
          contentLow: n.sig(e.content_percent.low),
          contentHigh: n.sig(e.content_percent.high),
        })}
      </p>
      {model ? (
        <>
          <p className="text-sm font-bold" data-testid="tm-model-label">
            {t(`TimeMachine.method.${model.kind}`)}
          </p>
          <p className="text-sm text-muted">
            {t(`TimeMachine.methodWhy.${model.kind}`)}
          </p>
          <IntervalChart
            testId="tm-peak"
            title={t("TimeMachine.substance.peak", { compound: e.constituent })}
            unit="mg/L"
            axis={logAxis([model.peak_mg_per_l.p5, model.peak_mg_per_l.p95])}
            rows={[
              {
                label: e.constituent,
                low: model.peak_mg_per_l.p5,
                mid: model.peak_mg_per_l.p50,
                high: model.peak_mg_per_l.p95,
              },
            ]}
          />
        </>
      ) : null}
      {notValidated ? (
        <p className="text-sm font-bold" data-testid="tm-not-validated">
          {notValidated}
        </p>
      ) : e.comparison ? (
        <div className="flex flex-col gap-1" data-testid="tm-verdict">
          <p className="text-sm font-bold">
            {t(`TimeMachine.substance.verdict.${e.comparison.verdict}`)}
          </p>
          <p className="text-sm">
            {t(`TimeMachine.substance.basis.${e.comparison.basis}`)}
          </p>
          <p className="text-sm">
            {t("TimeMachine.substance.margin", {
              low: n.sig(e.comparison.margin_low),
              high: n.sig(e.comparison.margin_high),
              measure: e.comparison.potency_measure,
              potency: n.sig(e.comparison.potency_um),
              assay: e.comparison.potency_assay,
            })}
          </p>
        </div>
      ) : noPotency ? (
        <p className="text-sm font-bold" data-testid="tm-no-potency">
          {noPotency}
        </p>
      ) : null}
      {note ? <English>{note}</English> : null}
    </article>
  );
}
