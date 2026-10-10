"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Moon, ScanSearch, Sun } from "lucide-react";
export function Navigation() {
  const pathname = usePathname();
  const [light, setLight] = useState(false);
  useEffect(() => {
    const saved = window.localStorage.getItem("thesislens-theme");
    const enabled = saved === "light";
    setLight(enabled);
    document.documentElement.dataset.theme = enabled ? "light" : "dark";
  }, []);
  function toggleTheme() {
    const next = !light;
    setLight(next);
    document.documentElement.dataset.theme = next ? "light" : "dark";
    window.localStorage.setItem("thesislens-theme", next ? "light" : "dark");
  }
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/88 backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1200px] items-center justify-between gap-3 px-4 py-3 sm:px-8">
        <Link
          href="/"
          className="flex items-center gap-2.5 text-lg font-semibold tracking-tight"
        >
          <span className="icon-shell !h-9 !w-9 !rounded-xl">
            <ScanSearch size={19} aria-hidden />
          </span>
          <span className="hidden min-[430px]:inline">ThesisLens</span>
        </Link>
        <nav
          aria-label="Main navigation"
          className="flex min-w-0 items-center overflow-x-auto rounded-xl border border-border/60 bg-card/45 p-1"
        >
          <Link
            className="nav-link"
            aria-current={pathname === "/" ? "page" : undefined}
            href="/"
          >
            Home
          </Link>
          {[
            ["Discover", "/discover"],
            ["Research", "/research"],
            ["Market Pulse", "/market-pulse"],
            ["Ask", "/ask"],
            ["Status", "/status"],
          ].map(([x, href]) => (
            <Link
              key={x}
              className="nav-link"
              aria-current={pathname.startsWith(href) ? "page" : undefined}
              href={href}
            >
              {x}
            </Link>
          ))}
        </nav>
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={light ? "Switch to dark mode" : "Switch to light mode"}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-card text-primary transition hover:bg-accent"
        >
          {light ? <Moon size={17} aria-hidden /> : <Sun size={17} aria-hidden />}
        </button>
      </div>
    </header>
  );
}
