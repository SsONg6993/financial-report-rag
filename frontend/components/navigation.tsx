"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ScanSearch } from "lucide-react";
export function Navigation() {
  const pathname = usePathname();
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
          className="flex items-center overflow-x-auto rounded-xl border border-border/60 bg-card/45 p-1"
        >
          <Link
            className="nav-link"
            aria-current={pathname === "/" ? "page" : undefined}
            href="/"
          >
            Home
          </Link>
          {["Discover", "Research", "Ask"].map((x) => (
            <Link
              key={x}
              className="nav-link"
              aria-current={
                pathname.startsWith("/" + x.toLowerCase()) ? "page" : undefined
              }
              href={"/" + x.toLowerCase()}
            >
              {x}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
