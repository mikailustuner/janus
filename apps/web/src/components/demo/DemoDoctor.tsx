"use client";
/**
 * The demo doctor page (Req 4.7, 19.7): the recorded form of the demo patient on a paper card,
 * with the demo label; it sends nothing.
 */
import { useEffect, useState } from "react";

import type { OutcomeFormOut } from "@/api/contracts";
import * as D from "@/api/decode";
import { StateView } from "@/components/StateView";
import { loadFixture } from "@/demo/client";
import { useDemo } from "@/demo/session";
import { DoctorForm } from "@/doctor/DoctorForm";
import { DOCTOR_MESSAGES } from "@/doctor/messages";

export function DemoDoctor() {
  const demo = useDemo() ?? "istanbul";
  const [form, setForm] = useState<OutcomeFormOut | null>(null);
  useEffect(() => {
    let live = true;
    loadFixture(demo).then((f) => {
      const r = D.decode(D.outcomeFormOut, f.doctorForm);
      if (live && r.ok) setForm(r.value);
    });
    return () => {
      live = false;
    };
  }, [demo]);
  if (!form) return <StateView state="loading" />;
  return (
    <DoctorForm
      form={form}
      m={DOCTOR_MESSAGES[form.language]}
      demo
      onSend={null}
    />
  );
}
