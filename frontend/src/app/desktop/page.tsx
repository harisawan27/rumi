import type { Metadata } from "next";
import DesktopPreview from "@/components/desktop/DesktopPreview";

export const metadata: Metadata = { title: "Rumi — Your space, in flow", description: "Explore Rumi’s desktop experience. An interactive preview with no cloud AI calls." };
export default function DesktopPage() { return <DesktopPreview />; }
