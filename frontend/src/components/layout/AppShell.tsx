import React from "react";
import { DesktopShell, type DesktopShellAction } from "@/components/layout/DesktopShell";

type ShellAction = DesktopShellAction;

type AppShellProps = {
  title?: string;
  hideHeaderTitle?: boolean;
  actions?: ShellAction[];
  showBack?: boolean;
  backHref?: string;
  backLabel?: string;
  children: React.ReactNode;
  contentClassName?: string;
};

export function AppShell({
  title,
  hideHeaderTitle,
  actions,
  showBack,
  backHref,
  backLabel,
  children,
  contentClassName,
}: AppShellProps) {
  return (
    <DesktopShell
      title={title}
      hideHeaderTitle={hideHeaderTitle}
      actions={actions}
      showBack={showBack}
      backHref={backHref}
      backLabel={backLabel}
      contentClassName={contentClassName}
    >
        {children}
    </DesktopShell>
  );
}
