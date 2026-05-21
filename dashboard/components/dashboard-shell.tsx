"use client";
import { useState } from "react";
import { SLUG_TO_ID, type SectionId, type SectionSlug } from "@/lib/sections";
import { IconRail } from "./icon-rail";
import { ContextSidebar } from "./context-sidebar";
import { MobileTopBar } from "./mobile-topbar";

interface DashboardShellProps {
  slug: string;
  activeEntrySlug?: string;
  children: React.ReactNode;
}

export function DashboardShell({ slug, activeEntrySlug, children }: DashboardShellProps) {
  const activeId: SectionId = SLUG_TO_ID[slug as SectionSlug] ?? "O";
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="dash-shell" data-sidebar={sidebarOpen ? "open" : "closed"}>
      <IconRail
        activeId={activeId}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
      />
      <ContextSidebar activeId={activeId} activeEntrySlug={activeEntrySlug} />
      <div>
        <MobileTopBar activeId={activeId} />
        <main className="canvas" aria-label="분석 대시보드">
          {children}
        </main>
      </div>
    </div>
  );
}
