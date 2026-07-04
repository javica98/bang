---
name: Dust & Dithering
colors:
  surface: '#171210'
  surface-dim: '#171210'
  surface-bright: '#3e3835'
  surface-container-lowest: '#120d0b'
  surface-container-low: '#201a18'
  surface-container: '#241e1c'
  surface-container-high: '#2f2926'
  surface-container-highest: '#3a3331'
  on-surface: '#ece0dc'
  on-surface-variant: '#d2c5ac'
  inverse-surface: '#ece0dc'
  inverse-on-surface: '#352f2d'
  outline: '#9b8f78'
  outline-variant: '#4f4633'
  surface-tint: '#f5bf12'
  primary: '#ffeabd'
  on-primary: '#3e2e00'
  primary-container: '#ffc821'
  on-primary-container: '#6f5500'
  inverse-primary: '#765a00'
  secondary: '#f2b9af'
  on-secondary: '#4a2720'
  secondary-container: '#643c35'
  on-secondary-container: '#dfa89e'
  tertiary: '#ffe6e3'
  on-tertiary: '#680008'
  tertiary-container: '#ffc0ba'
  on-tertiary-container: '#b1111b'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdf96'
  primary-fixed-dim: '#f5bf12'
  on-primary-fixed: '#251a00'
  on-primary-fixed-variant: '#594400'
  secondary-fixed: '#ffdad4'
  secondary-fixed-dim: '#f2b9af'
  on-secondary-fixed: '#31120d'
  on-secondary-fixed-variant: '#643c35'
  tertiary-fixed: '#ffdad6'
  tertiary-fixed-dim: '#ffb3ac'
  on-tertiary-fixed: '#410003'
  on-tertiary-fixed-variant: '#930010'
  background: '#171210'
  on-background: '#ece0dc'
  surface-variant: '#3a3331'
typography:
  headline-lg:
    fontFamily: Space Mono
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -1px
  headline-md:
    fontFamily: Space Mono
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  body-lg:
    fontFamily: Courier Prime
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Courier Prime
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-mono:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
  headline-lg-mobile:
    fontFamily: Space Mono
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
spacing:
  pixel-unit: 4px
  gutter: 16px
  margin-sm: 8px
  margin-md: 24px
  panel-padding: 12px
---

## Brand & Style
This design system captures the gritty, adventurous spirit of a 90s-era spaghetti western video game. The brand personality is rugged, nostalgic, and high-stakes, targeting fans of tactical card games and retro aesthetics. 

The design style is **Retro / Pixel-Art Brutalism**. It leans heavily into 16-bit console limitations, utilizing visible dithering patterns to simulate gradients and sharp, non-aliased edges for all UI elements. The emotional response should be one of "digital tactile-ness"—the UI should feel like a physical cartridge game being played on a CRT monitor, evoking the tension of a sunset duel in a dusty desert town.

## Colors
The palette is rooted in the "Golden Hour" of a western frontier, now shifted toward a high-noon brilliance. 
- **Primary (High-Noon Gold):** A bright, saturated yellow-gold (#ffc821) used for critical calls to action, active selection glows, and "BANG!" effects.
- **Secondary (Oxidized Sienna):** A warm, earthy brown (#7a4f47) used for the structural base for containers, menus, and heavy wooden UI elements.
- **Tertiary (Desperado Red):** Reserved for card suits (Hearts/Diamonds) and health depletion.
- **Neutral (Bleached Sand):** Used for typography on dark backgrounds and inactive UI states.
- **Paper Beige:** A specialized color for card faces and "Wanted" poster backgrounds to provide a high-contrast reading surface.

## Typography
The typography relies on fixed-width and geometric technical fonts to simulate the look of pixel-rendered text without sacrificing modern legibility. 

- **Headlines:** Use **Space Mono** for a blocky, impactful feel. It should be used for titles, character names, and game phase announcements (e.g., "DRAW PHASE").
- **Body & Lore:** Use **Courier Prime** for card descriptions and flavor text, mimicking the look of a weathered typewriter.
- **Game Logs & Tech:** Use **JetBrains Mono** for the play-by-play log and technical stats (Range, Life, Distance) to ensure perfect character alignment.

*Note: All text should be rendered with `font-smooth: never` or `image-rendering: pixelated` if possible to maintain the 16-bit aesthetic.*

## Layout & Spacing
The layout follows a **Fixed Grid** system inspired by classic CRT resolutions (scaled for modern displays). The base rhythm is built on 4px "pixel units."

- **Desktop:** The board is centered with the Draw/Discard piles in the middle, Player Hand at the bottom, and Opponents arranged in a horseshoe at the top.
- **Mobile:** A vertical stack. The Hand is docked at the bottom, the Prompt Area sits just above it, and the current target is featured in the center.
- **Gaps:** All containers use a strict 16px gutter. No fluid "flex" spacing is used between cards; they should overlap by fixed increments (e.g., 24px) to mimic a physical hand.

## Elevation & Depth
Depth is created through **Bold Borders** and **Dithered Drop Shadows** rather than blurs or soft gradients.

- **Level 0 (Floor):** Dark background with a horizontal dithered gradient (Oxidized Sienna to Black) representing the saloon floor.
- **Level 1 (Panels):** UI containers use a 2px solid border (#7a4f47) with an internal 1px highlight line on the top and left to simulate a beveled edge.
- **Level 2 (Active Elements):** Buttons and active cards feature a "hard" drop shadow (4px offset, 0px blur) using a 50% opacity black.
- **Focus State:** Active elements are highlighted with a 2px "High-Noon Gold" dashed border to simulate a flickering selection cursor.

## Shapes
In line with the 16-bit aesthetic, all shapes are **strictly sharp (0px)**. 

Curves are "faked" through stair-stepped pixel clusters for specific icons (like hearts or bullets), but all layout containers, buttons, and card frames must maintain 90-degree corners. This reinforces the "low-fidelity" digital construction of the interface.

## Components

- **Buttons:** Chunky, rectangular blocks. Default state has an Oxidized Sienna background with a Sand border. Hover/Active state flips to High-Noon Gold background with Black text. Always include a 1-pixel hard shadow.
- **Character Cards:** Vertical rectangles using the Paper Beige background. The top half contains a 64x64 pixel art portrait framed in an Oxidized Sienna border; the bottom half contains the power description in Courier Prime.
- **Player Panels:** Compact tiles featuring "Wooden Plank" textures. Life points are represented by a row of red pixel-art hearts. Equipment slots (Gun, Mustang) are icons located in a sub-grid on the right side of the panel.
- **Hand Cards:** 
    - *Action Cards:* Brown/Beige borders.
    - *Equipment Cards:* Blue/Steel-grey borders.
    - Overlapping logic: Cards in hand should "fan" slightly, with the focused card popping upward by 20px.
- **Prompt Area:** A full-width horizontal bar at the bottom with a dithered shadow. Instructions are centered in JetBrains Mono, flanked by large "Confirm" or "End Turn" buttons.
- **Life Points (Hearts):** 8-bit style hearts. Empty life points are represented by a dark-sienna "hollow" heart icon.