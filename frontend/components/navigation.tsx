"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Activity, Moon, ScanSearch, Sun } from "lucide-react";

const primaryItems = [
  { label: "Home", href: "/", paths: ["/"] },
  {
    label: "Explore",
    href: "/explore",
    paths: ["/explore", "/discover", "/research"],
  },
  {
    label: "Intelligence",
    href: "/intelligence",
    paths: ["/intelligence", "/market-pulse"],
  },
  { label: "Ask AI", href: "/ask", paths: ["/ask"] },
];

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
      <div className="site-header-inner mx-auto flex max-w-[1200px] items-center justify-between gap-3 px-4 py-3 sm:px-8">
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
          className="primary-nav min-w-0 rounded-xl border border-border/60 bg-card/45 p-1"
        >
          {primaryItems.map((item) => {
            const active = item.paths.some((path) =>
              path === "/" ? pathname === "/" : pathname.startsWith(path),
            );
            return (
            <Link
              key={item.label}
              className="nav-link"
              aria-current={active ? "page" : undefined}
              href={item.href}
            >
              {item.label}
            </Link>
            );
          })}
        </nav>
        <div className="header-actions flex shrink-0 items-center gap-2">
          <Link
            href="/status"
            aria-label="System status and settings"
            title="System status and settings"
            aria-current={pathname.startsWith("/status") ? "page" : undefined}
            className="header-icon-button"
          >
            <Activity size={17} aria-hidden />
          </Link>
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={light ? "Switch to dark mode" : "Switch to light mode"}
            className="header-icon-button"
          >
            {light ? (
              <Moon size={17} aria-hidden />
            ) : (
              <Sun size={17} aria-hidden />
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
