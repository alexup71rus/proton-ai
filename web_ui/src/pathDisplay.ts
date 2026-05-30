const REPO_PATH_MARKERS = [
  "/proton-ai/",
  "/proton-x/", // Legacy local folder name used before the public rename.
];


export function compactWorkspacePath(path: string | undefined, fallback = ""): string {
  if (!path) {
    return fallback;
  }
  for (const marker of REPO_PATH_MARKERS) {
    const markerIndex = path.indexOf(marker);
    if (markerIndex >= 0) {
      return path.slice(markerIndex + marker.length);
    }
  }
  return path;
}
