import type { ReactNode } from "react";
import { NavLink as RouterNavLink, useLocation } from "react-router-dom";
import {
  AppShell as MantineAppShell,
  Box,
  Button,
  Group,
  Text,
  Title,
} from "@mantine/core";


export interface AppShellNavItem {
  to: string;
  label: string;
  description: string;
  icon: ReactNode;
}


export interface AppShellProps {
  navItems: AppShellNavItem[];
  workspaceToolbar?: ReactNode;
  children?: ReactNode;
}


function isActiveRoute(pathname: string, target: string): boolean {
  if (target === "/") {
    return pathname === "/";
  }
  return pathname.startsWith(target);
}


export function AppShell({ navItems, workspaceToolbar, children }: AppShellProps) {
  const location = useLocation();

  return (
    <MantineAppShell
      header={{ height: 76 }}
      padding="lg"
      className="shell-main"
    >
      <MantineAppShell.Header withBorder>
        <Group h="100%" px="lg" justify="space-between" wrap="nowrap" gap="md">
          <Group gap="sm" wrap="nowrap" miw={170}>
            <span className="app-logo">PX</span>
            <Box>
              <Title order={4} lh={1.05}>Proton-X</Title>
              <Text size="xs" c="dimmed">Tiny router workbench</Text>
            </Box>
          </Group>

          <Box className="top-nav">
            <Group gap={4} wrap="nowrap">
              {navItems.map((item) => {
                const active = isActiveRoute(location.pathname, item.to);
                return (
                  <Button
                    key={item.to}
                    component={RouterNavLink}
                    to={item.to}
                    variant={active ? "light" : "subtle"}
                    color={active ? "indigo" : "gray"}
                    leftSection={item.icon}
                    size="sm"
                  >
                    {item.label}
                  </Button>
                );
              })}
            </Group>
          </Box>

          <Box className="workspace-toolbar-slot">
            {workspaceToolbar}
          </Box>
        </Group>
      </MantineAppShell.Header>

      <MantineAppShell.Main>
        <Box className="content-shell">
          {children}
        </Box>
      </MantineAppShell.Main>
    </MantineAppShell>
  );
}
