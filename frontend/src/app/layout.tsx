import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mirr'at — The Mirror",
  description: "Proactive ambient AI companion for Haris",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
