import type { Metadata } from "next";
import NativeDesktop from "@/components/desktop/NativeDesktop";
export const metadata: Metadata = { title: "Rumi Desktop — Local control" };
export default function NativeDesktopPage() { return <NativeDesktop />; }
