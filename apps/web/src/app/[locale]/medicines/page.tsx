import { noIndex } from "@/seo/metadata";
import { Medicines } from "@/components/medicines/Medicines";

export const metadata = noIndex;

export default function MedicinesPage() {
  return <Medicines />;
}
