/**
 * The doctor note PDF, rendered in the browser (experience design §10.2, DP6, Req 17.7–17.10).
 * Light face; Fraunces, Atkinson Hyperlegible Next and IBM Plex Mono embedded from /fonts (Noto Sans
 * as the last fallback for letters the text fonts lack); A4 or US Letter; on every page a footer
 * with the disclaimer, the demo label when demo, the versions and "page n of m". Real, selectable
 * text. Loaded only when "Download PDF" is pressed (a lazy chunk).
 */
import {
  Document,
  Font,
  Page,
  pdf,
  StyleSheet,
  Text,
  View,
} from "@react-pdf/renderer";

import type { LaidBlock, LaidDocument, NoteLayout } from "./layout";

// Light-face tokens (.kiro/steering/design.md); the PDF has no CSS variables.
const C = {
  bg: "#FFFFFF",
  fg: "#1B1F3B",
  muted: "#4E5170",
  line: "#DDD5C4",
  accent: "#1E6B62",
  warn: "#7A4D00",
};
const FALLBACK = ["PlexMono", "NotoFallback"];

let registered = false;
function registerFonts(origin: string) {
  if (registered) return;
  const f = (file: string) => `${origin}/fonts/${file}`;
  Font.register({
    family: "Atkinson",
    fonts: [
      { src: f("AtkinsonHyperlegibleNext-Regular.ttf"), fontWeight: 400 },
      { src: f("AtkinsonHyperlegibleNext-Bold.ttf"), fontWeight: 700 },
    ],
  });
  Font.register({
    family: "Fraunces",
    src: f("Fraunces-SemiBold.ttf"),
    fontWeight: 600,
  });
  Font.register({ family: "PlexMono", src: f("IBMPlexMono-Regular.ttf") });
  Font.register({ family: "NotoFallback", src: f("NotoSans-Fallback.ttf") });
  // Never split words with a hyphen the note did not contain (the text is verbatim).
  Font.registerHyphenationCallback((word) => [word]);
  registered = true;
}

const s = StyleSheet.create({
  page: {
    paddingTop: 40,
    paddingBottom: 72,
    paddingHorizontal: 44,
    fontFamily: ["Atkinson", ...FALLBACK],
    fontSize: 10,
    lineHeight: 1.45,
    color: C.fg,
    backgroundColor: C.bg,
  },
  title: {
    fontFamily: ["Fraunces", "Atkinson", ...FALLBACK],
    fontSize: 17,
    fontWeight: 600,
    marginBottom: 6,
  },
  demo: {
    fontWeight: 700,
    fontSize: 9,
    color: C.accent,
    marginBottom: 6,
    textTransform: "uppercase",
  },
  heading: {
    fontFamily: ["Fraunces", "Atkinson", ...FALLBACK],
    fontSize: 12.5,
    fontWeight: 600,
    marginTop: 12,
    marginBottom: 4,
  },
  sentence: { marginBottom: 4 },
  row: {
    borderTopWidth: 1,
    borderTopColor: C.line,
    paddingTop: 4,
    marginBottom: 4,
  },
  bold: { fontWeight: 700 },
  mono: { fontFamily: ["PlexMono", "NotoFallback"], fontSize: 9 },
  muted: { color: C.muted },
  warn: { color: C.warn, fontWeight: 700 },
  footer: {
    position: "absolute",
    left: 44,
    right: 44,
    bottom: 24,
    fontSize: 8,
    color: C.muted,
    borderTopWidth: 1,
    borderTopColor: C.line,
    paddingTop: 4,
  },
});

function Block({ b }: { b: LaidBlock }) {
  if (b.kind === "sentence") return <Text style={s.sentence}>{b.text}</Text>;
  if (b.kind === "stat")
    return (
      <View style={s.row} wrap={false}>
        {b.sentences.map((x) => (
          <Text key={x.id} style={s.sentence}>
            {x.text}
          </Text>
        ))}
        {b.pts ? <Text style={[s.sentence, s.muted]}>{b.pts}</Text> : null}
      </View>
    );
  return (
    <View style={s.row} wrap={false}>
      <Text>
        <Text style={s.muted}>{b.productLabel}: </Text>
        <Text style={s.bold}>{b.productName ?? "—"}</Text>
      </Text>
      {b.ingredients.map((i) => (
        <Text key={i.key}>
          {i.name ?? i.key}
          {i.tag ? <Text style={s.muted}> ({i.tag})</Text> : null}
          {i.atc.length ? (
            <Text style={s.mono}> {i.atc.join(", ")}</Text>
          ) : null}
          {i.combinationCode ? (
            <Text style={s.muted}> ({i.combinationCode})</Text>
          ) : null}
        </Text>
      ))}
      {b.notChecked.map((n) => (
        <Text key={n} style={s.muted}>
          {n}
        </Text>
      ))}
      <Text style={s.muted}>{b.started}</Text>
      {b.abruptStop ? <Text style={s.warn}>{b.abruptStop}</Text> : null}
    </View>
  );
}

export interface PdfLabels {
  demo: string | null;
  pageOf: (page: number, pages: number) => string;
  versions: string;
}

function NotePages({
  doc,
  labels,
  size,
}: {
  doc: LaidDocument;
  labels: PdfLabels;
  size: "A4" | "LETTER";
}) {
  return (
    <Page size={size} style={s.page} wrap>
      {labels.demo ? (
        <Text style={s.demo} fixed>
          {labels.demo}
        </Text>
      ) : null}
      {doc.sections.map((sec) => (
        <View key={sec.id}>
          {sec.id === "header" ? (
            <Text style={s.title}>{sec.heading}</Text>
          ) : sec.heading ? (
            <Text style={s.heading} minPresenceAhead={40}>
              {sec.heading}
            </Text>
          ) : null}
          {sec.blocks.map((b) => (
            <Block key={b.id} b={b} />
          ))}
        </View>
      ))}
      <View style={s.footer} fixed>
        <Text>{doc.disclaimer}</Text>
        {labels.demo ? <Text style={s.bold}>{labels.demo}</Text> : null}
        <Text
          render={({ pageNumber, totalPages }) =>
            `${labels.versions} · ${labels.pageOf(pageNumber, totalPages)}`
          }
        />
      </View>
    </Page>
  );
}

/** Renders the doctor's document (the first one) to a PDF blob. */
export async function renderNotePdf(
  layout: NoteLayout,
  labels: PdfLabels,
  size: "A4" | "LETTER",
  origin: string,
): Promise<Blob> {
  registerFonts(origin);
  const doc = layout.documents[0]!;
  const file = (
    <Document
      title={doc.title ?? "Janus"}
      language={doc.language}
      author="Janus"
      creator="Janus"
      producer="Janus"
    >
      <NotePages doc={doc} labels={labels} size={size} />
    </Document>
  );
  return pdf(file).toBlob();
}
