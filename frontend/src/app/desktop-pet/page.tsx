import type { Metadata } from "next";
import DesktopPet from "@/components/desktop/DesktopPet";

export const metadata: Metadata = { title: "Rumi desktop pet" };

export default function DesktopPetPage() {
  return <DesktopPet />;
}
