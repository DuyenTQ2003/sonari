import type { Metadata } from "next";
import type { ReactNode } from "react";
import { t } from "../lib/messages";
import "./globals.css";

export const metadata: Metadata = { title: t("app.title") };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="vi">
      <body className="bg-slate-50 text-slate-900 antialiased">{children}</body>
    </html>
  );
}
