# Cinematics Assets Setup Guide

This file explains how to download and install the external assets required for the enhanced cinematics system.

## Required Assets

The cinematics system requires two external files:

### 1. Special Elite Font (TTF)

**Purpose:** Custom typewriter-style font for cinematics text

**Where to place it:** `/CODIGO/assets/fonts/SpecialElite-Regular.ttf`

**How to download:**

1. Visit: https://fonts.google.com/specimen/Special+Elite
2. Click the **"Download"** button (top-right of the page)
3. A ZIP file will be downloaded
4. Extract the ZIP file
5. Find the file named `SpecialElite-Regular.ttf`
6. Copy it to `/CODIGO/assets/fonts/SpecialElite-Regular.ttf`

**Verification:**
```bash
ls -la "CODIGO/assets/fonts/SpecialElite-Regular.ttf"
# Should return the file with size ~50 KB
```

**Fallback behavior:** If the font file is not found, the system will automatically fall back to using a system font (Arial).

---

### 2. Typewriter Click Sound Effect (OGG)

**Purpose:** Sound effect played when letters appear in the typewriter effect

**Where to place it:** `/CODIGO/assets/sounds/typewriter_click.ogg`

**How to download (Option A - Recommended):**

1. Visit: https://www.zapsplat.com/music/typewriter-key-click-1/
2. Click **"Download File"** button
3. Save the file as `typewriter_click.ogg` to `/CODIGO/assets/sounds/`
4. If the file is `.mp3`, convert it to `.ogg` (see conversion instructions below)

**How to download (Option B - Alternative):**

1. Visit: https://freesound.org/people/Schratt/sounds/434261/
2. Create a free account (if needed)
3. Click **"Download"** button
4. The file will be `typewriter_key_clicked.ogg`
5. Rename it to `typewriter_click.ogg` and place in `/CODIGO/assets/sounds/`

**Convert MP3 to OGG (if needed):**

Using FFmpeg (install from https://ffmpeg.org/download.html):

```bash
ffmpeg -i typewriter_click.mp3 -c:a libvorbis -q:a 5 typewriter_click.ogg
```

Or using Audacity:
1. Open Audacity (https://www.audacityteam.org/)
2. File > Import Audio
3. Select the MP3 file
4. File > Export > Export As... > Format: "OGG Vorbis Files"
5. Save as `typewriter_click.ogg`

**Verification:**
```bash
ls -la "CODIGO/assets/sounds/typewriter_click.ogg"
# Should return a file with size ~10-50 KB
```

**Fallback behavior:** If the sound file is not found, the typewriter effect will work silently (no click sounds).

---

## Configuration

The system configuration is stored in:

**File:** `/CODIGO/narrative/cutscene_config.json`

You can customize various parameters without code changes:

```json
{
  "text_style": {
    "font_path": "assets/fonts/SpecialElite-Regular.ttf",  // TTF file location
    "font_size": 24,                                        // Text size in pixels
    "typewriter_fps": 30,                                   // Letters per second
    "max_width_ratio": 0.75,                                // Max text width (% of screen)
    "bottom_margin_ratio": 0.15,                            // Distance from bottom (% of screen)
    "line_height_multiplier": 1.3                           // Space between lines
  },
  "text_box": {
    "color": [0, 0, 0],                                     // Band color (RGB)
    "alpha": 220,                                           // Transparency (0-255)
    "min_height_px": 120,                                   // Minimum band height
    "edge_irregularity": 8,                                 // Jagged edge intensity
    "padding_top": 15,                                      // Top padding
    "padding_bottom": 15,                                   // Bottom padding
    "padding_left": 30,                                     // Left padding
    "padding_right": 30                                     // Right padding
  },
  "typewriter_sound": {
    "path": "assets/sounds/typewriter_click.ogg",           // OGG file location
    "volume": 0.4                                           // Volume (0.0-1.0)
  }
}
```

---

## Testing the Installation

After placing both files, run the game and:

1. Start the game (you should see the intro cinematic play)
2. Watch for text appearing letter-by-letter at the bottom of the screen
3. Listen for click sounds as letters appear
4. Press ESC to skip the cinematic

If you see text appearing but no sounds, the font was likely found but the sound file wasn't - that's fine, the system works in silent mode.

---

## Troubleshooting

### "Font file not found" message in logs
- Verify the path is exactly: `/CODIGO/assets/fonts/SpecialElite-Regular.ttf`
- Check that the file extension is `.ttf` (not `.otf` or other format)
- The system will fall back to Arial automatically

### No typewriter sound effect
- Verify the path is exactly: `/CODIGO/assets/sounds/typewriter_click.ogg`
- Check that the file format is `.ogg` (not `.mp3` or `.wav`)
- Use FFmpeg to convert if needed
- The system will continue working silently if the file is missing

### Text appears at wrong position
- Check `cutscene_config.json` settings:
  - `bottom_margin_ratio`: Should be 0.15 (15% from bottom)
  - `max_width_ratio`: Should be 0.75 (75% of screen width)
- Adjust these values to fine-tune positioning

### Irregular band edges are too subtle/too jagged
- Edit `cutscene_config.json`:
  - Decrease `edge_irregularity` (e.g., 5) for smoother edges
  - Increase `edge_irregularity` (e.g., 12) for more jagged effect

---

## File Checklist

- [ ] `/CODIGO/assets/fonts/SpecialElite-Regular.ttf` exists
- [ ] `/CODIGO/assets/sounds/typewriter_click.ogg` exists
- [ ] `/CODIGO/narrative/cutscene_config.json` exists
- [ ] `/CODIGO/narrative/text_renderer.py` exists
- [ ] `/CODIGO/narrative/text_box.py` exists
- [ ] `/CODIGO/narrative/cinematics.py` has been updated

Once all files are in place, the enhanced cinematics system is ready to use!
