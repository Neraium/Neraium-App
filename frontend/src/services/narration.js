/**
 * Narration system for demo — plays audio on state transitions.
 * Uses Web Speech API (browser native, no external files needed).
 */

const NARRATION_LINES = {
  STABLE: {
    text: "System operating normally. Baseline established and stable.",
    confidence: 0.95,
  },
  TRANSITION: {
    text: "Structural departure detected. System exhibiting measurable baseline deviation. Monitoring intensifies.",
    confidence: 0.65,
  },
  UNSTABLE: {
    text: "Instability confirmed. Degradation accelerating. Intervention window opening. Plan now.",
    confidence: 0.85,
  },
  LOCK_IN: {
    text: "Critical threshold locked in. Degradation irreversible. Execute contingency procedures immediately.",
    confidence: 0.92,
  },
};

let speechSynthesis = null;
let currentUtterance = null;
let lastPlayedState = null;
let narrationEnabled = true;

// Track which states have already had narration played in this session
const statesNarrated = new Set();

export function initNarration() {
  if (typeof window !== "undefined" && window.speechSynthesis) {
    speechSynthesis = window.speechSynthesis;
  }
}

export function setNarrationEnabled(enabled) {
  narrationEnabled = enabled;
  if (!enabled && currentUtterance) {
    speechSynthesis?.cancel();
    currentUtterance = null;
  }
}

export function getNarrationEnabled() {
  return narrationEnabled;
}

export function playNarration(state, confidenceLevel = null) {
  if (!narrationEnabled || !speechSynthesis) return;

  // Don't repeat the exact same state immediately
  if (lastPlayedState === state) return;

  // Get the narration for this state
  const narration = NARRATION_LINES[state];
  if (!narration) return;

  // Cancel any ongoing narration
  speechSynthesis.cancel();

  // Create utterance
  currentUtterance = new SpeechSynthesisUtterance(narration.text);
  currentUtterance.rate = 0.95; // Slightly slower for clarity
  currentUtterance.pitch = 1.0;
  currentUtterance.volume = 0.8;

  // Add end handler
  currentUtterance.onend = () => {
    currentUtterance = null;
    lastPlayedState = state;
    statesNarrated.add(state);
  };

  currentUtterance.onerror = () => {
    currentUtterance = null;
  };

  // Play
  speechSynthesis.speak(currentUtterance);
}

export function getNarrationText(state) {
  return NARRATION_LINES[state]?.text || "";
}

export function hasNarrationPlayed(state) {
  return statesNarrated.has(state);
}

export function resetNarrationSession() {
  statesNarrated.clear();
  lastPlayedState = null;
  speechSynthesis?.cancel();
  currentUtterance = null;
}

export function isNarratingNow() {
  return currentUtterance !== null && speechSynthesis?.speaking;
}
