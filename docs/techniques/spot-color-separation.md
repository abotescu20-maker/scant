---
tags: [technique, print]
scanart_style_ids: [risograph]
period: "1986-present"
source: "modern"
---

# Spot Color Separation

## Technique

The Risograph does not mix inks on the fly: each drum is loaded with one pre-mixed spot colour — Federal Blue, Fluorescent Pink, Yellow, Mint, Red, Black, and roughly twenty others. To produce a multi-colour print, the artwork must be *separated* into one greyscale channel per ink drum, with each channel representing how much of that specific colour prints at each pixel.

Typical separation workflow:
1. decide the palette (commonly 2–4 spot colours on off-white stock)
2. in software, split the design into one greyscale layer per colour, with white = no ink and black = full ink
3. rasterise tones into halftone dots (see [[halftone-moire]]) so the Riso master can physically reproduce them
4. print each layer on a separate pass, reloading the paper between drums
5. where two colours overlap, their semi-transparent soy inks multiply to produce a third colour — pink + blue yields purple, yellow + blue yields greenish teal

This additive / multiplicative behaviour is central to Riso's look: artists design not only the separations but the overlaps, treating a two-colour Riso print as visually three-colour or four-colour.

## Practitioners

- Risotto Studio (Glasgow)
- [[tom-froese|Tom Froese]]
- Colorama (Berlin)
- Hato Press (London)

## ScanArt mapping

Applicable ScanArt styles: `risograph`

## Relations

- [[risograph|Risograph]]
- [[stencil-master]]
- [[halftone-moire]]
- [[registration-misalignment]]

## Sources

- Risotto Studio, "Preparing files for Riso printing"
- Colorama, printer guide
- Perfectly Acceptable Press, artist resources
