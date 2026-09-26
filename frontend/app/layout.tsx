import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import { Navigation } from "@/components/navigation";
import "./globals.css";
export const metadata: Metadata = {
  title: "ThesisLens — Evidence over conviction",
  description:
    "Follow great investors. Understand what they own. Verify each idea yourself.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-3 focus:text-primary-foreground"
        >
          Skip to content
        </a>
        <Providers>
          <Navigation />
          <main id="main">{children}</main>
        </Providers>
        <footer className="mx-auto mt-14 flex max-w-[1200px] flex-col gap-2 border-t border-border/70 px-4 py-7 text-xs muted sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <span>ThesisLens · Evidence over conviction.</span>
          <span>
            Public disclosures are research inputs, not personalized advice.
          </span>
        </footer>
      </body>
    </html>
  );
}
