import type { Metadata } from "next";
import "./globals.css";
import { FundProvider } from "./providers";

export const metadata: Metadata = {
  title: "NiveshDristi — educational research tool",
  description: "Read-only portfolio research over honest, stored data.",
};

export default function RootLayout(
  { children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <FundProvider>{children}</FundProvider>
      </body>
    </html>
  );
}
