import { useEffect, useState } from "react";
import { Alert, Button, Group, Loader, Modal, ScrollArea, Stack, Text, TextInput } from "@mantine/core";
import { IconAlertCircle, IconArrowUp, IconCheck, IconFolder } from "@tabler/icons-react";

import { fetchDirectories, type DirectoryListingResponse } from "../api";


type DirectoryPickerModalProps = {
  opened: boolean;
  initialPath: string;
  title?: string;
  onClose: () => void;
  onSelect: (path: string) => void;
};


export function DirectoryPickerModal({
  opened,
  initialPath,
  title = "Choose folder",
  onClose,
  onSelect,
}: DirectoryPickerModalProps) {
  const [currentPath, setCurrentPath] = useState(initialPath || "data");
  const [draftPath, setDraftPath] = useState(initialPath || "data");
  const [listing, setListing] = useState<DirectoryListingResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!opened) {
      return;
    }
    const nextPath = initialPath || "data";
    setCurrentPath(nextPath);
    setDraftPath(nextPath);
  }, [initialPath, opened]);

  useEffect(() => {
    if (!opened) {
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    void fetchDirectories(currentPath)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setListing(payload);
        setDraftPath(payload.path);
      })
      .catch((caught) => {
        if (cancelled) {
          return;
        }
        setListing(null);
        setError(caught instanceof Error ? caught.message : "Could not read directory.");
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [currentPath, opened]);

  function openPath(path: string) {
    const nextPath = path.trim();
    if (nextPath) {
      setCurrentPath(nextPath);
    }
  }

  function selectCurrentPath() {
    onSelect(listing?.path ?? currentPath);
    onClose();
  }

  return (
    <Modal opened={opened} onClose={onClose} title={title} size="lg" centered>
      <Stack>
        <Group align="flex-end" wrap="nowrap">
          <TextInput
            label="Path"
            value={draftPath}
            leftSection={<IconFolder size={16} />}
            onChange={(event) => setDraftPath(event.currentTarget.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                openPath(draftPath);
              }
            }}
            style={{ flex: 1 }}
          />
          <Button variant="default" onClick={() => openPath(draftPath)}>
            Open
          </Button>
        </Group>

        <Group gap={6}>
          <Button size="compact-xs" variant="light" onClick={() => openPath("data")}>data/</Button>
          <Button size="compact-xs" variant="light" onClick={() => openPath(".")}>repo root</Button>
          <Button size="compact-xs" variant="light" onClick={() => openPath("~")}>home</Button>
        </Group>

        {error ? (
          <Alert color="red" icon={<IconAlertCircle size={18} />}>{error}</Alert>
        ) : null}

        <ScrollArea.Autosize mah={320}>
          <Stack gap={6}>
            {listing?.parent_path ? (
              <Button
                variant="subtle"
                justify="flex-start"
                leftSection={<IconArrowUp size={16} />}
                onClick={() => openPath(listing.parent_path || ".")}
              >
                Parent folder
              </Button>
            ) : null}
            {loading ? (
              <Group>
                <Loader size="sm" />
                <Text c="dimmed" size="sm">Reading directories...</Text>
              </Group>
            ) : listing?.entries.length ? (
              listing.entries.map((entry) => (
                <Button
                  key={entry.path}
                  variant="subtle"
                  color="gray"
                  justify="flex-start"
                  leftSection={<IconFolder size={16} />}
                  onClick={() => openPath(entry.path)}
                >
                  {entry.name}
                </Button>
              ))
            ) : (
              <Text c="dimmed" size="sm">No child directories.</Text>
            )}
          </Stack>
        </ScrollArea.Autosize>

        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Cancel</Button>
          <Button leftSection={<IconCheck size={16} />} onClick={selectCurrentPath} disabled={Boolean(error)}>
            Use this folder
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
