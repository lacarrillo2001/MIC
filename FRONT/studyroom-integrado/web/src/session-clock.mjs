export function secondsRemaining(start, minutes, now = Date.now()) {
  if (start === null) return minutes * 60;
  return Math.max(0, Math.ceil((start + minutes * 60000 - now) / 1000));
}
