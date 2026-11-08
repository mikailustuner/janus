"use client";
import type { UserRegion } from "@/api/contracts";
import { PATIENT_FACTS } from "@/demo/patients";
import { useDemo } from "@/demo/session";
import { useSettings } from "@/store/hooks";

/** The user region for emergency and crisis numbers: the demo patient's, else the setting. */
export function useUserRegion(): UserRegion {
  const demo = useDemo();
  const { value } = useSettings();
  return demo ? PATIENT_FACTS[demo].userRegion : value.userRegion;
}
