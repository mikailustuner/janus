"use client";
/**
 * Read aloud (Req 3.2, DP14): off by default; when on and the browser has a voice for the
 * interface language, reads only the finding's text through the Web Speech API. Nothing is sent.
 */
import { useLocale } from "next-intl";
import { useEffect, useState } from "react";

import { useSettings } from "@/store/hooks";
import { useT } from "@/theme/words";

import { SpeakerIcon } from "./icons";
import { Button } from "./ui";

export function ReadAloud({ text }: { text: () => string }) {
  const t = useT();
  const locale = useLocale();
  const { value } = useSettings();
  const [voice, setVoice] = useState<SpeechSynthesisVoice | null>(null);
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => {
    if (!value.readAloud || typeof speechSynthesis === "undefined") return;
    const pick = () =>
      setVoice(
        speechSynthesis
          .getVoices()
          // Only a voice of this device: a network voice would send the text to a speech service
          // (safety audit B2). Without one, the control is hidden.
          .find(
            (v) => v.localService && v.lang.toLowerCase().startsWith(locale),
          ) ?? null,
      );
    pick();
    speechSynthesis.addEventListener("voiceschanged", pick);
    return () => speechSynthesis.removeEventListener("voiceschanged", pick);
  }, [value.readAloud, locale]);
  if (!value.readAloud || !voice) return null;
  return (
    <Button
      variant="secondary"
      className="self-start"
      aria-pressed={speaking}
      onClick={() => {
        if (speaking) {
          speechSynthesis.cancel();
          setSpeaking(false);
          return;
        }
        const u = new SpeechSynthesisUtterance(text());
        u.voice = voice;
        u.lang = voice.lang;
        u.onend = () => setSpeaking(false);
        speechSynthesis.speak(u);
        setSpeaking(true);
      }}
    >
      <SpeakerIcon size={20} />
      {speaking ? t("ReadAloud.stop") : t("ReadAloud.read")}
    </Button>
  );
}
