import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";

import type { WorkspaceTestSettings } from "./api";


type UsePersistedTestDraftParams = {
  testSettings: WorkspaceTestSettings;
  onTestSettingsChange: (next: WorkspaceTestSettings) => Promise<void>;
};


type UsePersistedTestDraftResult = {
  userText: string;
  setUserText: Dispatch<SetStateAction<string>>;
  showDebug: boolean;
  setShowDebug: Dispatch<SetStateAction<boolean>>;
  settingsError: string | null;
};

const SAVE_DEBOUNCE_MS = 600;


function sameTestSettings(left: WorkspaceTestSettings, right: WorkspaceTestSettings): boolean {
  return left.user_text === right.user_text && left.show_debug === right.show_debug;
}


export function usePersistedTestDraft({
  testSettings,
  onTestSettingsChange,
}: UsePersistedTestDraftParams): UsePersistedTestDraftResult {
  const [userText, setUserText] = useState(testSettings.user_text);
  const [showDebug, setShowDebug] = useState(testSettings.show_debug);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const latestDraftRef = useRef<WorkspaceTestSettings>(testSettings);
  const hasLocalChangesRef = useRef(false);
  const pendingSaveCountRef = useRef(0);
  const saveVersionRef = useRef(0);
  const onTestSettingsChangeRef = useRef(onTestSettingsChange);

  useEffect(() => {
    onTestSettingsChangeRef.current = onTestSettingsChange;
  }, [onTestSettingsChange]);

  const updateUserText: Dispatch<SetStateAction<string>> = (nextValue) => {
    hasLocalChangesRef.current = true;
    setUserText((previousValue) => {
      const value = typeof nextValue === "function" ? nextValue(previousValue) : nextValue;
      latestDraftRef.current = {
        ...latestDraftRef.current,
        user_text: value,
      };
      return value;
    });
  };

  const updateShowDebug: Dispatch<SetStateAction<boolean>> = (nextValue) => {
    hasLocalChangesRef.current = true;
    setShowDebug((previousValue) => {
      const value = typeof nextValue === "function" ? nextValue(previousValue) : nextValue;
      latestDraftRef.current = {
        ...latestDraftRef.current,
        show_debug: value,
      };
      return value;
    });
  };

  useEffect(() => {
    if (hasLocalChangesRef.current || pendingSaveCountRef.current > 0) {
      return;
    }

    latestDraftRef.current = testSettings;
    setUserText(testSettings.user_text);
    setShowDebug(testSettings.show_debug);
  }, [testSettings.show_debug, testSettings.user_text]);

  useEffect(() => {
    const draft = {
      user_text: userText,
      show_debug: showDebug,
    };
    latestDraftRef.current = draft;

    if (sameTestSettings(draft, testSettings)) {
      hasLocalChangesRef.current = false;
      return undefined;
    }

    hasLocalChangesRef.current = true;
    const timeout = window.setTimeout(() => {
      const payload = latestDraftRef.current;
      const saveVersion = saveVersionRef.current + 1;
      saveVersionRef.current = saveVersion;
      pendingSaveCountRef.current += 1;

      void onTestSettingsChangeRef.current(payload)
        .then(() => {
          if (saveVersion === saveVersionRef.current && sameTestSettings(latestDraftRef.current, payload)) {
            hasLocalChangesRef.current = false;
          }
          setSettingsError(null);
        })
        .catch((saveError) => {
          if (sameTestSettings(latestDraftRef.current, payload)) {
            setSettingsError(saveError instanceof Error ? saveError.message : "Could not save test settings.");
          }
        })
        .finally(() => {
          pendingSaveCountRef.current -= 1;
        });
    }, SAVE_DEBOUNCE_MS);

    return () => window.clearTimeout(timeout);
  }, [showDebug, testSettings.show_debug, testSettings.user_text, userText]);

  return {
    userText,
    setUserText: updateUserText,
    showDebug,
    setShowDebug: updateShowDebug,
    settingsError,
  };
}
