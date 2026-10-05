# Guide: play_by_playback

Operate a media player (play/pause/seek; + at timestamp/quality/subtitle)

## Preconditions

- The browser is on a page containing an audio or video media player.

## Steps

1. Locate the media player interface on the page.
2. If specific playback settings are requested (such as speed, quality, or subtitles), locate and adjust those controls first (e.g., select a speed from a dropdown, toggle subtitles).
3. If a specific starting timestamp is requested, click or drag the progress/seek bar to the target time.
4. Click the play button (often a '▶' icon, a 'Play' button, or the video screen itself) to start playback.

## Watch for

- The play button changing to a pause icon ('❚❚' or similar).
- The current time indicator or progress bar advancing.
- A confirmation message or visual indicator showing the updated speed or setting.

## Pitfalls

- Attempting to seek or change settings before the media player has fully loaded.
- Accidentally clicking outside the progress bar when trying to seek, which might deselect the player or navigate away.

## Variants

- **adjusting playback speed** — Locate the speed selector (often labeled 'Speed', 'Playback Speed', or showing '1.0x'), click it, and select the desired multiplier.
- **seeking to a specific time** — Click along the progress bar timeline or drag the slider handle to the target timestamp before or during playback.
- **the player is embedded in a video container** — Click directly on the video screen area to toggle play/pause.

## Done when

The media player is actively playing with all requested settings (speed, timestamp, subtitles) applied.

_Distilled by gemini-3.5-flash on 2026-09-27 from 11 human demonstrations on train sites only._
