export function formatSavedSearchTime(value: string): string {
  const generatedAt = new Date(value);

  if (Number.isNaN(generatedAt.getTime())) {
    return "time unavailable";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(generatedAt);
}

export function presentSearchFailure(
  message: string,
  preservedSavedResults: boolean
): string {
  if (!preservedSavedResults) {
    return message;
  }

  return `${message} Your previous saved results are still shown.`;
}
