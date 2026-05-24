import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

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


export function usePersistedTestDraft({
  testSettings,
  onTestSettingsChange,
}: UsePersistedTestDraftParams): UsePersistedTestDraftResult {
  const [userText, setUserText] = useState(testSettings.user_text);
  const [showDebug, setShowDebug] = useState(testSettings.show_debug);
  const [settingsError, setSettingsError] = useState<string | null>(null);

  useEffect(() => {
    setUserText(testSettings.user_text);
    setShowDebug(testSettings.show_debug);
  }, [testSettings.show_debug, testSettings.user_text]);

  useEffect(() => {
    if (userText === testSettings.user_text && showDebug === testSettings.show_debug) {
      return undefined;
    }

    const timeout = window.setTimeout(() => {
      void onTestSettingsChange({
        ...testSettings,
        user_text: userText,
        show_debug: showDebug,
      }).then(() => {
        setSettingsError(null);
      }).catch((saveError) => {
        setSettingsError(saveError instanceof Error ? saveError.message : "Could not save test settings.");
      });
    }, 250);

    return () => window.clearTimeout(timeout);
  }, [onTestSettingsChange, showDebug, testSettings, userText]);

  return {
    userText,
    setUserText,
    showDebug,
    setShowDebug,
    settingsError,
  };
}