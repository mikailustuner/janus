// Feature: experience, Property P32: the card primitives render their semantics for any labels and
// options (segmented control: a fieldset with a legend and exactly one checked radio of one name;
// disclosure: details > summary with the content in the markup while closed; grouped list: one row
// per child). Property P33: a stat tile shows the figure formatted with Intl and its sentence holds
// the same figure; the figure and label are hidden from assistive technology (Req 29.3–29.7).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { NextIntlClientProvider, useTranslations } from "next-intl";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { formatCount } from "@/components/format";
import { routing } from "@/i18n/routing";
import { check, fc } from "@/test/fc";

vi.mock("@/i18n/navigation", () => ({
  Link: ({
    children,
    href,
    ...rest
  }: {
    children: React.ReactNode;
    href: unknown;
  }) => (
    <a {...rest} data-href={String(href)}>
      {children}
    </a>
  ),
}));

import {
  checkedOption,
  Disclosure,
  GroupedList,
  LargeTitle,
  Row,
  RowLink,
  SegmentedControl,
  StatTile,
  SummaryCard,
} from ".";

const html = (node: React.ReactNode) => renderToStaticMarkup(<>{node}</>);
const text = fc
  .string({ minLength: 1, maxLength: 30 })
  .filter((s) => /^[\p{L}\p{N} ]+$/u.test(s) && s.trim().length > 0);
const escape = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

describe("card primitives (P32)", () => {
  it("segmented control: one fieldset, one legend, exactly one checked radio of one name", () => {
    check(
      fc.property(
        fc.uniqueArray(fc.stringMatching(/^[a-z]{1,8}$/), {
          minLength: 1,
          maxLength: 8,
        }),
        fc.option(fc.stringMatching(/^[a-z]{1,8}$/), { nil: undefined }),
        text,
        fc.constantFrom("segmented" as const, "pills" as const),
        (values, value, legend, variant) => {
          const out = html(
            <SegmentedControl
              legend={legend}
              name="pick"
              options={values.map((v) => ({ value: v, label: `L-${v}` }))}
              value={value}
              onChange={() => {}}
              variant={variant}
            />,
          );
          expect(out.match(/<fieldset/g)).toHaveLength(1);
          expect(out).toContain(`<legend`);
          expect(out).toContain(escape(legend));
          expect(out.match(/type="radio"/g)).toHaveLength(values.length);
          expect(out.match(/name="pick"/g)).toHaveLength(values.length);
          const checked = [...out.matchAll(/<input[^>]*>/g)]
            .map((m) => m[0])
            .filter((tag) => / checked=""/.test(tag));
          expect(checked).toHaveLength(1);
          const want = values.includes(value!) ? value : values[0];
          expect(checked[0]).toContain(`value="${want}"`);
          expect(
            checkedOption(
              values.map((v) => ({ value: v, label: v })),
              value,
            ),
          ).toBe(want);
          for (const v of values) expect(out).toContain(`L-${v}`);
        },
      ),
    );
  });

  it("disclosure: details > summary, content present while closed", () => {
    check(
      fc.property(text, text, fc.boolean(), (summary, body, open) => {
        const out = html(
          <Disclosure summary={summary} defaultOpen={open}>
            <p>{body}</p>
          </Disclosure>,
        );
        expect(out.startsWith("<details")).toBe(true);
        expect(out.includes(' open=""')).toBe(open);
        const s = out.indexOf("<summary");
        expect(s).toBeGreaterThan(-1);
        expect(out.indexOf(escape(summary), s)).toBeGreaterThan(s);
        expect(out.indexOf(`<p>${escape(body)}</p>`)).toBeGreaterThan(
          out.indexOf("</summary>"),
        );
      }),
    );
  });

  it("grouped list: one row per child, header and footer around the list", () => {
    check(
      fc.property(
        fc.array(text, { minLength: 1, maxLength: 12 }),
        text,
        text,
        fc.boolean(),
        (rows, header, footer, plain) => {
          const out = html(
            <GroupedList
              header={header}
              headingId="h"
              footer={footer}
              plain={plain}
            >
              {rows.map((r, i) => (
                <Row key={i}>{r}</Row>
              ))}
              <RowLink href="/x">link</RowLink>
            </GroupedList>,
          );
          expect(out.match(/<li/g)).toHaveLength(rows.length + 1);
          expect(out).toContain(plain ? "grouped-plain" : 'class="grouped"');
          expect(out.indexOf(escape(header))).toBeLessThan(out.indexOf("<ul"));
          expect(out.lastIndexOf(escape(footer))).toBeGreaterThan(
            out.indexOf("</ul>"),
          );
          expect(out).toContain('aria-labelledby="h"');
        },
      ),
    );
  });

  it("large title and summary card: one heading of the asked level", () => {
    const t = html(
      <LargeTitle title="T" summary="S" summaryTestId="sum" eyebrow="E" />,
    );
    expect(t.match(/<h1/g)).toHaveLength(1);
    expect(t).toContain('data-testid="sum"');
    for (const level of [1, 2, 3] as const) {
      const c = html(
        <SummaryCard title="T" id="c" level={level} summary="S">
          <p>body</p>
        </SummaryCard>,
      );
      expect(c).toContain(`<h${level} id="c"`);
      expect(c).toContain('aria-labelledby="c"');
    }
  });
});

const messages = Object.fromEntries(
  routing.locales.map((l) => [
    l,
    JSON.parse(
      readFileSync(
        join(import.meta.dirname, "../../../messages", `${l}.json`),
        "utf8",
      ),
    ),
  ]),
);

function Reports({ count, locale }: { count: number; locale: string }) {
  const t = useTranslations();
  return (
    <StatTile
      value={formatCount(count, locale)}
      label={t("Cards.label.reports", { count })}
      sentence={t("MemoryView.reports", { count })}
    />
  );
}

describe("stat tiles (P33)", () => {
  it("the sentence holds the figure shown; figure and label are aria-hidden", () => {
    check(
      fc.property(
        fc.integer({ min: 1, max: 5_000_000 }),
        fc.constantFrom(...routing.locales),
        (count, locale) => {
          const out = renderToStaticMarkup(
            <NextIntlClientProvider
              locale={locale}
              messages={messages[locale]}
              timeZone="UTC"
            >
              <Reports count={count} locale={locale} />
            </NextIntlClientProvider>,
          );
          const figure = formatCount(count, locale);
          const value =
            /<span aria-hidden="true" class="tile-value">([^<]*)<\/span>/.exec(
              out,
            );
          expect(value?.[1]).toBe(figure);
          expect(out).toMatch(/<span aria-hidden="true" class="tile-label">/);
          const sentence = /<span class="sr-only">([^<]*)<\/span>/.exec(out);
          // ICU and Intl may use a narrow no-break space as the group separator (fr).
          const norm = (s: string) => s.replace(/[  ]/g, " ");
          expect(norm(sentence?.[1] ?? "")).toContain(norm(figure));
        },
      ),
    );
  });
});
