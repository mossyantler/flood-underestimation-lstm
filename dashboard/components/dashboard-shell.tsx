"use client";
import { useState } from "react";
import { SLUG_TO_ID, type SectionId } from "@/lib/sections";
import { IconRail } from "./icon-rail";
import { ContextSidebar } from "./context-sidebar";
import { MobileTopBar } from "./mobile-topbar";

interface DashboardShellProps {
  slug: string;
  children: React.ReactNode;
}

export function DashboardShell({ slug, children }: DashboardShellProps) {
  const activeId: SectionId = SLUG_TO_ID[slug] ?? "O";
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="dash-shell" data-sidebar={sidebarOpen ? "open" : "closed"}>
      <IconRail
        activeId={activeId}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
      />
      <ContextSidebar activeId={activeId} />
      <div>
        <MobileTopBar activeId={activeId} />
        <main className="canvas" aria-label="분석 대시보드">
          {children}
        </main>
      </div>
    </div>
  );
}
