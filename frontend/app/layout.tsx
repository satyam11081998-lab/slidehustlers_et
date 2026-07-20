import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KAVACH — Industrial Safety Intelligence",
  description:
    "KAVACH (कवच) — the digital armour for zero-harm industrial operations. Plant digital twin console.",
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
