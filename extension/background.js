// background.js — service worker for the Chrome extension
// Handles extension lifecycle events

chrome.runtime.onInstalled.addListener(() => {
  console.log("AI Page Assistant installed.");
});
