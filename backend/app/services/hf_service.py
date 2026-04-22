"""
Tier FREE: Gemini 2.0 Flash native image generation → PIL/NumPy animation.
30 filtre artistice. 6 animation modes (Auto, Blink, Steam, Wind, Glisten, Light).
Gemini generates the artistic transformation directly (understands art + subject).
PIL style transfer as fallback. MediaPipe FaceMesh for blink.
GIF 400x400px, 16 frame-uri, 80ms/frame.
"""
import asyncio
import io
import math
import random
import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageFont
import google.generativeai as genai
from app.config import settings

N_FRAMES = 16  # Optimized: 16 frames × 80ms = 1.28s playback (was 24 × 60ms = 1.44s)

# ─── Style Anchor System (ArcReel-inspired consistency) ──────────────────────
# Two layers:
#   1. Text memory: previous artwork descriptions → anti-repetition
#   2. Visual anchor: first generated image → style reference for Imagen
# Key: "session_id:style_id"
_style_memory: dict[str, list[str]] = {}
_style_anchors: dict[str, bytes] = {}  # stores JPEG bytes of first generation

def _remember_style(session_id: str, style_id: str, description: str):
    """Store an artwork description for future reference."""
    key = f"{session_id}:{style_id}"
    if key not in _style_memory:
        _style_memory[key] = []
    _style_memory[key].append(description[:200])
    if len(_style_memory[key]) > 5:
        _style_memory[key] = _style_memory[key][-5:]

def _recall_style(session_id: str, style_id: str) -> str:
    """Get gentle variation hint from previous generations (not a hard constraint)."""
    key = f"{session_id}:{style_id}"
    history = _style_memory.get(key, [])
    if not history:
        return ""
    prev = " | ".join(history[-2:])  # only last 2 (was 3)
    return f"""VARIATION HINT:
Previous versions explored: {prev}
Try a fresh creative angle — if possible, explore a different mood or palette than these, but prioritize artistic richness and authentic technique over forced variation."""

def _save_style_anchor(session_id: str, style_id: str, img: Image.Image):
    """Save first generated image as visual style anchor (ArcReel pattern)."""
    key = f"{session_id}:{style_id}"
    if key not in _style_anchors:
        buf = io.BytesIO()
        img.resize((256, 256), Image.LANCZOS).save(buf, format="JPEG", quality=80)
        _style_anchors[key] = buf.getvalue()
        print(f"Style anchor SAVED for {key} ({len(_style_anchors[key])}B)")

def _get_style_anchor(session_id: str, style_id: str) -> bytes | None:
    """Get visual style anchor for consistency."""
    key = f"{session_id}:{style_id}"
    anchor = _style_anchors.get(key)
    if anchor:
        print(f"Style anchor FOUND for {key}")
    return anchor


# ─── Mapare filtru → direcție artistică pentru Gemini ────────────────────────
STYLE_ARTISTIC_DIRECTION = {
    "warhol":   "Andy Warhol Factory silkscreen print TECHNIQUE applied to the subject: posterize into flat CMYK color separations, Ben-Day halftone dots, bold graphic reduction, 2x2 repeat grid with different color shifts per quadrant, commercial art aesthetic",
    "hokusai":  "Edo-period ukiyo-e woodblock print TECHNIQUE applied to the subject: bold ink outlines, flat color washes in Prussian blue and vermilion, bokashi gradation, rice-paper grain texture",
    "klimt":    "Gustav Klimt Vienna Secession TECHNIQUE applied to the subject: gold leaf mosaic patterns on surfaces, ornate geometric borders, rich jewel tones, decorative Byzantine-inspired details",
    "ghibli":   "Studio Ghibli hand-drawn cel animation TECHNIQUE applied to the subject: soft watercolor washes, clean crisp ink outlines, warm gentle ambient lighting, botanical background detail",
    "banksy":   "Banksy urban stencil spray-paint TECHNIQUE applied to the subject: high contrast black and white stencil reduction, spray feathering at edges, single bold accent color element, raw wall texture background",
    "dali":     "Salvador Dali paranoid-critical TECHNIQUE applied to the subject: hyperrealistic oil paint precision but with impossible physics — solid objects acquire soft draping weight, subtle scale violations, calm uncanny atmosphere",
    "vangogh":  "Vincent van Gogh impasto TECHNIQUE applied to the subject: thick directional brushstrokes covering every surface, pure color juxtaposition without blending, visible paint ridge texture, heightened complementary colors",
    "baroque":  "Dutch Golden Age chiaroscuro TECHNIQUE applied to the subject: single strong directional light from one side, deep warm shadows on the other, sfumato transitions, restricted earth tone palette with lead white highlights",
    "mondrian": "Piet Mondrian De Stijl neoplastic TECHNIQUE applied to the subject: decompose into flat orthogonal grid of rectangles, bold black dividing lines, fill with primary colors (red, blue, yellow) and neutrals only, no curves or diagonals",
    "mucha":    "Alphonse Mucha Art Nouveau poster TECHNIQUE applied to the subject: sinuous fluid ink lines, botanical halo frame, flat outlined shapes, muted pastel palette on aged cream ground, ornamental border panels",
    # 20 new styles
    "meiji_print":    "Meiji-era shin-hanga woodblock print: delicate bokashi gradation, confident ink contour lines, washi paper fibre texture, indigo-to-pale tonal transitions",
    "persian_mini":   "Safavid Persian miniature: frontal presentation without perspective, no cast shadows, compressed space, lapis lazuli and vermilion pigments, gold leaf background, botanical margin illumination",
    "mughal_mini":    "Mughal imperial miniature: fine parallel hatching for volume, atmospheric sky gradation, rich naturalistic detail, ornate floral borders, jewel-tone palette",
    "byzantine":      "Byzantine mosaic: decompose into individual tessera tiles of gold smalti and colored glass, visible gaps between tiles, hieratic frontal presentation, radiant gold background",
    "preraphaelite":  "Pre-Raphaelite wet white ground oil: jewel-saturated luminous color at maximum intensity, scientific botanical detail, flowing hair and drapery, medieval romantic atmosphere",
    "expressionism":  "German Expressionist Die Brücke: distorted anatomy, anti-naturalistic psychologically motivated color, visible knife strokes, angular compositions, raw emotional tension",
    "futurism":       "Italian Futurist simultaneity: overlapping stroboscopic ghost images of motion, radiating lines of force, diagonal composition, fragmented forms suggesting speed",
    "constructivism": "Soviet Constructivist design: strict geometric composition in cadmium red, black and white only, 45-degree diagonal axes, photomontage elements, propaganda poster aesthetic",
    "swiss_poster":   "Swiss International Typographic Style: strict modular grid, halftone photography, maximum two spot colors plus black, clean sans-serif typography, asymmetric layout",
    "pointillism":    "Seurat's chromoluminarist technique: pure unmixed pigment dots of consistent size, optical color mixing at viewing distance, luminous light through complementary dot placement",
    "risograph":      "Risograph duplicator aesthetic: two or three flat spot-color channels with imperfect registration, halftone moiré patterns, grain noise from stencil master, fluorescent inks",
    "woodcut":        "Hand-carved woodcut relief: binary black ink and white paper only, tonal zones resolved through parallel line hatching, visible gouge marks showing carving direction",
    "ligne_claire":   "Hergé ligne claire: uniform unwavering ink line of identical weight everywhere, flat unmodulated color fills, no hatching or crosshatching, clean precise outlines",
    "daguerreotype":  "1840s daguerreotype: silver-grey tonal palette only, metallic specular halation on highlights, mirror-like plate reflectivity, brass mat frame border, no warm sepia",
    "infrared":       "Kodak Aerochrome false-color infrared: foliage becomes brilliant white/gold, sky renders deep black, shadows in deep magenta/crimson, dreamlike surreal atmosphere",
    "lomography":     "LC-A Lomo camera aesthetic: heavy corner vignetting toward black, cross-processed shifted colors, oversaturated mid-tones, light leak streaks in warm orange/magenta",
    "cyberpunk":      "Cyberpunk neon-noir: deep indigo-black environment lit only by neon sources in electric magenta, cyan and hot pink, holographic UI overlays, rain-slicked reflective surfaces",
    "brutalist":      "Brutalist design: raw board-formed concrete texture, blunt oversized typography, minimal color palette of concrete grey with single accent, heavy shadow, industrial materiality",
    "wpa_poster":     "American WPA federal silkscreen poster: maximum six flat spot colors, bold heroic silhouettes, deliberate simplification, monumental staging, patriotic warm palette",
    "zine_collage":   "DIY punk zine collage: torn paper fragments with ragged edges, visible tape/glue marks, photocopier degradation, hand-lettered text, lo-fi black and white with accent color",
}

# Gradient colors pentru preview filtre (start, end)
STYLE_GRADIENTS = {
    "warhol":       ("#ff0080", "#ffff00"),
    "hokusai":      ("#0066cc", "#00ccff"),
    "klimt":        ("#b8860b", "#ffd700"),
    "ghibli":       ("#2d8a4e", "#87ceeb"),
    "banksy":       ("#1a1a1a", "#555555"),
    "dali":         ("#c8a060", "#f0e070"),
    "vangogh":      ("#1a3a6b", "#f4a900"),
    "baroque":      ("#1a0a00", "#8b4513"),
    "mondrian":     ("#cc0000", "#0033cc"),
    "mucha":        ("#d4a0b0", "#f5e0c0"),
    # 20 new styles
    "meiji_print":    ("#2c3e6b", "#7eb8c9"),
    "persian_mini":   ("#1a3a8f", "#c8a040"),
    "mughal_mini":    ("#2e4a2e", "#d4a060"),
    "byzantine":      ("#8b6914", "#ffd700"),
    "preraphaelite":  ("#2e5a1e", "#c07070"),
    "expressionism":  ("#8b0000", "#ff6600"),
    "futurism":       ("#333366", "#ff4444"),
    "constructivism": ("#cc0000", "#1a1a1a"),
    "swiss_poster":   ("#e60000", "#ffffff"),
    "pointillism":    ("#4488cc", "#88cc44"),
    "risograph":      ("#ff3399", "#ffcc00"),
    "woodcut":        ("#1a1a1a", "#8b4513"),
    "ligne_claire":   ("#3399ff", "#ffcc33"),
    "daguerreotype":  ("#666666", "#cccccc"),
    "infrared":       ("#ff0066", "#ffffff"),
    "lomography":     ("#ff6600", "#006666"),
    "cyberpunk":      ("#ff00ff", "#00ffff"),
    "brutalist":      ("#555555", "#999999"),
    "wpa_poster":     ("#cc3300", "#336699"),
    "zine_collage":   ("#ff3399", "#1a1a1a"),
}

# ─── Style-specific variations (5 per style) — for diversity on repeated generations
STYLE_VARIATIONS = {
    "warhol": [
        "increase Ben-Day dot density, make halftone screen more prominent across all surfaces",
        "shift palette to cooler tones: cyan, electric violet, cobalt blue, acid green",
        "heavier posterization — reduce to only 3 tonal levels per channel for maximum graphic impact",
        "warm palette variant: coral pink, butter yellow, tangerine orange, lime green quadrants",
        "maximum graphic reduction — near-silhouette with bold flat color fills, minimal detail",
    ],
    "hokusai": [
        "stronger Prussian blue dominance — deep indigo sky, ultramarine ocean tones throughout",
        "emphasize bokashi gradation — visible wet pigment bleed creating soft tonal transitions",
        "subject's ink outlines have stronger brush pressure variation — thick to thin in one stroke",
        "focus on vermilion and crimson accents against cool muted indigo ground",
        "thicker more confident ink outlines — bold Edo-period brushwork with visible pressure variation",
    ],
    "klimt": [
        "maximize gold leaf coverage — every non-subject surface covered in tessellated gold mosaic",
        "emphasize Byzantine spiral patterns within the decorative zones",
        "jewel-tone variant: deep emerald, sapphire blue, and ruby red against gold ground",
        "add intricate geometric border frame with Egyptian-inspired eye motifs",
        "softer palette: rose gold, champagne, ivory with subtle mosaic pattern overlay",
    ],
    "ghibli": [
        "add more atmospheric clouds and sky — soft cumulus with warm golden backlighting",
        "increase botanical frame density — more leaves, vines, and small flowers surrounding subject",
        "warmer sunset palette: amber, peach, soft rose, golden hour lighting",
        "cooler forest palette: moss green, misty blue, dappled sunlight through canopy",
        "softer watercolor edges on the subject — paint bleeds outward from its contours",
    ],
    "banksy": [
        "rougher wall texture — crumbling concrete with visible aggregate and water stains",
        "more spray overspray visible — paint particles feathering beyond the stencil edges of the subject",
        "red accent variant: bright crimson as the single pop of color against B&W stencil",
        "clean white wall variant — fresh stencil on pristine surface, minimal wall texture",
        "multi-layer stencil: add a subtle grey mid-tone layer between black and white",
    ],
    "dali": [
        "exaggerate the melting effect — surfaces drape and drip with impossible fluidity",
        "add impossible shadow cast at wrong angle — two light sources contradicting each other",
        "introduce subtle scale violation — one element disproportionately large or small",
        "desert landscape variant — place the subject on an infinite flat plain under vast sky",
        "hyperrealistic water reflection beneath the subject that shows a different reality",
    ],
    "vangogh": [
        "longer sweeping brushstrokes — each stroke visible as a thick impasto ridge with shadow",
        "starry night palette: ultramarine, cobalt, cadmium yellow against deep blue night",
        "harvest palette: golden ochre, raw sienna, viridian green, warm afternoon light",
        "tighter concentric brush loops around the subject creating energy vortex",
        "maximum paint texture — visible bristle marks, heavy impasto creating 3D surface relief",
    ],
    "baroque": [
        "single candle source from left — extreme chiaroscuro with 90% of image in warm shadow",
        "window light variant — cool blue-white light from right, warm umber shadows on left",
        "visible craquelure aging across the entire painted surface — fine web of cracks",
        "rich vermilion accent on one element against otherwise earth-tone restricted palette",
        "sfumato edges on all shadow transitions — no hard lines, everything dissolves into darkness",
    ],
    "mondrian": [
        "dominant red variant — largest rectangle is cadmium red, smaller blue and yellow accents",
        "balanced composition — roughly equal areas of white, red, blue, yellow, with thick black grid",
        "minimal variant — mostly white and grey rectangles with one small red and one blue accent",
        "bold black grid — lines twice the normal weight creating a heavier structural presence",
        "asymmetric variant — all colored rectangles pushed to one corner, rest is white grid",
    ],
    "mucha": [
        "elaborate botanical halo — roses, lilies, and ivy forming a circular frame around subject",
        "add ornamental border panels at top and bottom with geometric-floral hybrid patterns",
        "warm rose and gold palette on aged cream ground — Art Nouveau at its most decorative",
        "cooler sage and lilac palette — muted pastels with silver-grey ink outlines",
        "subject's outlines become more undulating and fluid — maximum Art Nouveau sinuosity",
    ],
    "meiji_print": [
        "stronger bokashi bleed — pigment transitions from deep indigo to pale sky more visible",
        "subject rendered with more visible woodblock registration marks at edges",
        "muted twilight palette: soft rose, dusky blue, ivory, pale gold — evening atmosphere",
        "emphasize washi paper grain — visible fibre texture under translucent ink layers",
        "bolder ink contours — confident single-stroke outlines with visible brush pressure",
    ],
    "persian_mini": [
        "maximize gold leaf illumination — thick gold borders with lapis lazuli blue panels",
        "gold leaf illumination more prominent directly on the subject's surfaces",
        "jewel pigment variant: intense vermilion, malachite green, lapis blue at full saturation",
        "frontal flat presentation — reject all perspective cues, every element at most recognizable angle",
        "add calligraphic cartouche element in one corner — decorative text-like frame",
    ],
    "mughal_mini": [
        "fine parallel hatching for all volume — delicate crosshatch shading technique",
        "finer hatching density on the subject's volume — more delicate crosshatch shading",
        "rich sky gradation — atmospheric deep blue at top fading to golden horizon",
        "emphasize naturalistic botanical detail — every leaf and petal precisely rendered",
        "add decorative gold-painted margin with flowering vine motifs",
    ],
    "byzantine": [
        "maximize gold smalti tessera coverage — entire background in shimmering gold mosaic",
        "add dark border frame with repeated geometric pattern — typical Byzantine arch format",
        "rich jewel-tone tessera: deep ruby, sapphire, emerald set against gold ground",
        "larger tessera tiles — each individual square clearly visible with gaps between them",
        "hieratic frontal presentation — subject faces viewer directly with solemn formality",
    ],
    "preraphaelite": [
        "maximum chromatic intensity — jewel colors at full saturation on wet white ground",
        "add botanical detail: ivy, wildflowers, ferns rendered with scientific precision",
        "medieval romantic atmosphere — soft golden light as through stained glass",
        "rich flowing drapery around or near the subject — luxurious fabric folds",
        "luminous sky background — pale gold and rose as in early Italian painting",
    ],
    "expressionism": [
        "more angular distortion — space tilts and compresses around the subject",
        "anti-naturalistic color: acid green, blood red, electric orange — psychological tension",
        "visible palette knife marks — thick aggressive strokes with sharp edges",
        "woodcut variant: reduce to stark black and white with minimal color accent",
        "maximum emotional intensity — colors clash violently, forms twist with inner energy",
    ],
    "futurism": [
        "more stroboscopic ghost images — 5-6 overlapping positions of the subject",
        "stronger radiating force lines emanating from the center of composition",
        "metallic palette: chrome silver, gunmetal grey, with bright velocity lines",
        "diagonal composition pushed to extreme — 45-degree tilt on everything",
        "add typography element — fragmented letters suggesting speed and modernity",
    ],
    "constructivism": [
        "pure red, black, and white only — no other colors permitted, maximum contrast",
        "add photomontage cut-out effect — subject appears as collaged photograph element",
        "dominant diagonal at 45 degrees — every element oriented on the dynamic axis",
        "bold Cyrillic-style typography element — blocky letters as compositional weight",
        "circular variant — subject inscribed in a bold geometric circle on black ground",
    ],
    "swiss_poster": [
        "strict 6-column modular grid — all elements snap precisely to invisible guides",
        "60-line halftone screen applied to photography — visible dot pattern throughout",
        "red and black only — Helvetica-like clean typography element integrated into composition",
        "asymmetric layout pushed to left — subject occupies 2/3 with white space on right",
        "add sans-serif text element as compositional anchor — clean typographic grid",
    ],
    "pointillism": [
        "larger dots in perfectly regular rows and columns — each pigment point clearly visible and methodically placed",
        "strict complementary pairing: every orange dot has a blue neighbor, every green has a red neighbor",
        "luminous sunlit palette — cadmium yellow and white dots dominate, viridian and cobalt accents in shadows",
        "cooler palette: cobalt blue, ultramarine violet, and cerulean dots creating shadowy atmospheric depth",
        "maximum dot density on strict grid — zero canvas visible, every position filled with a pure pigment dot",
    ],
    "risograph": [
        "fluorescent pink and teal two-channel separation with heavy misregistration offset",
        "three-channel variant: fluorescent yellow, pink, and blue with moiré interference",
        "heavy grain noise from stencil master — gritty lo-fi texture across all ink layers",
        "maximum misregistration — channels shifted 5-8 pixels creating ghostly double images",
        "school-bus yellow and electric blue only — bold two-color Riso print on cream paper",
    ],
    "woodcut": [
        "finer parallel hatching lines — dense crosshatch creating rich tonal gradation",
        "bold graphic variant — minimal lines, maximum contrast between carved and uncarved",
        "visible gouge marks — directional carving texture following the form of the subject",
        "add wood grain texture visible in the printed surface — natural material showing through",
        "reverse variant — white lines on black (inked background, carved out highlights)",
    ],
    "ligne_claire": [
        "perfectly uniform line weight everywhere — foreground and background identical stroke width",
        "flat primary color fills — bright red, blue, yellow with no shading or gradients",
        "add clear shadow shapes — flat grey shadows with sharp edges, no soft gradients",
        "pastel palette variant — softer muted colors but maintaining perfectly clean outlines",
        "add background environment with same clean line treatment — buildings, sky, or interior",
    ],
    "daguerreotype": [
        "stronger metallic halation bloom on highlights — silver plate specular reflection",
        "add brass mat frame border with ornate corner details — period-authentic presentation",
        "deeper blacks — rich tonal range from brilliant silver to absolute black",
        "mirror-like plate surface — subtle reflective quality shifts across the tonal range",
        "add fine scratches and age marks — period-authentic surface wear on silver plate",
    ],
    "infrared": [
        "brilliant white foliage variant — all vegetation rendered as pure white or pale gold",
        "deep magenta shadows — infrared film's characteristic crimson in dark areas",
        "maximum false-color contrast — stark white vegetation against near-black sky",
        "subtle dreamlike variant — softer false-color shift with pastel pink and gold tones",
        "add visible film grain and light halation at bright edges — analogue film character",
    ],
    "lomography": [
        "extreme vignetting — corners nearly black, bright oversaturated center",
        "warm orange-magenta light leak streak across the upper portion of the frame",
        "cross-process color shift: greens become cyan, reds become orange-pink throughout",
        "double exposure ghost — faint overlay of a second shifted image for dreamy effect",
        "maximum oversaturation — mid-tones pushed to vivid color, crushed blacks in corners",
    ],
    "cyberpunk": [
        "more rain — heavy rainfall with neon reflections on wet surfaces everywhere",
        "dominant magenta neon — electric pink as the primary light source color",
        "add holographic HUD overlay elements — translucent data readouts and targeting reticles",
        "cyan and orange contrast — teal neon against warm sodium vapor highlights",
        "add visible scan-lines and digital glitch artifacts — CRT monitor aesthetic overlay",
    ],
    "brutalist": [
        "maximum raw concrete texture — board-formed surface with visible wood grain impression",
        "single orange accent against otherwise grey concrete palette — industrial safety color",
        "heavy geometric shadow — harsh directional light creating bold angular shadows on concrete",
        "add blunt oversized typography element — bold sans-serif occupying aggressive space",
        "weathered variant — concrete staining, water marks, industrial patina on all surfaces",
    ],
    "wpa_poster": [
        "patriotic warm palette: deep navy, barn red, cream, golden ochre — 1930s Americana",
        "bold heroic silhouette — subject reduced to simplified monumental form against sky",
        "maximum flat color — 4 spot colors only with no gradients, each a distinct ink layer",
        "add serif typography element — WPA-era letterforms as compositional anchor",
        "cool mountain palette: forest green, sky blue, snow white, granite grey — national park poster",
    ],
    "zine_collage": [
        "more torn paper fragments — ragged edges with visible cardboard layers beneath",
        "add hand-lettered punk text: scratchy marker words scattered across composition",
        "heavy photocopier degradation — multiple generation copy artifacts, faded and gritty",
        "add visible tape and glue marks — transparent tape strips holding fragments together",
        "maximum lo-fi: barely legible through photocopy noise, extreme black and white contrast",
    ],
}

# ─── Style-specific composition: HOW the subject is transformed (not what to add around it)
STYLE_COMPOSITION = {
    "warhol": "The subject itself is posterized into flat CMYK separations. Arrange as 2x2 grid — same subject, 4 different color palettes. The subject IS the pop art.",
    "hokusai": "The subject itself is rendered as if carved in a woodblock — bold ink outlines define its form, flat color washes fill its surfaces, bokashi gradation on its edges. No wave, no Mount Fuji — the subject IS the ukiyo-e print.",
    "klimt": "The subject's surface itself becomes gold mosaic tessera — its form built from geometric tiles and spirals. Gold leaf is ON the subject, not around it.",
    "ghibli": "The subject itself is painted with soft watercolor washes and clean cel-animation outlines. Warm golden light falls directly ON the subject.",
    "banksy": "The subject itself is reduced to a high-contrast stencil — its forms simplified to black and white with spray-paint feathering at edges. Concrete texture shows THROUGH the subject.",
    "dali": "The subject itself acquires impossible physics — its solid surfaces drape and melt with photorealistic precision. The subject deforms, the technique is ON the subject.",
    "vangogh": "The subject itself is built from thick impasto brushstrokes — every surface of the subject has visible paint ridges, directional strokes following its contours.",
    "baroque": "A single light source illuminates the subject from one side — deep warm shadow on the other. The subject has oil-paint texture and sfumato edges.",
    "mondrian": "The subject's form is decomposed into orthogonal rectangles — its shapes abstracted into primary color blocks separated by bold black lines.",
    "mucha": "The subject's outline becomes sinuous Art Nouveau curves — its edges flow and undulate. Flat decorative fills inside the subject's form.",
    "meiji_print": "The subject is rendered with delicate ink contours and bokashi color gradation — pigment bleeds softly across its surfaces on visible washi paper texture.",
    "persian_mini": "The subject is presented frontally with no perspective — flat lapis and vermilion pigments fill its forms. Gold leaf illumination on its surfaces.",
    "mughal_mini": "The subject is rendered with fine parallel hatching strokes for volume — naturalistic detail on its surfaces, jewel-tone palette.",
    "byzantine": "The subject is built from individual mosaic tessera tiles — gold smalti and colored glass compose its form with visible gaps between tiles.",
    "preraphaelite": "The subject glows with jewel-saturated pigment on wet white ground — every surface luminous at maximum chromatic intensity.",
    "expressionism": "The subject's form is distorted with angular tension — anti-naturalistic colors, visible knife strokes across its surfaces, space warps around it.",
    "futurism": "The subject appears in multiple overlapping positions — stroboscopic ghost images of itself. Force lines radiate from the subject outward.",
    "constructivism": "The subject is reduced to strict geometric shapes in red, black, and white — its form decomposed into 45-degree diagonal elements.",
    "swiss_poster": "The subject is treated with halftone photography — visible dot screen, clean sans-serif label, strict grid alignment. Maximum two spot colors.",
    "pointillism": "The subject is rendered entirely from small, UNIFORMLY SIZED pure-pigment dots arranged in a STRICT REGULAR GRID. Each dot is a single unmixed color from Seurat's palette (cadmium red, chrome orange, cadmium yellow, viridian, cobalt blue, ultramarine violet). Adjacent dots are COMPLEMENTARY colors for OPTICAL mixing. Brighter areas = yellow + white dots, shadows = violet + blue dots. Methodically placed in rows and columns — scientific color theory, NOT random splatter.",
    "risograph": "The subject is printed in 2-3 misregistered spot-color channels — its form splits into overlapping color separations with halftone moiré.",
    "woodcut": "The subject exists only as carved relief — black ink where wood remains, white where the gouge removed material. Hatching lines follow the subject's form.",
    "ligne_claire": "The subject has perfectly uniform ink outlines and flat color fills — no variation in line weight, clean precise edges, no gradients.",
    "daguerreotype": "The subject is rendered in silver-grey tones on a reflective plate — metallic halation blooms on its brightest edges.",
    "infrared": "The subject undergoes false-color transformation — organic materials become white/gold, shadows shift to deep magenta.",
    "lomography": "The subject is oversaturated with cross-processed color shift — heavy vignette darkens around it, warm light leak crosses over it.",
    "cyberpunk": "The subject is lit only by neon — electric magenta, cyan, hot pink sources cast colored light and reflections directly ON the subject's surfaces.",
    "brutalist": "The subject is rendered in raw concrete materiality — board-formed texture on its surfaces, monumental weight, industrial shadow.",
    "wpa_poster": "The subject is simplified into a bold heroic silhouette — flat spot colors, deliberate reduction, monumental dignity.",
    "zine_collage": "The subject is assembled from torn paper fragments — its form cut and pasted from different sources, visible tape at joins, photocopier grain.",
}


# ─── Style Tags + Semantic Matching (Wiki-first, RAG-ready) ──────────────────
# Each style has tags for: mood, material affinity, color profile, subject fit.
# Used for smart style suggestion based on photo content analysis.
# When we scale to 100+ styles, swap keyword match for vector similarity.
STYLE_TAGS = {
    "warhol":         {"mood": ["fun", "bold", "ironic", "commercial"], "materials": ["plastic", "metal", "packaging", "consumer"], "colors": ["bright", "neon", "cmyk", "saturated"], "subjects": ["face", "object", "food", "text", "number", "sign"]},
    "hokusai":        {"mood": ["calm", "contemplative", "nature"], "materials": ["wood", "paper", "fabric", "natural"], "colors": ["blue", "indigo", "muted", "earth"], "subjects": ["plant", "animal", "object", "number"]},
    "klimt":          {"mood": ["luxurious", "ornate", "romantic"], "materials": ["gold", "metal", "jewelry", "ceramic"], "colors": ["gold", "jewel", "warm", "rich"], "subjects": ["face", "object", "cup", "plant"]},
    "ghibli":         {"mood": ["warm", "gentle", "nostalgic", "magical"], "materials": ["organic", "wood", "ceramic", "fabric"], "colors": ["pastel", "warm", "soft", "natural"], "subjects": ["animal", "plant", "food", "face", "object"]},
    "banksy":         {"mood": ["provocative", "urban", "political", "raw"], "materials": ["concrete", "brick", "metal", "industrial"], "colors": ["bw", "monochrome", "red_accent"], "subjects": ["face", "sign", "text", "object", "number"]},
    "dali":           {"mood": ["surreal", "dreamlike", "unsettling", "philosophical"], "materials": ["organic", "soft", "liquid", "melting"], "colors": ["earth", "desert", "warm", "hyperreal"], "subjects": ["object", "face", "food", "cup", "animal"]},
    "vangogh":        {"mood": ["passionate", "emotional", "turbulent", "alive"], "materials": ["canvas", "paint", "organic", "natural"], "colors": ["complementary", "vibrant", "blue_yellow", "warm"], "subjects": ["plant", "object", "face", "food", "animal"]},
    "baroque":        {"mood": ["dramatic", "solemn", "intimate", "mysterious"], "materials": ["oil", "canvas", "velvet", "dark_wood"], "colors": ["dark", "earth", "chiaroscuro", "warm"], "subjects": ["face", "cup", "food", "object", "animal"]},
    "mondrian":       {"mood": ["structured", "minimal", "geometric", "clean"], "materials": ["flat", "graphic", "paper", "architectural"], "colors": ["primary", "red_blue_yellow", "bold"], "subjects": ["object", "sign", "text", "number"]},
    "mucha":          {"mood": ["decorative", "elegant", "flowing", "botanical"], "materials": ["paper", "print", "organic", "floral"], "colors": ["pastel", "cream", "muted", "rose"], "subjects": ["face", "plant", "cup", "food"]},
    "meiji_print":    {"mood": ["delicate", "atmospheric", "contemplative"], "materials": ["paper", "ink", "wood", "fabric"], "colors": ["muted", "indigo", "rose", "ivory"], "subjects": ["plant", "animal", "object", "number"]},
    "persian_mini":   {"mood": ["ornate", "sacred", "precious", "flat"], "materials": ["gold", "pigment", "stone", "ceramic"], "colors": ["jewel", "lapis", "vermilion", "gold"], "subjects": ["face", "animal", "plant", "object"]},
    "mughal_mini":    {"mood": ["refined", "naturalistic", "imperial"], "materials": ["paper", "pigment", "silk", "organic"], "colors": ["jewel", "green", "gold", "earth"], "subjects": ["animal", "plant", "face", "object"]},
    "byzantine":      {"mood": ["sacred", "solemn", "radiant", "eternal"], "materials": ["gold", "glass", "stone", "mosaic"], "colors": ["gold", "jewel", "ruby", "sapphire"], "subjects": ["face", "object", "cup", "sign"]},
    "preraphaelite":  {"mood": ["romantic", "luminous", "medieval", "botanical"], "materials": ["oil", "jewel", "organic", "fabric"], "colors": ["saturated", "jewel", "green", "red"], "subjects": ["face", "plant", "animal", "cup"]},
    "expressionism":  {"mood": ["anxious", "raw", "emotional", "distorted"], "materials": ["paint", "woodcut", "rough", "angular"], "colors": ["anti_natural", "acid", "harsh", "contrast"], "subjects": ["face", "object", "animal", "sign"]},
    "futurism":       {"mood": ["dynamic", "speed", "mechanical", "modern"], "materials": ["metal", "machine", "glass", "chrome"], "colors": ["metallic", "bright", "fragmented"], "subjects": ["object", "face", "number", "sign"]},
    "constructivism": {"mood": ["political", "geometric", "bold", "propaganda"], "materials": ["paper", "metal", "industrial", "graphic"], "colors": ["red_black_white", "minimal", "stark"], "subjects": ["text", "sign", "number", "face", "object"]},
    "swiss_poster":   {"mood": ["clean", "systematic", "modern", "functional"], "materials": ["paper", "print", "halftone", "graphic"], "colors": ["limited", "spot_color", "clean"], "subjects": ["text", "sign", "number", "object", "face"]},
    "pointillism":    {"mood": ["luminous", "scientific", "shimmering", "outdoor"], "materials": ["canvas", "pigment", "paint", "natural"], "colors": ["pure", "complementary", "bright", "optical"], "subjects": ["plant", "face", "animal", "food", "object"]},
    "risograph":      {"mood": ["indie", "lo-fi", "playful", "zine"], "materials": ["paper", "ink", "print", "stencil"], "colors": ["fluorescent", "misregistered", "limited"], "subjects": ["text", "sign", "object", "face", "number"]},
    "woodcut":        {"mood": ["stark", "medieval", "graphic", "primal"], "materials": ["wood", "ink", "paper", "carved"], "colors": ["bw", "binary", "stark"], "subjects": ["face", "animal", "plant", "object", "number"]},
    "ligne_claire":   {"mood": ["clean", "comic", "precise", "flat"], "materials": ["ink", "paper", "print", "graphic"], "colors": ["flat", "primary", "clean", "bright"], "subjects": ["face", "object", "animal", "sign", "number"]},
    "daguerreotype":  {"mood": ["antique", "precious", "ghostly", "formal"], "materials": ["metal", "silver", "glass", "mirror"], "colors": ["silver", "grey", "monochrome", "metallic"], "subjects": ["face", "object", "cup", "sign"]},
    "infrared":       {"mood": ["surreal", "dreamlike", "otherworldly", "alien"], "materials": ["organic", "foliage", "film", "natural"], "colors": ["false_color", "white", "magenta", "inverted"], "subjects": ["plant", "animal", "object", "face"]},
    "lomography":     {"mood": ["nostalgic", "accidental", "warm", "analog"], "materials": ["film", "plastic", "analog", "chemical"], "colors": ["cross_processed", "saturated", "warm", "vignetted"], "subjects": ["face", "object", "food", "animal", "plant"]},
    "cyberpunk":      {"mood": ["dark", "neon", "futuristic", "dystopian"], "materials": ["metal", "glass", "neon", "rain", "chrome"], "colors": ["neon", "magenta", "cyan", "dark"], "subjects": ["face", "object", "text", "sign", "number"]},
    "brutalist":      {"mood": ["heavy", "industrial", "monumental", "raw"], "materials": ["concrete", "metal", "stone", "industrial"], "colors": ["grey", "monochrome", "minimal", "accent"], "subjects": ["object", "sign", "text", "number"]},
    "wpa_poster":     {"mood": ["patriotic", "heroic", "monumental", "vintage"], "materials": ["paper", "print", "silkscreen", "flat"], "colors": ["limited", "warm", "patriotic", "earthy"], "subjects": ["face", "object", "plant", "animal", "sign"]},
    "zine_collage":   {"mood": ["punk", "diy", "rebellious", "raw", "chaotic"], "materials": ["paper", "tape", "photocopy", "glue", "torn"], "colors": ["bw", "lo-fi", "accent", "degraded"], "subjects": ["text", "face", "sign", "object", "number"]},
}


def suggest_styles(subject_type: str, mood_keywords: list[str] = None, top_n: int = 5) -> list[dict]:
    """Suggest best matching styles for a subject type + optional mood.
    Returns list of {style_id, score, reasons} sorted by relevance.
    Wiki-first approach: exact match on structured tags. No vectors needed at <100 styles."""
    scores = {}
    for sid, tags in STYLE_TAGS.items():
        score = 0
        reasons = []

        # Subject match (heaviest weight)
        if subject_type in tags.get("subjects", []):
            idx = tags["subjects"].index(subject_type)
            subject_score = 10 - idx * 2  # first = 10pts, second = 8pts, etc.
            score += subject_score
            reasons.append(f"good for {subject_type}")

        # Mood match
        if mood_keywords:
            for kw in mood_keywords:
                kw_lower = kw.lower()
                for tag_cat in ["mood", "materials", "colors"]:
                    if kw_lower in tags.get(tag_cat, []):
                        score += 5
                        reasons.append(f"matches '{kw}'")
                        break

        if score > 0:
            scores[sid] = {"style_id": sid, "score": score, "reasons": reasons}

    ranked = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
    return ranked[:top_n]


# ─── Entry point async ───────────────────────────────────────────────────────
async def generate_video_free(
    image_bytes: bytes,
    style_id: str = "warhol",
    custom_prompt: str = None,
    progress_cb=None,
    animation_mode: str = "life",
    frame_delay: int = 80,
    session_id: str = "",
) -> tuple:
    """Returns (gif_bytes, prompt_used)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _generate_free_sync, image_bytes, style_id, custom_prompt, progress_cb, animation_mode, frame_delay, session_id
    )


async def generate_video_blend(
    image_bytes: bytes,
    style_a: str,
    style_b: str,
    blend_ratio: float = 0.5,
    progress_cb=None,
    animation_mode: str = "life",
    frame_delay: int = 80,
    session_id: str = "",
) -> tuple:
    """Blend 2 styles (A + B) with configurable ratio."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _generate_blend_sync, image_bytes, style_a, style_b, blend_ratio,
        progress_cb, animation_mode, frame_delay, session_id
    )


def _generate_blend_sync(
    image_bytes: bytes, style_a: str, style_b: str, blend_ratio: float,
    progress_cb=None, animation_mode: str = "life", frame_delay: int = 80, session_id: str = "",
) -> tuple:
    """Pipeline blend: analyze → merged prompt (A+B) → Imagen → animate in style_a (primary)."""
    if progress_cb:
        progress_cb(35)
    subject_desc, subject_type = _analyze_subject(image_bytes)

    # Determine primary/secondary based on ratio
    primary_style = style_a if blend_ratio < 0.5 else style_b
    secondary_style = style_b if blend_ratio < 0.5 else style_a
    primary_pct = int((1 - blend_ratio) * 100) if blend_ratio < 0.5 else int(blend_ratio * 100)
    secondary_pct = 100 - primary_pct

    if progress_cb:
        progress_cb(45)

    # Build blend prompt combining both style instructions
    style_a_enum = StyleId(style_a) if style_a in [e.value for e in StyleId] else StyleId.warhol
    style_b_enum = StyleId(style_b) if style_b in [e.value for e in StyleId] else StyleId.hokusai
    technique_a = STYLE_INSTRUCTIONS.get(style_a_enum, "")
    technique_b = STYLE_INSTRUCTIONS.get(style_b_enum, "")
    comp_a = STYLE_COMPOSITION.get(style_a, "")
    comp_b = STYLE_COMPOSITION.get(style_b, "")

    blend_prompt = f"""Transform this photograph of {subject_desc} by BLENDING two artistic styles together.

SUBJECT: The {subject_type} "{subject_desc}" must remain recognizable.

STYLE A ({primary_pct}%): {style_a.replace('_', ' ').title()}
{technique_a}
{comp_a}

STYLE B ({secondary_pct}%): {style_b.replace('_', ' ').title()}
{technique_b}
{comp_b}

BLEND RULES:
- Combine the techniques, not just visual elements
- Primary style ({primary_pct}%) sets the dominant mood and composition
- Secondary style ({secondary_pct}%) contributes texture, color, or pattern details
- The result must feel like ONE coherent artwork that naturally fuses both traditions
- Examples of good blends: Warhol CMYK posterization done in Hokusai's ukiyo-e ink technique; Klimt gold mosaic applied with Van Gogh's impasto brushstrokes
- Do NOT just place iconic elements side by side — truly FUSE the approaches"""

    # Use the blend prompt with primary style's Imagen call (technique is already in prompt)
    if progress_cb:
        progress_cb(55)
    art_image = _gemini_generate_styled_image(image_bytes, primary_style, blend_prompt, session_id)
    if art_image is None:
        print(f"Blend failed, fallback to PIL for {primary_style}")
        original_img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((512, 512), Image.LANCZOS)
        art_image = _apply_style_transfer(original_img, primary_style)

    if progress_cb:
        progress_cb(75)
    # Animate using primary style's animation function
    gif_bytes = _animate_artistic(art_image, primary_style, subject_type, animation_mode, frame_delay)
    return gif_bytes, blend_prompt


def _generate_free_sync(
    image_bytes: bytes,
    style_id: str,
    custom_prompt: str = None,
    progress_cb=None,
    animation_mode: str = "life",
    frame_delay: int = 80,
    session_id: str = "",
) -> tuple:
    """Returns (gif_bytes, full_prompt_used).
    Pipeline v13: analyze → rich prompt → anti-repetition → Gemini+Imagen → animate."""
    # Pas 1: Analizează subiectul din poză (ce e, cum arată)
    if progress_cb:
        progress_cb(35)
    if custom_prompt:
        subject_desc = custom_prompt
        subject_type = "object"
    else:
        subject_desc, subject_type = _analyze_subject(image_bytes)
        print(f"Subject: [{subject_type}] {subject_desc[:80]}")

    # Pas 2: Construiește mega-prompt cu tot contextul
    if progress_cb:
        progress_cb(45)
    rich_prompt = _build_rich_prompt(style_id, subject_desc, subject_type)

    # Pas 3: Gemini Image Gen cu mega-prompt + poza originală
    if progress_cb:
        progress_cb(55)
    art_image = None
    if image_bytes and len(image_bytes) > 100:
        art_image = _gemini_generate_styled_image(image_bytes, style_id, rich_prompt, session_id)
        if art_image is None:
            print(f"Gemini image gen failed for {style_id}, falling back to PIL")
            original_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            original_img = original_img.resize((512, 512), Image.LANCZOS)
            art_image = _apply_style_transfer(original_img, style_id)
    else:
        # Regenerare fără imagine sursă — fallback la Imagen text-to-image
        art_image, _ = _imagen_fast(rich_prompt, style_id, prompt_is_final=True)

    # Pas 4: Animăm
    if progress_cb:
        progress_cb(75)
    gif_bytes = _animate_artistic(art_image, style_id, subject_type, animation_mode, frame_delay)
    return gif_bytes, rich_prompt


def _analyze_subject(image_bytes: bytes) -> tuple:
    """Gemini analizează poza → (descriere_subiect, tip_subiect).
    Returnează descriere vizuală detaliată + categorie."""
    PROMPT = """Look at this photo and describe the main subject in ONE detailed sentence.

On the FIRST LINE write ONLY one category word:
face | cup | animal | plant | food | object | text | sign | number

Choose:
- face: person's face or portrait
- cup: mug, cup, glass, bottle, drink container
- animal: pet, cat, dog, bird, any animal
- plant: plant, flower, tree, vegetation
- food: food, meal, fruit, edible item
- text: text, letters, words, typography
- sign: sign, poster, label, plaque
- number: numbers, digits, numeric display
- object: everything else

On the SECOND LINE write a detailed visual description (20-40 words):
- Include: what it is, exact colors, materials, texture, size, context
- For text/numbers: what it says, font style, colors, what surface it's on
- Be specific: "large red sans-serif digits 78 in white wooden frame on dark background"
  NOT vague: "a framed number"

Return ONLY these two lines, nothing else."""

    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel, Part
        vertexai.init(project=settings.google_cloud_project, location=settings.google_cloud_location)
        model = GenerativeModel("gemini-2.5-flash")
        response = model.generate_content([PROMPT, Part.from_data(data=image_bytes, mime_type="image/jpeg")])
        lines = response.text.strip().split("\n", 1)
        subject_type = lines[0].strip().lower()
        valid_types = {"face", "cup", "animal", "plant", "food", "object", "text", "sign", "number"}
        if subject_type not in valid_types:
            subject_type = "object"
        subject_desc = lines[1].strip() if len(lines) > 1 else "an object"
        return subject_desc, subject_type
    except Exception as e:
        print(f"Subject analysis failed: {e}")
        return "an object in a photograph", "object"


def _build_rich_prompt(style_id: str, subject_desc: str, subject_type: str) -> str:
    """Construiește mega-prompt cu: subiect + tehnică + compoziție + variație stil-specifică."""
    style_enum = StyleId(style_id) if style_id in [e.value for e in StyleId] else StyleId.warhol
    technique = STYLE_INSTRUCTIONS.get(style_enum, STYLE_INSTRUCTIONS[StyleId.warhol])
    composition = STYLE_COMPOSITION.get(style_id, "")
    variations = STYLE_VARIATIONS.get(style_id, ["emphasize the core artistic technique"])
    variation = random.choice(variations)

    return f"""Transform this photograph of {subject_desc} into a {style_id.replace('_', ' ')} artwork.

SUBJECT PRESERVATION (CRITICAL):
The {subject_type} described as "{subject_desc}" MUST remain the central recognizable focus.
Do NOT replace it with a portrait of the artist, an iconic artwork, or any other subject.
The viewer must be able to identify the original subject immediately.

CREATIVE VISION:
Transform the subject's own material, texture, color, and form using the artist's
signature technique. Let the subject itself become the artwork — its surfaces, edges,
and substance reimagined through the artistic lens. Rich atmospheric details, evocative
environmental elements, and authentic period textures are welcome when they enhance
the subject. The goal is a museum-quality artwork where the subject is the hero,
rendered with the full creative vocabulary of the style.

ARTISTIC TECHNIQUE:
{technique}

COMPOSITION:
{composition}

VARIATION FOR THIS GENERATION:
{variation}

Generate a single artwork that an art history expert would recognize as authentic {style_id.replace('_', ' ')} technique applied to this specific subject."""


# ─── Gemini: prompt artistic + subject detection ──────────────────────────────
def _build_artistic_prompt(image_bytes: bytes, style_id: str) -> tuple:
    """Returns (artistic_prompt, subject_type).

    subject_type: face | cup | animal | plant | food | object
    """
    art_directions = STYLE_ARTISTIC_DIRECTION.get(style_id, STYLE_ARTISTIC_DIRECTION["dali"])

    PROMPT = f"""You are an art director creating an AI image generation prompt. Look at this photo and create a single Imagen prompt that applies an artistic style TO THE EXACT SUBJECT in the image.

CRITICAL RULE: You must transform what is ACTUALLY IN the photo. Do NOT replace, substitute, or hallucinate a different subject. If the photo shows a number, paint that number. If it shows a chair, paint that chair. If it shows a face, paint that face. NEVER generate a portrait of the artist themselves or an iconic artwork — apply the artist's TECHNIQUE to the actual subject.

STEP 1 - On the VERY FIRST LINE, write ONLY one of these subject type words (nothing else on that line):
face | cup | animal | plant | food | object | text | sign | number

Choose based on the main subject:
- face: if a person's face or portrait is prominent
- cup: if it's a mug, cup, glass, bottle, or drink container
- animal: if it's a pet, cat, dog, bird, or any animal
- plant: if it's a plant, flower, tree, or vegetation
- food: if it's food, meal, fruit, or edible item
- text: if it contains text, letters, words, or typography
- sign: if it's a sign, poster, label, or plaque
- number: if it contains numbers, digits, or numeric display
- object: for everything else (building, car, gadget, furniture, etc.)

STEP 2 - Describe the ACTUAL subject with precise visual details:
- People: age, gender, exact hair (color, cut style), facial hair, eye color, skin tone, clothing, expression
- Objects: exact material, precise color, shape, texture, size, context
- Text/Numbers/Signs: what it says/shows, the font style, colors, material it's on, framing
- Animals: species, breed, colors, pose

STEP 3 - Write the final Imagen prompt that applies the artistic TECHNIQUE to this exact subject.

Artistic technique to apply: {art_directions}

Rules for the prompt:
- The subject from the photo MUST remain the same — do NOT swap it for something else
- Apply the artistic TECHNIQUE (colors, brushwork, composition style) to the actual subject
- Include visual details: color palette, texture, technique, lighting
- 40-60 words total
- NO generic terms like "artistic", "beautiful", "stunning"
- NEVER describe a portrait of the artist themselves

Examples:
- object on line 1, then: "framed red number 78 on dark background reimagined as Andy Warhol silkscreen print, posterized into four flat CMYK color panels, Ben-Day halftone dots, bold graphic pop art reduction, hot pink and acid yellow fills"
- face on line 1, then: "young woman with curly red hair, her portrait reimagined using Gustav Klimt's gold leaf mosaic technique, Byzantine ornamental borders, jewel tones of emerald and sapphire, oil on canvas"
- cup on line 1, then: "white ceramic coffee mug reimagined using Andy Warhol's silkscreen print technique, bold flat CMYK colors, black outline, repetitive 2x2 grid, vivid red and white"
- animal on line 1, then: "orange tabby cat reimagined using Hiroshige ukiyo-e woodblock print technique, bold ink outlines, flat color washes, cherry blossom background"
- number on line 1, then: "large red digits 78 in white frame reimagined using Mondrian De Stijl technique, decomposed into primary color rectangles with bold black grid lines"

Return ONLY subject_type on line 1, then the final prompt on line 2+. Nothing else."""

    # Vertex AI (ADC - funcționează pe Cloud Run)
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel, Part

        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
        model = GenerativeModel("gemini-2.5-flash")
        image_part = Part.from_data(data=image_bytes, mime_type="image/jpeg")
        response = model.generate_content([PROMPT, image_part])
        result = response.text.strip()
        return _parse_gemini_response(result)
    except Exception as e1:
        print(f"Gemini Vertex failed: {e1}")
        # Fallback: google-genai cu API key
        try:
            genai.configure(api_key=settings.google_api_key or None)
            model2 = genai.GenerativeModel("gemini-2.5-flash")
            response2 = model2.generate_content([
                PROMPT,
                {"mime_type": "image/jpeg", "data": image_bytes}
            ])
            result2 = response2.text.strip()
            return _parse_gemini_response(result2)
        except Exception as e2:
            print(f"Gemini API key also failed: {e2}")
            return f"the exact subject from the photo transformed using {art_directions}, detailed artistic rendering", "object"


def _parse_gemini_response(text: str) -> tuple:
    """Parsează răspunsul Gemini: prima linie = subject_type, restul = prompt."""
    VALID_SUBJECTS = {"face", "cup", "animal", "plant", "food", "object", "text", "sign", "number"}
    lines = text.strip().splitlines()
    if not lines:
        return text, "object"

    first_line = lines[0].strip().lower()
    if first_line in VALID_SUBJECTS:
        subject_type = first_line
        artistic_prompt = "\n".join(lines[1:]).strip()
    else:
        # Gemini nu a respectat formatul - detectăm subiectul din text
        subject_type = "object"
        for subj in VALID_SUBJECTS:
            if subj in text.lower():
                subject_type = subj
                break
        artistic_prompt = text

    print(f"Subject: {subject_type} | Prompt: {artistic_prompt[:80]}...")
    return artistic_prompt, subject_type


# ─── GEMINI NATIVE IMAGE GENERATION ──────────────────────────────────────────

# Import STYLE_INSTRUCTIONS from gemini_service (the unified technique prompts)
from app.services.gemini_service import STYLE_INSTRUCTIONS
from app.models.schemas import StyleId

def _gemini_generate_styled_image(image_bytes: bytes, style_id: str, rich_prompt: str, session_id: str = "") -> Image.Image | None:
    """Two-step pipeline: Gemini describes the artwork → Imagen 4 generates it.
    
    Step 1: Gemini 2.5 Flash analyzes photo + style → writes a vivid description
            of what the final artwork looks like (80-100 words).
    Step 2: Imagen 4 generates the artwork from that description.
    
    This produces dramatically better results than Gemini image gen alone because
    Imagen 4 is a dedicated image generation model that creates from scratch
    rather than doing light style transfer on existing pixels.
    """
    try:
        from google import genai
        from google.genai import types

        api_key = settings.google_api_key
        if not api_key:
            print("Image gen: no API key configured")
            return None
        client = genai.Client(api_key=api_key)

        # Get style details for the description prompt
        style_enum = StyleId(style_id) if style_id in [e.value for e in StyleId] else StyleId.warhol
        technique = STYLE_INSTRUCTIONS.get(style_enum, STYLE_INSTRUCTIONS[StyleId.warhol])
        composition = STYLE_COMPOSITION.get(style_id, "")
        variations = STYLE_VARIATIONS.get(style_id, ["emphasize the core artistic technique"])
        variation = random.choice(variations)

        # STEP 1: Gemini creates an artistic interpretation description
        # v33: safe re-additions — soft anti-repetition + signature technique hints
        style_label = style_id.replace("_", " ").title()
        variation_hint = _recall_style(session_id, style_id) if session_id else ""

        describe_prompt = f"""You are a world-class art director. Look at this photo, then imagine
the most creative, surprising interpretation a {style_label} master would create.

The artist sees this subject and is INSPIRED — they don't just copy it literally.
They reimagine it through their unique artistic vision while keeping the subject recognizable.

Technique: {technique}
Composition: {composition}
Creative direction: {variation}

{variation_hint}

Write an 80-120 word IMAGE GENERATION PROMPT for the final masterpiece.
Rules:
- The original subject must be RECOGNIZABLE but CREATIVELY TRANSFORMED
- USE the artist's signature techniques: if Dalí, the subject can melt and drape; if Van Gogh, impasto brushstrokes cover every surface; if Klimt, gold mosaic; if Hokusai, bold ink outlines and bokashi
- Describe specific artistic decisions: unusual color choices, dramatic composition, texture surprises, atmospheric landscapes
- Include material and surface qualities (oil paint ridges, ink bleeding, gold leaf, melting chrome, draped surfaces)
- Add atmosphere and environment — sky, landscape, lighting, mood. What does this artwork FEEL like?
- Think about what would make this artwork WIN an art prize — be bold and ambitious
- Transform the SUBJECT ITSELF using the technique rather than placing a famous painting next to it
- Write as ONE paragraph, present tense, describing the finished artwork"""

        # Build content: text + photo + (optional) style anchor for consistency on regen
        content_parts = [
            types.Part.from_text(text=describe_prompt),
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        ]
        style_anchor = _get_style_anchor(session_id, style_id) if session_id else None
        if style_anchor:
            content_parts.append(types.Part.from_text(
                text="\n\nSTYLE REFERENCE (maintain this artistic family but create a NEW variation, not a copy):"
            ))
            content_parts.append(types.Part.from_bytes(data=style_anchor, mime_type="image/jpeg"))

        desc_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=content_parts,
        )
        artwork_description = desc_response.text.strip()
        print(f"Artwork description for {style_id}: {artwork_description[:120]}...")

        # Remember description for anti-repetition on next gen
        if session_id:
            _remember_style(session_id, style_id, artwork_description)

        # STEP 2: Imagen 4 with minimal config (no negative_prompt → maximum creativity)
        imagen_response = client.models.generate_images(
            model="imagen-4.0-ultra-generate-001",
            prompt=artwork_description,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1",
            ),
        )

        for img_result in imagen_response.generated_images:
            img = Image.open(io.BytesIO(img_result.image.image_bytes)).convert("RGB")
            img = img.resize((512, 512), Image.LANCZOS)
            print(f"Imagen 4 gen SUCCESS for {style_id} ({img.size})")
            # Save anchor for future regens with same session
            if session_id:
                _save_style_anchor(session_id, style_id, img)
            return img

        print(f"Imagen 4: no image generated for {style_id}")
        return None

    except Exception as e:
        print(f"Imagen 4 pipeline FAILED for {style_id}: {e}")
        # Fallback to Gemini 3.1 Flash Image (still better than 2.5)
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=settings.google_api_key)
            response = client.models.generate_content(
                model="gemini-3.1-flash-image-preview",
                contents=[
                    types.Part.from_text(text=rich_prompt),
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                ],
                config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
            )
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data and \
                       part.inline_data.mime_type and part.inline_data.mime_type.startswith("image/"):
                        img = Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
                        img = img.resize((512, 512), Image.LANCZOS)
                        print(f"Gemini 3.1 fallback SUCCESS for {style_id}")
                        return img
        except Exception as e2:
            print(f"Gemini 3.1 fallback also FAILED: {e2}")
        return None


# ─── STYLE TRANSFER: transformă poza originală artistic cu PIL/NumPy ─────────

def _apply_style_transfer(img: Image.Image, style_id: str) -> Image.Image:
    """Aplică transformare artistică DIRECT pe imaginea originală.
    Subiectul rămâne 100% intact — doar pixelii sunt transformați."""
    dispatch = {
        "warhol":         _style_warhol,
        "banksy":         _style_banksy,
        "dali":           _style_dali,
        "vangogh":        _style_vangogh,
        "klimt":          _style_klimt,
        "ghibli":         _style_ghibli,
        "hokusai":        _style_hokusai,
        "baroque":        _style_baroque,
        "mondrian":       _style_mondrian,
        "mucha":          _style_mucha,
        "expressionism":  _style_expressionism,
        "futurism":       _style_futurism,
        "constructivism": _style_constructivism,
        "cyberpunk":      _style_cyberpunk,
        "brutalist":      _style_brutalist,
        "pointillism":    _style_pointillism,
        "risograph":      _style_risograph,
        "woodcut":        _style_woodcut,
        "ligne_claire":   _style_ligne_claire,
        "daguerreotype":  _style_daguerreotype,
        "infrared":       _style_infrared,
        "lomography":     _style_lomography,
        "swiss_poster":   _style_swiss_poster,
        "byzantine":      _style_byzantine,
        "preraphaelite":  _style_preraphaelite,
        "meiji_print":    _style_meiji_print,
        "persian_mini":   _style_persian_mini,
        "mughal_mini":    _style_mughal_mini,
        "wpa_poster":     _style_wpa_poster,
        "zine_collage":   _style_zine_collage,
    }
    fn = dispatch.get(style_id, _style_default)
    return fn(img)


def _style_warhol(img: Image.Image) -> Image.Image:
    """Warhol: posterize + CMYK color separations + 2x2 grid."""
    img = img.quantize(colors=6, method=Image.Quantize.MEDIANCUT).convert("RGB")
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    hh, hw = h // 2, w // 2
    # 4 color tints for quadrants
    tints = [
        np.array([255, 0, 128]),   # magenta
        np.array([0, 200, 255]),   # cyan
        np.array([255, 255, 0]),   # yellow
        np.array([100, 255, 50]),  # lime
    ]
    result = arr.copy()
    for i, (y0, y1, x0, x1) in enumerate([
        (0, hh, 0, hw), (0, hh, hw, w), (hh, h, 0, hw), (hh, h, hw, w)
    ]):
        tint = tints[i].astype(np.float32)
        region = result[y0:y1, x0:x1]
        # Strong posterized tint
        result[y0:y1, x0:x1] = region * 0.55 + tint * 0.45
    # High contrast
    result = (result - 60) * 1.6 + 60
    # Bold black outlines via edge detection
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    edges = np.abs(np.gradient(gray, axis=0)) + np.abs(np.gradient(gray, axis=1))
    edge_mask = (edges > 15).astype(np.float32)[:, :, np.newaxis]
    result = result * (1 - edge_mask * 0.8)
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def _style_banksy(img: Image.Image) -> Image.Image:
    """Banksy: high contrast B&W stencil + single red accent."""
    arr = np.array(img, dtype=np.float32)
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    # Hard threshold stencil
    stencil = np.where(gray > 120, 220.0, 25.0)
    result = np.stack([stencil, stencil, stencil], axis=-1)
    # Red accent on warm areas
    warm = (arr[:, :, 0] > arr[:, :, 1] + 30) & (arr[:, :, 0] > 100)
    result[warm] = [200, 30, 30]
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def _style_dali(img: Image.Image) -> Image.Image:
    """Dalí: fluid warp distortion + warm ochre sky tint."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    # Fluid distortion
    dx = (8 * np.sin(3 * np.pi * yc / h + 1.5)).astype(int)
    dy = (6 * np.cos(3 * np.pi * xc / w + 0.7)).astype(int)
    sx = np.clip(xc.astype(int) + dx, 0, w - 1)
    sy = np.clip(yc.astype(int) + dy, 0, h - 1)
    result = arr[sy, sx].copy()
    # Warm ochre tint
    result[:, :, 0] *= 1.1
    result[:, :, 1] *= 0.95
    result[:, :, 2] *= 0.8
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def _style_vangogh(img: Image.Image) -> Image.Image:
    """Van Gogh: heavy saturation + swirl distortion + paint texture."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    # Boost saturation
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    arr = gray[:, :, np.newaxis] + (arr - gray[:, :, np.newaxis]) * 1.8
    # Swirl center
    cy, cx = h / 2, w / 2
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = np.sqrt((xc - cx) ** 2 + (yc - cy) ** 2)
    angle = np.arctan2(yc - cy, xc - cx)
    swirl_angle = angle + 0.15 * np.exp(-dist / (h * 0.5))
    src_x = np.clip(cx + dist * np.cos(swirl_angle), 0, w - 1).astype(int)
    src_y = np.clip(cy + dist * np.sin(swirl_angle), 0, h - 1).astype(int)
    result = arr[src_y, src_x]
    # Paint edge texture
    edges = np.abs(np.gradient(gray, axis=0)) + np.abs(np.gradient(gray, axis=1))
    edge_boost = np.clip(edges / 20, 0, 1)[:, :, np.newaxis]
    result = result * (1 + edge_boost * 0.5)
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def _style_klimt(img: Image.Image) -> Image.Image:
    """Klimt: gold overlay on non-face areas + geometric pattern."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    gold = np.array([212, 175, 55], dtype=np.float32)
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    # Geometric mosaic pattern
    pattern = (np.sin(xc * 0.2) * np.sin(yc * 0.2) + 1) * 0.5
    # Keep center (likely subject) more natural, gold the edges
    dist = np.sqrt((xc - w / 2) ** 2 + (yc - h / 2) ** 2)
    edge_factor = np.clip(dist / (min(h, w) * 0.35) - 0.3, 0, 1)[:, :, np.newaxis]
    gold_alpha = edge_factor * 0.5 * pattern[:, :, np.newaxis]
    result = arr * (1 - gold_alpha) + gold * gold_alpha
    # Warm rich tone
    result[:, :, 0] *= 1.05
    result[:, :, 2] *= 0.85
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def _style_ghibli(img: Image.Image) -> Image.Image:
    """Ghibli: soft watercolor blur + warm tones + edge outlines."""
    # Watercolor effect: blur + quantize
    soft = img.filter(ImageFilter.GaussianBlur(3))
    soft = soft.quantize(colors=24, method=Image.Quantize.MEDIANCUT).convert("RGB")
    arr = np.array(soft, dtype=np.float32)
    # Warm ambient light
    arr[:, :, 0] *= 1.06
    arr[:, :, 1] *= 1.03
    # Add ink outlines from original
    orig = np.array(img, dtype=np.float32)
    gray = 0.299 * orig[:, :, 0] + 0.587 * orig[:, :, 1] + 0.114 * orig[:, :, 2]
    edges = np.abs(np.gradient(gray, axis=0)) + np.abs(np.gradient(gray, axis=1))
    edge_mask = np.clip(edges / 25, 0, 1)[:, :, np.newaxis]
    arr = arr * (1 - edge_mask * 0.7) + 30 * edge_mask * 0.7
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _style_hokusai(img: Image.Image) -> Image.Image:
    """Hokusai: flat color quantize + bold outlines + Prussian blue tint."""
    quantized = img.quantize(colors=8, method=Image.Quantize.MEDIANCUT).convert("RGB")
    arr = np.array(quantized, dtype=np.float32)
    # Prussian blue tint
    arr[:, :, 2] *= 1.3
    arr[:, :, 0] *= 0.85
    # Bold ink outlines
    orig = np.array(img, dtype=np.float32)
    gray = 0.299 * orig[:, :, 0] + 0.587 * orig[:, :, 1] + 0.114 * orig[:, :, 2]
    edges = np.abs(np.gradient(gray, axis=0)) + np.abs(np.gradient(gray, axis=1))
    edge_mask = np.clip(edges / 12, 0, 1)[:, :, np.newaxis]
    arr = arr * (1 - edge_mask) + 15 * edge_mask
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _style_baroque(img: Image.Image) -> Image.Image:
    """Baroque: strong chiaroscuro + warm tone + vignette."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    # Chiaroscuro: one-sided lighting
    xc = np.linspace(0, 1, w)[np.newaxis, :]
    light = np.clip(1.2 - xc * 0.8, 0.2, 1.2)[:, :, np.newaxis]
    arr = arr * light
    # Warm earth tones
    arr[:, :, 0] *= 1.1
    arr[:, :, 1] *= 0.95
    arr[:, :, 2] *= 0.75
    # Dark vignette
    yg, xg = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = ((xg / w - 0.5) ** 2 + (yg / h - 0.5) ** 2)
    vignette = np.clip(1.0 - dist * 2.5, 0.1, 1.0)[:, :, np.newaxis]
    arr *= vignette
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _style_mondrian(img: Image.Image) -> Image.Image:
    """Mondrian: decompose into color blocks + black grid."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    colors = [
        np.array([220, 20, 20]),  np.array([20, 60, 200]),
        np.array([240, 210, 20]), np.array([240, 240, 240]),
    ]
    # Quantize to 4 dominant colors mapped to Mondrian primaries
    quantized = img.quantize(colors=4, method=Image.Quantize.MEDIANCUT).convert("RGB")
    q_arr = np.array(quantized, dtype=np.float32)
    # Map each quantized color to nearest Mondrian primary
    result = np.zeros_like(arr)
    for y in range(h):
        for x in range(0, w, 4):  # process in blocks for speed
            x_end = min(x + 4, w)
            pixel = q_arr[y, x]
            best = min(colors, key=lambda c: np.sum((pixel - c) ** 2))
            result[y, x:x_end] = best
    # Black grid lines
    grid_y = np.linspace(0, h, 6, dtype=int)
    grid_x = np.linspace(0, w, 6, dtype=int)
    for gy in grid_y:
        result[max(0, gy - 2):min(h, gy + 2)] = 0
    for gx in grid_x:
        result[:, max(0, gx - 2):min(w, gx + 2)] = 0
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def _style_mucha(img: Image.Image) -> Image.Image:
    """Mucha: pastel tones + soft blur + outline."""
    arr = np.array(img, dtype=np.float32)
    # Desaturate toward pastels
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    pastel = np.array([245, 215, 195], dtype=np.float32)
    result = arr * 0.5 + pastel * 0.2 + gray[:, :, np.newaxis] * 0.3
    # Soft glow
    glow = Image.fromarray(np.clip(result, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4))
    glow_arr = np.array(glow, dtype=np.float32)
    result = result * 0.7 + glow_arr * 0.3
    # Ink outlines
    edges = np.abs(np.gradient(gray, axis=0)) + np.abs(np.gradient(gray, axis=1))
    edge_mask = np.clip(edges / 20, 0, 1)[:, :, np.newaxis]
    result = result * (1 - edge_mask * 0.6) + 40 * edge_mask * 0.6
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def _style_expressionism(img: Image.Image) -> Image.Image:
    """Expressionism: harsh colors + distortion + high contrast."""
    arr = np.array(img, dtype=np.float32)
    # Anti-naturalistic color: swap/boost channels
    arr[:, :, 1] *= 0.7  # reduce green
    arr[:, :, 0] *= 1.3  # boost red
    # High contrast
    arr = (arr - 100) * 1.8 + 100
    # Slight angular distortion
    h, w = arr.shape[:2]
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = (4 * np.sin(yc * 0.08)).astype(int)
    sx = np.clip(xc.astype(int) + dx, 0, w - 1)
    result = arr[yc.astype(int), sx]
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def _style_futurism(img: Image.Image) -> Image.Image:
    """Futurism: stroboscopic ghost + speed lines."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    # Multiple shifted overlays (stroboscopic)
    result = arr * 0.5
    for shift in [8, 16, 24]:
        shifted = np.roll(arr, shift, axis=1) * 0.2
        result += shifted
    # Speed line diagonals
    for y in range(0, h, 6):
        result[y, :] *= 0.85
    # Electric blue/orange tint
    result[:, :, 2] *= 1.2
    result[:, :, 0] *= 1.1
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def _style_constructivism(img: Image.Image) -> Image.Image:
    """Constructivism: red/black/white only + geometric."""
    arr = np.array(img, dtype=np.float32)
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    result = np.zeros_like(arr)
    result[gray > 170] = [240, 240, 240]  # white
    result[(gray > 85) & (gray <= 170)] = [200, 30, 30]  # red
    result[gray <= 85] = [20, 20, 20]  # black
    return Image.fromarray(result.astype(np.uint8))


def _style_cyberpunk(img: Image.Image) -> Image.Image:
    """Cyberpunk: neon glow + dark + scan lines + RGB split."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    # Darken everything
    arr *= 0.4
    # Neon boost on bright edges
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    edges = np.abs(np.gradient(gray, axis=0)) + np.abs(np.gradient(gray, axis=1))
    neon = np.clip(edges / 8, 0, 1)[:, :, np.newaxis]
    arr[:, :, 0] += neon[:, :, 0] * 200  # magenta edges
    arr[:, :, 2] += neon[:, :, 0] * 180  # cyan
    # Scan lines
    for y in range(0, h, 3):
        arr[y] *= 0.7
    # RGB channel offset
    arr[:, :, 0] = np.roll(arr[:, :, 0], 2, axis=1)
    arr[:, :, 2] = np.roll(arr[:, :, 2], -2, axis=1)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _style_brutalist(img: Image.Image) -> Image.Image:
    """Brutalist: grey concrete + high contrast + heavy."""
    arr = np.array(img, dtype=np.float32)
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    # Concrete grey with slight warm tint
    result = np.stack([gray * 1.02, gray * 0.98, gray * 0.94], axis=-1)
    # High contrast
    result = (result - 90) * 1.5 + 90
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def _style_pointillism(img: Image.Image) -> Image.Image:
    """Seurat chromoluminarist: pure unmixed pigment dots on regular grid.
    Each dot is a single pure color from Seurat's palette. Adjacent dots
    are complementary colors that mix OPTICALLY at viewing distance."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    dot_size = 5
    result = np.full_like(arr, 245)  # white canvas

    # Seurat's palette — 11 pure unmixed pigment colors
    PIGMENTS = np.array([
        [220, 40, 40],    # cadmium red
        [240, 130, 10],   # chrome orange
        [240, 210, 40],   # cadmium yellow
        [250, 250, 200],  # zinc white warm
        [130, 200, 60],   # viridian green
        [40, 140, 230],   # cobalt blue
        [70, 50, 180],    # ultramarine violet
        [180, 100, 160],  # cobalt violet
        [255, 200, 180],  # naples yellow (warm highlight)
        [180, 210, 240],  # cerulean (cool highlight)
        [35, 25, 70],     # dark indigo (deepest shadow)
    ], dtype=np.float32)

    for y in range(0, h - dot_size, dot_size):
        for x in range(0, w - dot_size, dot_size):
            block = arr[y:y + dot_size, x:x + dot_size]
            target = block.mean(axis=(0, 1))

            # Find 2 closest pure pigments for optical mixing
            distances = np.linalg.norm(PIGMENTS - target, axis=1)
            idx_sorted = np.argsort(distances)
            primary = PIGMENTS[idx_sorted[0]]
            secondary = PIGMENTS[idx_sorted[1]]

            # Checkerboard: alternate primary/secondary
            grid_pos = (y // dot_size + x // dot_size) % 2
            color = primary if grid_pos == 0 else secondary

            # Draw circular dot
            cy, cx = y + dot_size // 2, x + dot_size // 2
            r = dot_size // 2 - 1
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if dy * dy + dx * dx <= r * r:
                        py, px = cy + dy, cx + dx
                        if 0 <= py < h and 0 <= px < w:
                            result[py, px] = color
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def _style_risograph(img: Image.Image) -> Image.Image:
    """Risograph: 2-3 color channels with misregistration."""
    arr = np.array(img, dtype=np.float32)
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    result = np.zeros_like(arr)
    # Channel 1: pink (shifted right)
    pink_mask = np.clip((255 - gray) / 255, 0, 1)
    result[:, :, 0] += np.roll(pink_mask, 3, axis=1) * 255
    result[:, :, 1] += np.roll(pink_mask, 3, axis=1) * 50
    result[:, :, 2] += np.roll(pink_mask, 3, axis=1) * 100
    # Channel 2: teal (shifted left)
    result[:, :, 1] += np.roll(pink_mask, -2, axis=1) * 180
    result[:, :, 2] += np.roll(pink_mask, -2, axis=1) * 180
    # Paper grain
    rng = np.random.default_rng(42)
    grain = rng.normal(0, 8, arr.shape)
    result += grain
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def _style_woodcut(img: Image.Image) -> Image.Image:
    """Woodcut: pure black & white, no greyscale."""
    arr = np.array(img, dtype=np.float32)
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    bw = np.where(gray > 128, 255.0, 0.0)
    return Image.fromarray(np.stack([bw, bw, bw], axis=-1).astype(np.uint8))


def _style_ligne_claire(img: Image.Image) -> Image.Image:
    """Ligne Claire: flat colors + uniform ink outlines."""
    quantized = img.quantize(colors=12, method=Image.Quantize.MEDIANCUT).convert("RGB")
    arr = np.array(quantized, dtype=np.float32)
    # Uniform ink outlines
    orig = np.array(img, dtype=np.float32)
    gray = 0.299 * orig[:, :, 0] + 0.587 * orig[:, :, 1] + 0.114 * orig[:, :, 2]
    edges = np.abs(np.gradient(gray, axis=0)) + np.abs(np.gradient(gray, axis=1))
    edge_mask = (edges > 12).astype(np.float32)[:, :, np.newaxis]
    arr = arr * (1 - edge_mask) + 20 * edge_mask
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _style_daguerreotype(img: Image.Image) -> Image.Image:
    """Daguerreotype: silver-grey + vignette + halation."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    # Silver tone (slightly cool)
    result = np.stack([gray * 0.95, gray * 0.97, gray * 1.0], axis=-1)
    # Vignette
    yg, xg = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = ((xg / w - 0.5) ** 2 + (yg / h - 0.5) ** 2)
    vignette = np.clip(1.0 - dist * 3, 0.15, 1.0)[:, :, np.newaxis]
    result *= vignette
    # Halation on highlights
    highlights = np.clip((gray - 200) / 55, 0, 1)
    glow = Image.fromarray((highlights * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(8))
    glow_arr = np.array(glow, dtype=np.float32)[:, :, np.newaxis] / 255
    result += glow_arr * 40
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def _style_infrared(img: Image.Image) -> Image.Image:
    """Infrared: white foliage + dark sky + magenta shadows."""
    arr = np.array(img, dtype=np.float32)
    # Green areas become white (chlorophyll response)
    green_mask = (arr[:, :, 1] > arr[:, :, 0]) & (arr[:, :, 1] > arr[:, :, 2])
    arr[green_mask] = [250, 240, 250]
    # Blue areas (sky) become dark
    blue_mask = (arr[:, :, 2] > arr[:, :, 0] + 30) & (arr[:, :, 2] > arr[:, :, 1])
    arr[blue_mask] *= 0.3
    # Magenta tint on shadows
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    dark = gray < 80
    arr[dark, 0] *= 1.3
    arr[dark, 2] *= 1.2
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _style_lomography(img: Image.Image) -> Image.Image:
    """Lomography: heavy vignette + cross-process + saturation boost."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    # Cross-process color shift
    arr[:, :, 0] *= 1.15  # orange-pink reds
    arr[:, :, 1] *= 0.9   # muted greens
    arr[:, :, 2] *= 1.1   # blue-green cast
    # Saturation boost
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    arr = gray[:, :, np.newaxis] + (arr - gray[:, :, np.newaxis]) * 1.5
    # Heavy vignette
    yg, xg = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = ((xg / w - 0.5) ** 2 + (yg / h - 0.5) ** 2)
    vignette = np.clip(1.0 - dist * 3.5, 0.05, 1.0)[:, :, np.newaxis]
    arr *= vignette
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _style_swiss_poster(img: Image.Image) -> Image.Image:
    """Swiss Grid: halftone dots + 2 spot colors + black."""
    arr = np.array(img, dtype=np.float32)
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    h, w = arr.shape[:2]
    result = np.full_like(arr, 245)  # white ground
    # Halftone: threshold to 3 tones mapped to 2 spot colors
    result[gray < 85] = [220, 50, 30]    # red spot
    result[(gray >= 85) & (gray < 170)] = [20, 20, 20]  # black
    # White stays white (gray >= 170)
    return Image.fromarray(result.astype(np.uint8))


def _style_byzantine(img: Image.Image) -> Image.Image:
    """Byzantine: gold ground + mosaic tessera + frontal."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    # Pixelate into tessera tiles (8x8)
    tile = 8
    for y in range(0, h - tile, tile):
        for x in range(0, w - tile, tile):
            avg = arr[y:y + tile, x:x + tile].mean(axis=(0, 1))
            arr[y:y + tile, x:x + tile] = avg
    # Gold tint on background (lighter areas)
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    gold = np.array([212, 185, 70], dtype=np.float32)
    gold_mask = np.clip((gray - 140) / 115, 0, 0.6)[:, :, np.newaxis]
    arr = arr * (1 - gold_mask) + gold * gold_mask
    # Dark lead-line gaps between tiles
    for y in range(0, h, tile):
        arr[y:y + 1] *= 0.3
    for x in range(0, w, tile):
        arr[:, x:x + 1] *= 0.3
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _style_preraphaelite(img: Image.Image) -> Image.Image:
    """Pre-Raphaelite: jewel saturation + sharp detail + even light."""
    arr = np.array(img, dtype=np.float32)
    # Jewel saturation boost
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    arr = gray[:, :, np.newaxis] + (arr - gray[:, :, np.newaxis]) * 1.6
    # Sharpen
    sharp = img.filter(ImageFilter.SHARPEN).filter(ImageFilter.SHARPEN)
    s_arr = np.array(sharp, dtype=np.float32)
    arr = arr * 0.6 + s_arr * 0.4
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _style_meiji_print(img: Image.Image) -> Image.Image:
    """Meiji: soft bokashi gradation + indigo/rose palette."""
    arr = np.array(img, dtype=np.float32)
    # Quantize + soft blur for bokashi
    soft = img.filter(ImageFilter.GaussianBlur(2))
    soft = soft.quantize(colors=10, method=Image.Quantize.MEDIANCUT).convert("RGB")
    arr = np.array(soft, dtype=np.float32)
    # Indigo/rose tint
    arr[:, :, 2] *= 1.15
    arr[:, :, 0] *= 1.05
    arr[:, :, 1] *= 0.9
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _style_persian_mini(img: Image.Image) -> Image.Image:
    """Persian: flat jewel colors + gold + no shadows."""
    arr = np.array(img, dtype=np.float32)
    # Remove shadows (flatten)
    arr = np.clip(arr * 1.3, 0, 255)
    # Boost saturation to jewel level
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    arr = gray[:, :, np.newaxis] + (arr - gray[:, :, np.newaxis]) * 2.0
    # Quantize to flat fills
    result = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    result = result.quantize(colors=8, method=Image.Quantize.MEDIANCUT).convert("RGB")
    return result


def _style_mughal_mini(img: Image.Image) -> Image.Image:
    """Mughal: warm earths + atmospheric sky + botanical detail."""
    arr = np.array(img, dtype=np.float32)
    # Warm earth tone shift
    arr[:, :, 0] *= 1.1
    arr[:, :, 1] *= 0.95
    arr[:, :, 2] *= 0.85
    # Mild quantize for miniature flatness
    result = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    result = result.quantize(colors=16, method=Image.Quantize.MEDIANCUT).convert("RGB")
    return result


def _style_wpa_poster(img: Image.Image) -> Image.Image:
    """WPA: flat heroic silhouette + earthy palette + 5 colors max."""
    quantized = img.quantize(colors=5, method=Image.Quantize.MEDIANCUT).convert("RGB")
    arr = np.array(quantized, dtype=np.float32)
    # Warm earthy tint
    arr[:, :, 0] *= 1.05
    arr[:, :, 1] *= 0.95
    arr[:, :, 2] *= 0.8
    # High contrast for poster feel
    arr = (arr - 70) * 1.4 + 70
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _style_zine_collage(img: Image.Image) -> Image.Image:
    """Zine: B&W high contrast + torn edges + noise."""
    arr = np.array(img, dtype=np.float32)
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    # Harsh B&W photocopy
    bw = np.clip((gray - 100) * 2.5 + 100, 0, 255)
    result = np.stack([bw, bw, bw], axis=-1)
    # Heavy noise (photocopy degradation)
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 20, result.shape)
    result += noise
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def _style_default(img: Image.Image) -> Image.Image:
    """Default: mild artistic enhancement."""
    arr = np.array(img, dtype=np.float32)
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    arr = gray[:, :, np.newaxis] + (arr - gray[:, :, np.newaxis]) * 1.4
    arr = (arr - 80) * 1.3 + 80
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


# ─── Imagen 3 Fast ────────────────────────────────────────────────────────────
def _imagen_fast(prompt: str, style_id: str, prompt_is_final: bool = False, image_bytes: bytes = None) -> tuple:
    """Imagen 3 Fast - transformă imaginea artistic (image-to-image cu referință).
    Falls back to text-to-image dacă edit_image nu e disponibil.
    Returns (PIL Image, prompt_str)."""
    try:
        import vertexai
        from vertexai.preview.vision_models import ImageGenerationModel, Image as VertexImage

        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )

        full_prompt = prompt if prompt_is_final else prompt + ", masterpiece, highly detailed, 4k"
        model = ImageGenerationModel.from_pretrained("imagen-3.0-fast-generate-001")

        # Try image-to-image (edit) mode first — preserves actual subject
        if image_bytes and len(image_bytes) > 100:
            try:
                base_image = VertexImage(image_bytes=image_bytes)
                response = model.edit_image(
                    prompt=full_prompt,
                    base_image=base_image,
                    number_of_images=1,
                    safety_filter_level="block_few",
                    person_generation="allow_all",
                )
                img = Image.open(io.BytesIO(response.images[0]._image_bytes)).convert("RGB")
                print(f"Imagen edit_image SUCCESS for {style_id}")
                return img, full_prompt
            except Exception as edit_err:
                print(f"Imagen edit_image failed ({edit_err}), falling back to generate_images")

        # Fallback: text-to-image (may not preserve subject)
        response = model.generate_images(
            prompt=full_prompt,
            number_of_images=1,
            aspect_ratio="1:1",
            safety_filter_level="block_few",
            person_generation="allow_all",
        )
        img = Image.open(io.BytesIO(response.images[0]._image_bytes)).convert("RGB")
        return img, full_prompt

    except Exception as e:
        print(f"Imagen Fast failed: {e}")
        return _color_gradient_fallback(style_id), f"[fallback] {prompt[:80]}"


def _color_gradient_fallback(style_id: str) -> Image.Image:
    colors = {
        "warhol":   [(255, 0, 128),  (255, 255, 0)],
        "hokusai":  [(0, 40, 140),   (0, 180, 220)],
        "klimt":    [(80, 50, 5),    (200, 160, 20)],
        "ghibli":   [(30, 100, 60),  (120, 190, 220)],
        "banksy":   [(15, 15, 15),   (70, 70, 70)],
        "dali":     [(160, 120, 60), (240, 210, 90)],
        "vangogh":  [(15, 30, 90),   (220, 140, 0)],
        "baroque":  [(20, 8, 0),     (110, 50, 15)],
        "mondrian": [(180, 0, 0),    (0, 40, 160)],
        "mucha":    [(200, 140, 160),(240, 220, 190)],
    }.get(style_id, [(20, 20, 50), (100, 50, 150)])
    h, w = 400, 400
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    c0, c1 = colors
    for y in range(h):
        t = y / h
        arr[y] = [int(c0[i] * (1 - t) + c1[i] * t) for i in range(3)]
    return Image.fromarray(arr)


# ─── Effect overlay: blend generic effect onto style-specific base frames ─────
def _overlay_effect(base_frames: list, effect_frames: list) -> list:
    """Composit: style-specific animation as base + generic effect overlay.
    Base carries the artistic identity (Warhol CMYK shift, Hokusai wave, etc.)
    Effect adds the user-chosen layer (steam wisps, wind, sparkles, light sweep).
    Blend: 70% base + 30% effect difference from original."""
    if not base_frames or not effect_frames:
        return base_frames or effect_frames
    # Use the first effect frame as reference (static image before effect)
    ref = np.array(effect_frames[0], dtype=np.float32)
    result = []
    for i in range(min(len(base_frames), len(effect_frames))):
        base_arr = np.array(base_frames[i], dtype=np.float32)
        eff_arr = np.array(effect_frames[i], dtype=np.float32)
        # Extract only the effect delta (what changed from the original)
        delta = eff_arr - ref
        # Apply delta to base frames (additive blend, 40% strength)
        composited = base_arr + delta * 0.4
        result.append(Image.fromarray(np.clip(composited, 0, 255).astype(np.uint8)))
    return result


# ─── Router animație ──────────────────────────────────────────────────────────
def _animate_artistic(
    img: Image.Image,
    style_id: str,
    subject_type: str = "object",
    animation_mode: str = "life",
    frame_delay: int = 80,
) -> bytes:
    """Animație cinematică - 512px, N_FRAMES frame-uri, frame_delay ms/fr."""
    img = img.resize((512, 512), Image.LANCZOS)

    if animation_mode == "cinemagraph":
        frames = _frames_cinemagraph(img, subject_type, style_id)
    elif animation_mode == "blink":
        frames = _frames_blink(img, style_id)
        if len(frames) < 2:  # fallback if no face detected
            frames = _frames_life(img, subject_type, style_id)
    elif animation_mode in ("steam", "wind", "glisten", "sweep"):
        # Composit: stil-specific base animation + overlay effect
        # Base = animatia unica a stilului (CMYK shift pt Warhol, wave pt Hokusai, etc.)
        base_frames = _frames_style_visual(img, style_id)
        # Overlay = efectul generic ales de user
        if animation_mode == "steam":
            frames = _overlay_effect(base_frames, _frames_steam(img))
        elif animation_mode == "wind":
            frames = _overlay_effect(base_frames, _frames_wind(img))
        elif animation_mode == "glisten":
            frames = _overlay_effect(base_frames, _frames_glisten(img))
        else:  # sweep
            frames = _overlay_effect(base_frames, _frames_light_sweep(img))
    else:
        frames = _frames_life(img, subject_type, style_id)

    # Adaugă watermark ScanArt pe fiecare frame
    frames = [_add_watermark(f) for f in frames]

    # 400x400 + 48-color palette, NO dither (cleaner = better compression)
    # Additional trick: 12 frames instead of 16 = 25% smaller
    output_frames = [f.resize((400, 400), Image.LANCZOS) for f in frames[::(max(1, len(frames)//12))]][:12]
    palette_frames = [f.convert("P", palette=Image.ADAPTIVE, colors=48, dither=Image.NONE) for f in output_frames]
    output = io.BytesIO()
    palette_frames[0].save(
        output, format="GIF", save_all=True,
        append_images=palette_frames[1:], loop=0,
        duration=int(frame_delay * (len(frames) / 12)),  # preserve playback duration
        optimize=True,
    )
    return output.getvalue()


def _add_watermark(img: Image.Image) -> Image.Image:
    """Adaugă watermark semi-transparent 'ScanArt' în colțul dreapta-jos."""
    img = img.convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    text = "ScanArt.app"
    font_size = max(10, int(w * 0.030))  # ~12px la 400px — vizibil dar discret

    # Încearcă să folosești un font truetype; fallback la default PIL
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    margin = int(w * 0.025)
    x = w - tw - margin
    y = h - th - margin

    # Umbra (negru semi-transparent)
    draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 120))
    # Text alb semi-transparent
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 160))

    combined = Image.alpha_composite(img, overlay)
    return combined.convert("RGB")


# ─── MOD LIFE: animație naturală per subject ──────────────────────────────────
def _frames_life(img: Image.Image, subject_type: str, style_id: str) -> list:
    """Dispatcher: animație naturală bazată pe subiect + stil vizual."""
    # Animație specifică subiectului
    if subject_type == "face":
        return _frames_blink(img, style_id)
    elif subject_type == "cup":
        return _frames_shimmer(img, style_id)
    elif subject_type == "animal":
        return _frames_animal(img, style_id)
    elif subject_type in ("plant", "flower"):
        return _frames_sway(img, style_id)
    elif subject_type == "food":
        return _frames_glow_pulse(img, style_id)
    else:
        # Animație vizuală per filtru
        return _frames_style_visual(img, style_id)


def _frames_blink(img: Image.Image, style_id: str) -> list:
    """MediaPipe FaceMesh → clipit realist N_FRAMES frame-uri.
    Fallback la _frames_style_visual dacă nu detectează față."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]

    # Detectare față cu MediaPipe
    eye_mask = _detect_eye_mask(arr, h, w)
    if eye_mask is None:
        print("FaceMesh: no face detected, fallback to style visual")
        return _frames_style_visual(img, style_id)

    # 16 frame-uri: 6 open + 1 closing + 2 closed + 1 opening + 6 open
    blink_curve = (
        [0.0] * 6 +          # open
        [0.7] +              # closing
        [1.0, 1.0] +         # closed
        [0.7] +              # opening
        [0.0] * 6            # open
    )
    # Culoarea pleoapelor = media fruntii (top 15% din imagine)
    forehead = arr[:int(h * 0.15)]
    lid_color = forehead.mean(axis=(0, 1))

    frames = []
    for alpha in blink_curve:
        f = arr.copy()
        if alpha > 0.0:
            # Blend zona ochilor cu culoarea pleoapelor
            blend = eye_mask[:, :, np.newaxis] * alpha
            f = f * (1 - blend) + lid_color * blend
            # Linie subtire pentru pleoapa inchisa
            if alpha >= 0.8:
                rows = np.where(eye_mask.max(axis=1) > 0.3)[0]
                if len(rows) > 0:
                    mid_row = rows[len(rows) // 2]
                    lh = max(1, int(eye_mask.shape[0] * 0.008))
                    f[mid_row:mid_row + lh] *= 0.3
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _detect_eye_mask(arr: np.ndarray, h: int, w: int) -> np.ndarray | None:
    """Detectare ochi cu MediaPipe FaceMesh. Returns float32 mask (h,w) sau None."""
    try:
        import mediapipe as mp
        import cv2

        mp_face_mesh = mp.solutions.face_mesh
        img_uint8 = arr.astype(np.uint8)
        img_bgr = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2BGR)

        with mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.3,
        ) as face_mesh:
            results = face_mesh.process(img_bgr)

        if not results.multi_face_landmarks:
            return None

        landmarks = results.multi_face_landmarks[0].landmark

        # Landmark-uri ochi (stâng + drept)
        LEFT_EYE  = [33, 160, 158, 133, 153, 144, 163, 7]
        RIGHT_EYE = [362, 385, 387, 263, 373, 380, 384, 398]

        mask = np.zeros((h, w), dtype=np.float32)
        for eye_pts in [LEFT_EYE, RIGHT_EYE]:
            xs = [int(landmarks[i].x * w) for i in eye_pts]
            ys = [int(landmarks[i].y * h) for i in eye_pts]
            cx, cy = sum(xs) // len(xs), sum(ys) // len(ys)
            rx = max(int((max(xs) - min(xs)) * 0.8), 10)
            ry = max(int((max(ys) - min(ys)) * 1.6), 6)
            # Elipsă Gaussian blur pentru tranziție naturală
            Y, X = np.ogrid[:h, :w]
            ellipse = np.clip(1.0 - ((X - cx) / rx) ** 2 - ((Y - cy) / ry) ** 2, 0, 1)
            mask = np.maximum(mask, ellipse)

        # Blur pentru margini moi
        from scipy.ndimage import gaussian_filter
        mask = gaussian_filter(mask, sigma=3)
        return mask

    except Exception as e:
        print(f"MediaPipe eye detection failed: {e}")
        return None


def _frames_shimmer(img: Image.Image, style_id: str) -> list:
    """Shimmer + abur pentru cup/drink - 16 frame-uri."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # Highlight circular pe suprafata (shimmer)
        cx = int(w * (0.45 + 0.08 * math.sin(phase)))
        cy = int(h * 0.22)
        rx, ry = int(w * 0.12), int(h * 0.04)
        Y, X = np.ogrid[:h, :w]
        shimmer_mask = np.clip(1.0 - ((X - cx) / rx) ** 2 - ((Y - cy) / ry) ** 2, 0, 1)
        shimmer_intensity = 0.35 * (0.5 + 0.5 * math.sin(phase))
        f = f + shimmer_mask[:, :, np.newaxis] * shimmer_intensity * 255
        # Linii de abur (3 linii ascendente sinusoidal)
        steam_top = int(h * 0.05)
        steam_bot = int(h * 0.18)
        for k in range(3):
            sx = int(w * (0.35 + k * 0.12 + 0.03 * math.sin(phase + k * 1.2)))
            for sy in range(steam_top, steam_bot):
                px = sx + int(4 * math.sin((sy - steam_top) * 0.4 + phase + k))
                px = np.clip(px, 0, w - 1)
                alpha = 0.15 * (1 - (sy - steam_top) / (steam_bot - steam_top))
                if 0 <= sy < h:
                    f[sy, px] = np.clip(f[sy, px] + alpha * 255, 0, 255)
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_animal(img: Image.Image, style_id: str) -> list:
    """Urechi + coada animate - 16 frame-uri."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # Zona superioara 20% (urechi) - warp sinusoidal
        ear_h = int(h * 0.20)
        shift = int(5 * math.sin(phase))
        f[:ear_h] = np.roll(f[:ear_h], shift, axis=1)
        # Zona dreapta-jos 15% (coada) - arc rotatie
        tail_h = int(h * 0.15)
        tail_w = int(w * 0.20)
        tail_shift = int(8 * math.sin(phase * 1.5))
        f[h - tail_h:, w - tail_w:] = np.roll(
            f[h - tail_h:, w - tail_w:], tail_shift, axis=0
        )
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_sway(img: Image.Image, style_id: str) -> list:
    """Legănat natural pentru plante - 16 frame-uri cu scipy."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    try:
        from scipy.ndimage import map_coordinates
    except ImportError:
        return _frames_style_visual(img, style_id)

    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        # Amplitudine scade de sus (varf ±10px) la baza (0px)
        amplitude = 10.0 * (1 - yc / h)
        dx = amplitude * np.sin(phase + yc * 0.03)
        src_x = np.clip(xc + dx, 0, w - 1)
        src_y = yc
        f = np.zeros_like(arr)
        for ch in range(3):
            f[:, :, ch] = map_coordinates(arr[:, :, ch], [src_y, src_x], order=1, mode='reflect')
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_glow_pulse(img: Image.Image, style_id: str) -> list:
    """Glow pulse radial pentru food - 16 frame-uri."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = np.sqrt((xc - w / 2) ** 2 + (yc - h / 2) ** 2)
    max_dist = math.sqrt((w / 2) ** 2 + (h / 2) ** 2)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # Radial glow pulse
        glow_factor = 1.0 + 0.12 * math.sin(phase)
        radial_weight = np.clip(1.0 - dist / max_dist, 0, 1)[:, :, np.newaxis]
        f = f * (1.0 + (glow_factor - 1.0) * radial_weight)
        # Shimmer pe suprafata
        shimmer = 0.08 * np.sin(phase + dist * 0.08)[:, :, np.newaxis]
        f = f * (1 + shimmer)
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_meiji_print(img: Image.Image) -> list:
    """Bokashi gradation breathing + progressive ink contour reveal."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    gray = np.mean(arr, axis=2)
    edges = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1])) + np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
    edge_mask = (edges > 15).astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        result = arr.copy()
        # Bokashi breathing — edge gradation expands/contracts
        blur_radius = 2 + int(3 * math.sin(2 * math.pi * t))
        blurred = np.array(Image.fromarray(arr.astype(np.uint8)).filter(ImageFilter.GaussianBlur(max(1, blur_radius))), dtype=np.float32)
        bokashi = 0.3 + 0.2 * math.sin(2 * math.pi * t)
        result = result * (1 - bokashi) + blurred * bokashi
        # Ink contour progressive reveal
        reveal = (i + 1) / N_FRAMES
        ink_alpha = np.minimum(edge_mask * reveal * 2, 1.0)
        for c in range(3):
            result[:, :, c] = result[:, :, c] * (1 - ink_alpha) + 20 * ink_alpha
        # Washi paper warmth
        result[:, :, 0] *= 1.03
        result[:, :, 2] *= 0.95
        frames.append(Image.fromarray(np.clip(result, 0, 255).astype(np.uint8)))
    return frames


def _frames_persian_mini(img: Image.Image) -> list:
    """Gold leaf angle glint + jewel saturation pulse."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    brightness = np.mean(arr, axis=2)
    gold_mask = (brightness > 150).astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        result = arr.copy()
        # Gold glint sweeps diagonally
        for y in range(h):
            for x in range(0, w, 4):
                diag = (x + y) / (w + h)
                glint = gold_mask[y, x] * 60 * max(0, math.sin(2 * math.pi * (t - diag * 2)))
                result[y, x:min(x+4, w), :] += glint
        # Jewel saturation pulse — saturate reds and blues
        sat = 1.1 + 0.3 * math.sin(2 * math.pi * t + 0.5)
        mean = np.mean(result, axis=2, keepdims=True)
        result = mean + (result - mean) * sat
        frames.append(Image.fromarray(np.clip(result, 0, 255).astype(np.uint8)))
    return frames


def _frames_mughal_mini(img: Image.Image) -> list:
    """Hatching strokes breathing + border bloom."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        result = arr.copy()
        # Hatching breathing — fine horizontal lines modulate
        for y in range(0, h, 3):
            intensity = 0.85 + 0.3 * math.sin(2 * math.pi * t + y * 0.1)
            result[y, :, :] *= intensity
        # Border bloom — edges of frame brighten progressively
        border = 30
        bloom = 0.5 + 0.5 * math.sin(2 * math.pi * t)
        result[:border, :, :] *= (0.8 + 0.4 * bloom)
        result[-border:, :, :] *= (0.8 + 0.4 * bloom)
        result[:, :border, :] *= (0.8 + 0.4 * bloom)
        result[:, -border:, :] *= (0.8 + 0.4 * bloom)
        frames.append(Image.fromarray(np.clip(result, 0, 255).astype(np.uint8)))
    return frames


def _frames_preraphaelite(img: Image.Image) -> list:
    """Wet white ground luminosity pulse + sequential element illumination."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        result = arr.copy()
        # Wet ground luminosity pulse — white ground beneath paint glows
        luminosity = 1.0 + 0.15 * math.sin(2 * math.pi * t)
        result = result * luminosity
        # Saturation intensify — jewel colors pulse
        mean = np.mean(result, axis=2, keepdims=True)
        sat = 1.1 + 0.2 * math.sin(2 * math.pi * t + 1.0)
        result = mean + (result - mean) * sat
        # Sequential illumination — scan from top to bottom
        scan_y = int(h * t)
        band = 40
        y0, y1 = max(0, scan_y - band), min(h, scan_y + band)
        result[y0:y1] *= 1.15
        frames.append(Image.fromarray(np.clip(result, 0, 255).astype(np.uint8)))
    return frames


def _frames_swiss_poster(img: Image.Image) -> list:
    """Halftone screen rotation + grid column phase shift."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    frames = []
    cols = 6
    col_w = w // cols
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        result = arr.copy()
        # Grid columns shift phase
        for c in range(cols):
            phase = c * 0.5
            shift_y = int(3 * math.sin(2 * math.pi * t + phase))
            x0, x1 = c * col_w, (c + 1) * col_w
            result[:, x0:x1, :] = np.roll(result[:, x0:x1, :], shift_y, axis=0)
        # Halftone dot simulation — periodic brightness modulation
        dot_period = 6
        for y in range(0, h, dot_period):
            for x in range(0, w, dot_period):
                angle = 2 * math.pi * t * 0.3
                rx = int(x * math.cos(angle) - y * math.sin(angle)) % dot_period
                ry = int(x * math.sin(angle) + y * math.cos(angle)) % dot_period
                if rx < dot_period // 2 and ry < dot_period // 2:
                    ey, ex = min(y + dot_period, h), min(x + dot_period, w)
                    result[y:ey, x:ex] *= 1.1
        frames.append(Image.fromarray(np.clip(result, 0, 255).astype(np.uint8)))
    return frames


# ─── Animații vizuale per filtru (mod "life" fallback + style flavor) ─────────
def _frames_style_visual(img: Image.Image, style_id: str) -> list:
    """Animație vizuală specifică filtrului - 16 frame-uri. Toate 30 stiluri acoperite."""
    dispatch = {
        # Original 10
        "warhol":        _frames_warhol,
        "hokusai":       _frames_hokusai,
        "klimt":         _frames_klimt,
        "ghibli":        _frames_ghibli,
        "banksy":        _frames_banksy,
        "dali":          _frames_dali,
        "vangogh":       _frames_vangogh,
        "baroque":       _frames_baroque,
        "mondrian":      _frames_mondrian,
        "mucha":         _frames_mucha,
        # Wave/fluid family (use hokusai-style wave or dali-melt)
        "meiji_print":   _frames_meiji_print,    # bokashi gradation + ink reveal
        "persian_mini":  _frames_persian_mini,   # gold glint + jewel saturation
        "mughal_mini":   _frames_mughal_mini,    # hatching breathing + border bloom
        "byzantine":     _frames_byzantine,      # mosaic tessera flicker
        "preraphaelite": _frames_preraphaelite,   # wet ground luminosity + scan
        # Edge/energy family
        "expressionism": _frames_expressionism,  # edge vibration
        "futurism":      _frames_futurism,       # speed lines + motion blur
        "constructivism":_frames_constructivism, # geometric rotation
        # Grid/geometric family
        "swiss_poster":  _frames_swiss_poster,    # halftone + column phase shift
        "brutalist":     _frames_brutalist,      # concrete grain + shadow shift
        # Texture/grain family
        "pointillism":   _frames_pointillism,    # dots shimmer
        "risograph":     _frames_risograph,      # layer misregistration
        "woodcut":       _frames_woodcut,        # ink bleed
        "ligne_claire":  _frames_ligne_claire,   # line breathing
        "daguerreotype": _frames_daguerreotype,  # silver shimmer + vignette pulse
        # Digital/modern family
        "infrared":      _frames_infrared,       # heat map shift
        "lomography":    _frames_lomography,     # light leak travel
        "cyberpunk":     _frames_cyberpunk,      # scanline + neon flicker
        "wpa_poster":    _frames_wpa_poster,     # flag wave
        "zine_collage":  _frames_zine_collage,   # cut pieces jitter
    }
    fn = dispatch.get(style_id, _frames_dali)
    return fn(img)


def _frames_warhol(img: Image.Image) -> list:
    """Warhol CMYK registration shift — canale RGB se deplasează ciclic ca o imprimare offset."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    # Posterize mai întâi (reduce la 4-5 nivele per canal ca silkscreen)
    levels = 5
    posterized = np.floor(arr / (256 / levels)) * (256 / levels)
    # 4 tint-uri CMYK care se ciclează
    tints = [
        np.array([255, 0, 128], dtype=np.float32),   # magenta
        np.array([0, 220, 255], dtype=np.float32),    # cyan
        np.array([255, 255, 0], dtype=np.float32),    # yellow
        np.array([100, 255, 50], dtype=np.float32),   # lime
    ]
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = posterized.copy()
        # Registration offset — fiecare canal RGB se shifteaza diferit (ca print misalignment)
        shift_r = int(2 * math.sin(phase))
        shift_g = int(2 * math.sin(phase + 2.1))
        shift_b = int(2 * math.cos(phase))
        f[:, :, 0] = np.roll(f[:, :, 0], shift_r, axis=1)  # R shift horizontal
        f[:, :, 1] = np.roll(f[:, :, 1], shift_g, axis=0)  # G shift vertical
        f[:, :, 2] = np.roll(f[:, :, 2], shift_b, axis=1)  # B shift horizontal
        # Color tint ciclic (se schimbă dominant-ul)
        tint_idx = i % len(tints)
        tint = tints[tint_idx]
        tint_alpha = 0.15 + 0.1 * abs(math.sin(phase * 2))
        f = f * (1 - tint_alpha) + tint * tint_alpha
        # High contrast silkscreen
        f = (f - 80) * 1.6 + 80
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_hokusai(img: Image.Image) -> list:
    """Wave sinusoidal de jos în sus (amplitudine 12px, frecvență) - 24fr."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        # Unda dinspre baza catre varf
        wave_amp = 12.0 * (yc / h)  # amplitudine creste spre baza
        dx = wave_amp * np.sin(2 * math.pi * xc / w * 3 + phase)
        src_x = np.clip(xc + dx, 0, w - 1).astype(int)
        src_y = yc.astype(int)
        f = arr[src_y, src_x].copy().astype(np.float32)
        # Albastru intens Hokusai
        f[:, :, 2] *= 1.0 + 0.15 * math.sin(phase)
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_klimt(img: Image.Image) -> list:
    """Klimt: tessera tiles micro-rotation + gold shimmer wave traversing the image."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    gold = np.array([212, 175, 55], dtype=np.float32)
    # Divide into mosaic tiles (10x10 grid)
    tile_h, tile_w = h // 10, w // 10
    try:
        from scipy.ndimage import rotate as scipy_rotate
        has_scipy = True
    except ImportError:
        has_scipy = False
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # Gold shimmer wave that travels diagonally across the image
        for ty in range(10):
            for tx in range(10):
                y0, y1 = ty * tile_h, min((ty + 1) * tile_h, h)
                x0, x1 = tx * tile_w, min((tx + 1) * tile_w, w)
                tile = f[y0:y1, x0:x1].copy()
                # Each tile has a phase offset based on position (wave effect)
                tile_phase = phase + (ty + tx) * 0.5
                # Micro-rotation per tile (±1.5 degrees)
                if has_scipy and tile.shape[0] > 2 and tile.shape[1] > 2:
                    angle = 1.5 * math.sin(tile_phase)
                    th, tw_t = tile.shape[:2]
                    rotated = scipy_rotate(tile, angle, reshape=False, order=1, mode='reflect')
                    f[y0:y1, x0:x1] = rotated[:y1-y0, :x1-x0]
                # Gold tint intensity varies per tile in wave
                gold_alpha = 0.12 * max(0, math.sin(tile_phase))
                f[y0:y1, x0:x1] = f[y0:y1, x0:x1] * (1 - gold_alpha) + gold * gold_alpha
        # Subtle overall warm pulse
        f[:, :, 0] *= 1.0 + 0.04 * math.sin(phase)
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_ghibli(img: Image.Image) -> list:
    """Ken Burns zoom 1.0→1.03 + subtle sway ±2px - 16fr."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    vx, vy = np.linspace(-1, 1, w), np.linspace(-1, 1, h)
    xg, yg = np.meshgrid(vx, vy)
    vignette = np.clip(1.0 - 0.4 * (xg ** 2 + yg ** 2), 0.4, 1.0)[:, :, np.newaxis]
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        # Ken Burns lent
        zoom = 1.0 + 0.03 * t  # reduced from 0.08 — barely perceptible zoom
        pan_x = int(w * 0.04 * math.sin(t * math.pi))
        pan_y = int(h * 0.02 * (1 - math.cos(t * math.pi)))
        nw, nh = int(w * zoom), int(h * zoom)
        tmp = Image.fromarray(arr.astype(np.uint8)).resize((nw, nh), Image.LANCZOS)
        lx = max(0, min((nw - w) // 2 + pan_x, nw - w))
        ty = max(0, min((nh - h) // 2 + pan_y, nh - h))
        f = np.array(tmp.crop((lx, ty, lx + w, ty + h)), dtype=np.float32)
        # Warm shimmer
        f[:, :, 0] *= 1.0 + 0.06 * math.sin(t * 2 * math.pi)
        f[:, :, 1] *= 1.0 + 0.04 * math.sin(t * 2 * math.pi + 0.5)
        # Soft glow
        glow_img = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
        glow = np.array(glow_img, dtype=np.float32)
        f = f * 0.85 + glow * 0.15
        f *= vignette
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_banksy(img: Image.Image) -> list:
    """Banksy: paint drip (picături curg jos) + stencil edge breathing + grain."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    rng = np.random.default_rng(42)
    # Pre-compute: high-contrast B&W stencil base
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    stencil = np.clip((gray - 128) * 2.0 + 128, 0, 255)
    # Detect accent color zone (roșu)
    accent_mask = (arr[:, :, 0] > arr[:, :, 1] + 40).astype(np.float32)
    # Pre-compute drip columns (5-8 paint drips la poziții random)
    n_drips = 6
    drip_x = rng.integers(int(w * 0.15), int(w * 0.85), n_drips)
    drip_speed = rng.uniform(1.5, 4.0, n_drips)  # pixeli/frame
    drip_width = rng.integers(2, 5, n_drips)

    try:
        from scipy.ndimage import binary_dilation, binary_erosion
        has_scipy = True
    except ImportError:
        has_scipy = False

    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        # Stencil breathing: dilate/erode ciclic
        if has_scipy:
            breath = math.sin(phase)
            if breath > 0.3:
                mask = stencil > 128
                expanded = binary_dilation(mask, iterations=1)
                f_gray = np.where(expanded, stencil + 20, stencil - 20)
            elif breath < -0.3:
                mask = stencil > 128
                shrunk = binary_erosion(mask, iterations=1)
                f_gray = np.where(shrunk, stencil + 20, stencil - 20)
            else:
                f_gray = stencil.copy()
        else:
            f_gray = stencil.copy()
        f_gray = np.clip(f_gray, 0, 255)
        # Build RGB from stencil
        f = np.stack([f_gray, f_gray, f_gray], axis=-1).astype(np.float32)
        # Re-apply accent color
        f[:, :, 0] = f_gray * (1 - accent_mask * 0.6) + arr[:, :, 0] * accent_mask * 0.6
        # Paint drips flowing down
        for d in range(n_drips):
            dx = drip_x[d]
            drip_len = int(12 + drip_speed[d] * i)
            drip_start = max(0, int(h * 0.3) - 5)
            drip_end = min(h, drip_start + drip_len)
            dw = drip_width[d]
            x0 = max(0, dx - dw)
            x1 = min(w, dx + dw)
            # Drip gets thinner toward bottom
            for row in range(drip_start, drip_end):
                taper = 1.0 - (row - drip_start) / max(1, drip_end - drip_start)
                tw = max(1, int(dw * taper))
                cx0 = max(0, dx - tw)
                cx1 = min(w, dx + tw)
                f[row, cx0:cx1] = f[row, cx0:cx1] * 0.15  # dark drip
        # Grain noise
        noise = rng.normal(0, 6, (h, w, 3))
        f = f + noise
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_dali(img: Image.Image) -> list:
    """Wave fluid lent + color rotation - 24fr."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        # Distorsiune fluid Dali
        dx = (14 * np.sin(3 * math.pi * yc / h + phase)).astype(int)
        dy = (10 * np.cos(3 * math.pi * xc / w + phase * 0.7)).astype(int)
        sx = np.clip(xc.astype(int) + dx, 0, w - 1)
        sy = np.clip(yc.astype(int) + dy, 0, h - 1)
        f = arr[sy, sx].copy().astype(np.float32)
        # Color rotation subtila
        mix = 0.18 * abs(math.sin(phase))
        r, b = f[:, :, 0].copy(), f[:, :, 2].copy()
        f[:, :, 0] = r * (1 - mix) + b * mix
        f[:, :, 2] = b * (1 - mix) + r * mix
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_vangogh(img: Image.Image) -> list:
    """Swirl spiral simulat prin warp + brushstroke texture - 24fr."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    cy, cx = h / 2, w / 2
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = np.sqrt((xc - cx) ** 2 + (yc - cy) ** 2)
    angle = np.arctan2(yc - cy, xc - cx)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        # Swirl: subtle brushstroke motion at edges only (not whole image)
        swirl_strength = 0.08 * math.sin(phase)  # reduced from 0.25 — subtle, not chaotic
        swirl_angle = angle + swirl_strength * np.exp(-dist / (h * 0.25))
        src_x = np.clip(cx + dist * np.cos(swirl_angle), 0, w - 1).astype(int)
        src_y = np.clip(cy + dist * np.sin(swirl_angle), 0, h - 1).astype(int)
        f = arr[src_y, src_x].copy().astype(np.float32)
        # Saturatie ridicata Van Gogh
        gray = 0.299 * f[:, :, 0] + 0.587 * f[:, :, 1] + 0.114 * f[:, :, 2]
        sat = 1.3 + 0.1 * math.sin(phase)
        f = gray[:, :, np.newaxis] + (f - gray[:, :, np.newaxis]) * sat
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_baroque(img: Image.Image) -> list:
    """Baroque: candlelight source moves across the scene, casting shifting shadows."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # Light source position oscillates (candle flicker)
        light_x = w * (0.35 + 0.15 * math.sin(phase))
        light_y = h * (0.25 + 0.08 * math.cos(phase * 1.3))
        # Distance from light source
        dist = np.sqrt((xc - light_x) ** 2 + (yc - light_y) ** 2)
        max_dist = math.sqrt(w ** 2 + h ** 2)
        # Light falloff (inverse square-ish, clamped)
        light_intensity = np.clip(1.0 - (dist / (max_dist * 0.5)) ** 1.5, 0.05, 1.0)
        # Flicker randomness
        flicker = 1.0 + 0.12 * math.sin(phase) + 0.05 * math.sin(phase * 3.7)
        light_map = (light_intensity * flicker)[:, :, np.newaxis]
        f = f * light_map
        # Warm candle tone (more warmth near light source)
        warmth = light_intensity[:, :, np.newaxis] * 0.08
        f[:, :, 0] = f[:, :, 0] + warmth[:, :, 0] * 40  # red
        f[:, :, 1] = f[:, :, 1] + warmth[:, :, 0] * 15  # slight green
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_mondrian(img: Image.Image) -> list:
    """Mondrian: grid lines shift positions + color blocks grow/shrink rhythmically."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    mondrian_colors = [
        np.array([220, 20, 20], dtype=np.float32),
        np.array([20, 60, 200], dtype=np.float32),
        np.array([240, 210, 20], dtype=np.float32),
        np.array([240, 240, 240], dtype=np.float32),
    ]
    # Base grid positions (will shift)
    base_y = [0, int(h * 0.22), int(h * 0.48), int(h * 0.73), h]
    base_x = [0, int(w * 0.30), int(w * 0.55), int(w * 0.80), w]
    rng = np.random.default_rng(77)
    cell_colors = rng.integers(0, len(mondrian_colors), (4, 4))

    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # Grid lines shift position (±3px oscillation)
        shift_y = [0] + [int(3 * math.sin(phase + k * 1.2)) for k in range(3)] + [0]
        shift_x = [0] + [int(3 * math.cos(phase + k * 0.9)) for k in range(3)] + [0]
        cells_y = [max(0, min(h, base_y[k] + shift_y[k])) for k in range(5)]
        cells_x = [max(0, min(w, base_x[k] + shift_x[k])) for k in range(5)]
        # Color overlay per cell with phase-shifted intensity
        for cy in range(4):
            for cx in range(4):
                y0, y1 = cells_y[cy], cells_y[cy + 1]
                x0, x1 = cells_x[cx], cells_x[cx + 1]
                if y1 <= y0 or x1 <= x0:
                    continue
                color = mondrian_colors[cell_colors[cy, cx]]
                cell_phase = phase + (cy + cx) * 0.8
                alpha = 0.20 + 0.15 * max(0, math.sin(cell_phase))
                f[y0:y1, x0:x1] = f[y0:y1, x0:x1] * (1 - alpha) + color * alpha
        # Draw thick black grid lines at shifted positions
        line_w = 4
        for gy in cells_y[1:-1]:
            f[max(0, gy - line_w // 2):min(h, gy + line_w // 2)] *= 0.05
        for gx in cells_x[1:-1]:
            f[:, max(0, gx - line_w // 2):min(w, gx + line_w // 2)] *= 0.05
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_mucha(img: Image.Image) -> list:
    """Mucha: slow circular halo rotation + vine tendrils growing from edges."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    mucha_pastel = np.array([245, 215, 195], dtype=np.float32)
    try:
        from scipy.ndimage import rotate as scipy_rotate
        has_scipy = True
    except ImportError:
        has_scipy = False

    # Create a border halo mask (ring around center)
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = np.sqrt((xc - w / 2) ** 2 + (yc - h / 2) ** 2)
    max_r = min(h, w) / 2
    # Halo ring between 70% and 95% of radius
    halo_mask = np.clip(1.0 - abs(dist / max_r - 0.82) / 0.13, 0, 1)

    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # Rotate the halo pattern slowly
        if has_scipy:
            rotation_angle = 8 * math.sin(phase)  # ±8 degrees
            rotated_halo = scipy_rotate(halo_mask, rotation_angle, reshape=False, order=1, mode='constant')
        else:
            rotated_halo = halo_mask
        # Apply pastel halo
        halo_alpha = rotated_halo[:, :, np.newaxis] * (0.18 + 0.08 * math.sin(phase))
        f = f * (1 - halo_alpha) + mucha_pastel * halo_alpha * 255 / 255
        # Vine growth from edges: sinusoidal tendrils that extend inward
        for vine in range(4):
            vine_phase = phase + vine * math.pi / 2
            # Vine origin at edge
            if vine == 0:  # left
                vx = int(6 + 3 * math.sin(vine_phase))
                for row in range(0, h, 8):
                    length = int(15 + 10 * abs(math.sin(vine_phase + row * 0.05)))
                    for px in range(vx, min(w, vx + length)):
                        py = row + int(3 * math.sin(px * 0.3 + vine_phase))
                        if 0 <= py < h:
                            f[py, px] = f[py, px] * 0.6 + mucha_pastel * 0.4
            elif vine == 1:  # right
                vx = w - 7 - int(3 * math.sin(vine_phase))
                for row in range(0, h, 8):
                    length = int(15 + 10 * abs(math.sin(vine_phase + row * 0.05)))
                    for px in range(max(0, vx - length), vx):
                        py = row + int(3 * math.sin(px * 0.3 + vine_phase))
                        if 0 <= py < h:
                            f[py, px] = f[py, px] * 0.6 + mucha_pastel * 0.4
        # Soft glow
        glow_img = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4))
        glow = np.array(glow_img, dtype=np.float32)
        f = f * 0.85 + glow * 0.15
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


# ─── NEW STYLE ANIMATIONS (20 new styles) ────────────────────────────────────

def _frames_byzantine(img: Image.Image) -> list:
    """Byzantine: mosaic tessera flicker — individual tiles brighten/dim like candlelit mosaics."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    gold = np.array([200, 170, 50], dtype=np.float32)
    tile_size = max(8, h // 20)
    rng = np.random.default_rng(42)
    tile_phases = rng.uniform(0, 2 * math.pi, (h // tile_size + 1, w // tile_size + 1))
    frames = []
    for i in range(N_FRAMES):
        phase = (i / N_FRAMES) * 2 * math.pi
        f = arr.copy()
        for ty in range(0, h, tile_size):
            for tx in range(0, w, tile_size):
                tp = tile_phases[ty // tile_size, tx // tile_size]
                flicker = 0.15 * math.sin(phase + tp)
                y1, x1 = min(ty + tile_size, h), min(tx + tile_size, w)
                f[ty:y1, tx:x1] = f[ty:y1, tx:x1] * (1 + flicker) + gold * max(0, flicker) * 0.3
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_expressionism(img: Image.Image) -> list:
    """Expressionism: edges vibrate angularly — contours shake, mass stays stable."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    # Edge detection via gradient magnitude
    gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
    gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    edges = np.clip((gy + gx) / 255.0, 0, 1)
    rng = np.random.default_rng(99)
    frames = []
    for i in range(N_FRAMES):
        phase = (i / N_FRAMES) * 2 * math.pi
        f = arr.copy()
        # Jitter only at edges (edge mask controls amplitude)
        jitter_x = (edges * 4 * np.sin(phase + rng.uniform(-1, 1, (h, w)))).astype(np.intp)
        jitter_y = (edges * 3 * np.cos(phase * 1.3 + rng.uniform(-1, 1, (h, w)))).astype(np.intp)
        yc, xc = np.mgrid[0:h, 0:w]
        sx = np.clip(xc + jitter_x, 0, w - 1)
        sy = np.clip(yc + jitter_y, 0, h - 1)
        f = arr[sy, sx]
        # Boost saturation
        g = 0.299 * f[:, :, 0] + 0.587 * f[:, :, 1] + 0.114 * f[:, :, 2]
        f = g[:, :, np.newaxis] + (f - g[:, :, np.newaxis]) * 1.4
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_futurism(img: Image.Image) -> list:
    """Futurism: diagonal motion blur streaks — speed lines emanating from center."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = np.sqrt((xc - w / 2) ** 2 + (yc - h / 2) ** 2)
    angle = np.arctan2(yc - h / 2, xc - w / 2)
    max_dist = np.sqrt((w / 2) ** 2 + (h / 2) ** 2)
    frames = []
    for i in range(N_FRAMES):
        phase = (i / N_FRAMES) * 2 * math.pi
        f = arr.copy()
        # Radial motion blur: shift pixels outward from center
        blur_amount = (dist / max_dist) * 8 * (0.5 + 0.5 * math.sin(phase))
        dx = (blur_amount * np.cos(angle)).astype(int)
        dy = (blur_amount * np.sin(angle)).astype(int)
        sx = np.clip(xc.astype(int) + dx, 0, w - 1)
        sy = np.clip(yc.astype(int) + dy, 0, h - 1)
        blurred = arr[sy, sx]
        # Blend: center stays sharp, edges get motion blur
        center_mask = np.clip(1.0 - dist / (max_dist * 0.4), 0, 1)[:, :, np.newaxis]
        f = f * center_mask + blurred * (1 - center_mask)
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_constructivism(img: Image.Image) -> list:
    """Constructivism: geometric elements rotate on 45° axes + red planes advance/recede."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        result = arr.copy()
        # Red planes advance/recede
        red_mask = arr[:, :, 0] > np.maximum(arr[:, :, 1], arr[:, :, 2]) + 20
        intensity = 0.7 + 0.6 * math.sin(2 * math.pi * t)
        result[red_mask, 0] = np.clip(result[red_mask, 0] * intensity, 0, 255)
        # Diagonal shear on 45° — shift rows proportional to y
        angle_shift = int(4 * math.sin(2 * math.pi * t * 0.5))
        for y in range(h):
            shift = int(angle_shift * (y - h//2) / h)
            result[y] = np.roll(result[y], shift, axis=0)
        # Desaturate non-red areas toward black
        non_red = ~red_mask
        result[non_red] *= (0.6 + 0.2 * math.sin(2 * math.pi * t + 1))
        frames.append(Image.fromarray(np.clip(result, 0, 255).astype(np.uint8)))
    return frames


def _frames_brutalist(img: Image.Image) -> list:
    """Brutalist: directional shadow sweep + concrete grain crawl."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    gray = np.mean(arr, axis=2)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        result = arr.copy()
        # Shadow sweep: light moves left→right
        light_x = 0.2 + 0.6 * t
        for x in range(w):
            dist = abs(x / w - light_x)
            shadow = max(0.4, 1.0 - dist * 1.5)
            result[:, x, :] *= shadow
        # Directional grain crawl
        offset = int(t * 20) % h
        noise = np.random.RandomState(42).randint(-8, 8, (h, w)).astype(np.float32)
        noise = np.roll(noise, offset, axis=0)
        for c in range(3):
            result[:, :, c] += noise
        # Desaturate
        result = result * 0.7 + np.stack([gray]*3, axis=-1) * 0.3
        frames.append(Image.fromarray(np.clip(result, 0, 255).astype(np.uint8)))
    return frames


def _frames_pointillism(img: Image.Image) -> list:
    """Pointillism: individual dots shimmer warm↔cool with diagonal phase.
    Simulates changing light causing optical color mix to shift per dot."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    dot_size = 5  # match _style_pointillism grid
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        result = arr.copy()
        for y in range(0, h - dot_size, dot_size):
            for x in range(0, w - dot_size, dot_size):
                gy, gx = y // dot_size, x // dot_size
                # Diagonal wave: phase propagates from top-left
                phase = (gy + gx) * 0.35
                shift = 0.08 * math.sin(2 * math.pi * t + phase)
                y0, y1 = y, min(y + dot_size, h)
                x0, x1 = x, min(x + dot_size, w)
                # Warm↔cool shift per dot
                result[y0:y1, x0:x1, 0] *= (1.0 + shift)
                result[y0:y1, x0:x1, 2] *= (1.0 - shift)
                bright = 1.0 + 0.06 * math.sin(2 * math.pi * t + phase * 1.3)
                result[y0:y1, x0:x1, 1] *= bright
        frames.append(Image.fromarray(np.clip(result, 0, 255).astype(np.uint8)))
    return frames


def _frames_risograph(img: Image.Image) -> list:
    """Risograph: color layer misregistration — CMYK channels drift independently."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    frames = []
    for i in range(N_FRAMES):
        phase = (i / N_FRAMES) * 2 * math.pi
        f = arr.copy()
        # Each channel shifts independently (riso misregistration)
        sr = int(3 * math.sin(phase))
        sg = int(3 * math.sin(phase + 2.1))
        sb = int(3 * math.cos(phase + 1.0))
        f[:, :, 0] = np.roll(arr[:, :, 0], (sr, sg), axis=(0, 1))
        f[:, :, 1] = np.roll(arr[:, :, 1], (-sg, sr), axis=(0, 1))
        f[:, :, 2] = np.roll(arr[:, :, 2], (sb, -sr), axis=(0, 1))
        # Paper grain texture
        grain = np.random.default_rng(i).normal(0, 4, (h, w, 1))
        f = f + grain
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_woodcut(img: Image.Image) -> list:
    """Woodcut: ink bleed expanding from dark areas — lines thicken/thin cyclically."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    dark_mask = (gray < 100).astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        phase = (i / N_FRAMES) * 2 * math.pi
        f = arr.copy()
        # Ink spread: dilate dark areas cyclically
        spread = int(1 + abs(math.sin(phase)) * 2)
        from PIL import ImageFilter as IF
        dark_img = Image.fromarray((dark_mask * 255).astype(np.uint8))
        for _ in range(spread):
            dark_img = dark_img.filter(IF.MaxFilter(3))
        expanded_dark = np.array(dark_img, dtype=np.float32) / 255.0
        # Apply ink bleed
        f = f * (1 - expanded_dark[:, :, np.newaxis] * 0.7)
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_ligne_claire(img: Image.Image) -> list:
    """Ligne Claire: outlines breathe — line width oscillates."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
    gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    edges = np.clip((gy + gx) / 128.0, 0, 1)
    frames = []
    for i in range(N_FRAMES):
        phase = (i / N_FRAMES) * 2 * math.pi
        f = arr.copy()
        # Lines thicken/thin
        line_strength = 0.5 + 0.3 * math.sin(phase)
        line_overlay = edges[:, :, np.newaxis] * line_strength
        f = f * (1 - line_overlay) + np.array([20, 20, 30]) * line_overlay
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_daguerreotype(img: Image.Image) -> list:
    """Daguerreotype: plate tilt — halation shifts as if tilting silver plate."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    gray = np.mean(arr, axis=2)
    highlights = (gray > 180).astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        # Silver-grey base
        result = np.stack([gray]*3, axis=-1).copy()
        # Halation bloom shifts with viewing angle
        shift_x = int(3 * math.sin(2 * math.pi * t))
        shift_y = int(2 * math.cos(2 * math.pi * t * 0.7))
        shifted_hl = np.roll(np.roll(highlights, shift_x, axis=1), shift_y, axis=0)
        bloom = 40 * shifted_hl
        result += bloom[:, :, np.newaxis]
        # Metallic reflectivity variation
        sweep = 0.5 + 0.5 * np.sin(np.linspace(0, math.pi, w) + 2 * math.pi * t)
        result *= sweep[np.newaxis, :, np.newaxis]
        # Vignette
        Y, X = np.ogrid[:h, :w]
        vig = 1.0 - 0.4 * ((X - w//2)**2 / (w//2)**2 + (Y - h//2)**2 / (h//2)**2)
        result *= vig[:, :, np.newaxis]
        frames.append(Image.fromarray(np.clip(result, 0, 255).astype(np.uint8)))
    return frames


def _frames_infrared(img: Image.Image) -> list:
    """Infrared: false-color heat map that shifts temperature bands."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    frames = []
    for i in range(N_FRAMES):
        phase = (i / N_FRAMES) * 2 * math.pi
        # Shift temperature thresholds
        offset = 30 * math.sin(phase)
        shifted = gray + offset
        # False color mapping
        r = np.clip(shifted * 2.5 - 200, 0, 255)
        g = np.clip(255 - abs(shifted - 128) * 3, 0, 255)
        b = np.clip(300 - shifted * 2.5, 0, 255)
        f = np.stack([r, g, b], axis=-1)
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_lomography(img: Image.Image) -> list:
    """Lomography: light leak that travels across the image diagonally."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # Light leak position travels diagonally
        leak_cx = w * (0.1 + 0.8 * t)
        leak_cy = h * (0.2 + 0.3 * math.sin(phase))
        dist = np.sqrt((xc - leak_cx) ** 2 + (yc - leak_cy) ** 2)
        leak = np.clip(1.0 - dist / (w * 0.35), 0, 1)
        # Warm orange leak
        f[:, :, 0] += leak * 80
        f[:, :, 1] += leak * 30
        # Vignette
        edge_dist = np.sqrt((xc - w / 2) ** 2 + (yc - h / 2) ** 2)
        max_d = np.sqrt((w / 2) ** 2 + (h / 2) ** 2)
        vig = np.clip(1.0 - (edge_dist / max_d) ** 2 * 0.6, 0.2, 1.0)[:, :, np.newaxis]
        f = f * vig
        # Boost saturation
        g = 0.299 * f[:, :, 0] + 0.587 * f[:, :, 1] + 0.114 * f[:, :, 2]
        f = g[:, :, np.newaxis] + (f - g[:, :, np.newaxis]) * 1.4
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_cyberpunk(img: Image.Image) -> list:
    """Cyberpunk: scanlines scroll + neon edge flicker + chromatic aberration."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
    gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    edges = np.clip((gy + gx) / 128.0, 0, 1)
    frames = []
    for i in range(N_FRAMES):
        phase = (i / N_FRAMES) * 2 * math.pi
        f = arr.copy()
        # Scrolling scanlines
        scanline_offset = int(i * 3) % 6
        for row in range(scanline_offset, h, 6):
            f[row:row + 1] *= 0.7
        # Neon edge glow (cyan + magenta)
        flicker = 0.5 + 0.5 * math.sin(phase * 3)
        neon_r = edges * 255 * 0.8 * flicker
        neon_b = edges * 255 * 0.6 * flicker
        f[:, :, 0] = np.clip(f[:, :, 0] + neon_r, 0, 255)
        f[:, :, 2] = np.clip(f[:, :, 2] + neon_b, 0, 255)
        # Chromatic aberration (shift R and B channels)
        shift = int(2 * math.sin(phase))
        f[:, :, 0] = np.roll(f[:, :, 0], shift, axis=1)
        f[:, :, 2] = np.roll(f[:, :, 2], -shift, axis=1)
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_wpa_poster(img: Image.Image) -> list:
    """WPA Poster: flag-like wave on the image — gentle undulation."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        phase = (i / N_FRAMES) * 2 * math.pi
        # Gentle flag wave
        wave = 6 * np.sin(xc / w * 3 * math.pi + phase) * (1 - xc / w * 0.3)
        sx = np.clip(xc, 0, w - 1).astype(int)
        sy = np.clip(yc + wave, 0, h - 1).astype(int)
        f = arr[sy, sx]
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_zine_collage(img: Image.Image) -> list:
    """Zine Collage: 6 torn fragments jitter + rotate individually."""
    arr = np.array(img)
    h, w = arr.shape[:2]
    frames = []
    # Define 6 irregular zones
    zones = [(0, 0, w//2, h//3), (w//2, 0, w, h//3), (0, h//3, w//3, 2*h//3),
             (w//3, h//3, w, 2*h//3), (0, 2*h//3, w//2, h), (w//2, 2*h//3, w, h)]
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        result = np.zeros_like(arr)
        for zi, (x0, y0, x1, y1) in enumerate(zones):
            phase = zi * 1.1
            dx = int(3 * math.sin(2 * math.pi * t + phase))
            dy = int(2 * math.cos(2 * math.pi * t + phase * 0.7))
            # Extract zone and shift
            zone = arr[y0:y1, x0:x1].copy()
            zy, zx = zone.shape[:2]
            ny0 = max(0, min(y0 + dy, h - zy))
            nx0 = max(0, min(x0 + dx, w - zx))
            result[ny0:ny0+zy, nx0:nx0+zx] = zone
        # Add grain
        noise = np.random.RandomState(i + 100).randint(0, 20, result.shape, dtype=np.uint8)
        result = np.clip(result.astype(np.int16) + noise - 10, 0, 255).astype(np.uint8)
        frames.append(Image.fromarray(result))
    return frames


# ─── ANIMATION MODES: Steam, Wind, Glisten, Light Sweep ──────────────────────

def _frames_steam(img: Image.Image) -> list:
    """Steam: rising vapor wisps from lower third, wavering upward."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    rng = np.random.default_rng(33)
    # Pre-compute steam particle origins (8 wisps)
    n_wisps = 8
    wisp_x = rng.integers(int(w * 0.15), int(w * 0.85), n_wisps)
    wisp_speed = rng.uniform(2.0, 5.0, n_wisps)
    wisp_width = rng.integers(8, 20, n_wisps)

    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        for ws in range(n_wisps):
            wx = wisp_x[ws]
            ww = wisp_width[ws]
            # Wisp rises from bottom
            wisp_y_base = int(h * 0.75)
            rise = int(wisp_speed[ws] * i * 2.5)
            wisp_top = max(0, wisp_y_base - rise)
            wisp_bot = wisp_y_base
            for row in range(wisp_top, wisp_bot):
                # Horizontal wavering
                sway = int(ww * 0.4 * math.sin(row * 0.15 + phase + ws))
                cx = wx + sway
                # Fade out as wisp rises
                fade = (row - wisp_top) / max(1, wisp_bot - wisp_top)
                alpha = 0.25 * fade  # more visible near origin
                spread = max(2, int(ww * fade))
                x0 = max(0, cx - spread)
                x1 = min(w, cx + spread)
                if x1 > x0:
                    f[row, x0:x1] = f[row, x0:x1] * (1 - alpha) + 255 * alpha
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_wind(img: Image.Image) -> list:
    """Wind: horizontal pixel displacement wave, stronger on right side."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    try:
        from scipy.ndimage import map_coordinates
        has_scipy = True
    except ImportError:
        has_scipy = False

    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        # Wind blows left to right — amplitude increases toward right edge
        wind_strength = (xc / w) * 12  # max 12px at right edge
        dy = wind_strength * np.sin(phase + yc * 0.06 + xc * 0.02)
        dx = wind_strength * 0.3 * np.cos(phase * 1.3 + yc * 0.04)
        src_x = np.clip(xc + dx, 0, w - 1)
        src_y = np.clip(yc + dy, 0, h - 1)
        if has_scipy:
            f = np.zeros_like(arr)
            for ch in range(3):
                f[:, :, ch] = map_coordinates(arr[:, :, ch], [src_y, src_x], order=1, mode='reflect')
        else:
            f = arr[src_y.astype(int), src_x.astype(int)]
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_glisten(img: Image.Image) -> list:
    """Glisten: sparkle points that appear, intensify, and fade across the image."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    rng = np.random.default_rng(55)
    # Pre-compute 30 sparkle positions on bright areas
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    bright_mask = gray > np.percentile(gray, 70)
    bright_ys, bright_xs = np.where(bright_mask)
    if len(bright_ys) > 30:
        indices = rng.choice(len(bright_ys), 30, replace=False)
        spark_y = bright_ys[indices]
        spark_x = bright_xs[indices]
    else:
        spark_y = rng.integers(0, h, 30)
        spark_x = rng.integers(0, w, 30)
    spark_phase_offset = rng.uniform(0, 2 * math.pi, 30)

    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        for s in range(30):
            # Each sparkle has its own phase
            sp = phase + spark_phase_offset[s]
            intensity = max(0, math.sin(sp)) ** 3  # sharp peaks
            if intensity < 0.05:
                continue
            sy, sx = spark_y[s], spark_x[s]
            radius = int(2 + 4 * intensity)
            # Draw cross-shaped sparkle
            for dy in range(-radius, radius + 1):
                py = sy + dy
                if 0 <= py < h:
                    alpha = intensity * 0.7 * (1 - abs(dy) / (radius + 1))
                    f[py, sx] = f[py, sx] * (1 - alpha) + 255 * alpha
            for dx in range(-radius, radius + 1):
                px = sx + dx
                if 0 <= px < w:
                    alpha = intensity * 0.7 * (1 - abs(dx) / (radius + 1))
                    f[sy, px] = f[sy, px] * (1 - alpha) + 255 * alpha
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_light_sweep(img: Image.Image) -> list:
    """Light sweep: diagonal light beam sweeps across the image left to right."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    # Diagonal coordinate
    diag = (xc / w + yc / h) / 2  # 0..1 diagonal

    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        f = arr.copy()
        # Light beam position sweeps from -0.2 to 1.2
        beam_center = -0.2 + t * 1.4
        beam_width = 0.08
        # Gaussian beam profile
        beam = np.exp(-((diag - beam_center) ** 2) / (2 * beam_width ** 2))
        # Apply light (brighten + slight warm tint)
        light_intensity = beam[:, :, np.newaxis] * 0.5
        f = f + light_intensity * (255 - f)  # screen blend
        # Slight warm tint in the beam
        f[:, :, 0] += beam * 15  # warm red
        f[:, :, 1] += beam * 8   # slight green
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


# ─── MOD CINEMAGRAPH: o singură zonă animată ──────────────────────────────────
def _frames_cinemagraph(img: Image.Image, subject_type: str, style_id: str) -> list:
    """Cinemagraph: base frame static + o zonă animată per subject_type."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]

    # Definim zona animată (mask normalizată 0.0-1.0)
    motion_mask = _get_cinemagraph_mask(subject_type, h, w)

    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi

        # Animație pentru zona respectivă
        animated = _apply_cinemagraph_motion(arr, subject_type, style_id, phase, h, w)

        # Composite: static + animated
        mask3 = motion_mask[:, :, np.newaxis]
        f = arr * (1 - mask3) + animated * mask3
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))

    return frames


def _get_cinemagraph_mask(subject_type: str, h: int, w: int) -> np.ndarray:
    """Returns soft float32 mask (h,w) pentru zona animată cinemagraph."""
    try:
        from scipy.ndimage import gaussian_filter
    except ImportError:
        gaussian_filter = None

    mask = np.zeros((h, w), dtype=np.float32)
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)

    if subject_type == "face":
        # Zona ochilor (25-40% height, 20-80% width)
        cy, cx = h * 0.32, w * 0.5
        ry, rx = h * 0.08, w * 0.30
        mask = np.clip(1.0 - ((xc - cx) / rx) ** 2 - ((yc - cy) / ry) ** 2, 0, 1)
    elif subject_type == "cup":
        # Zona superioara 0-18%
        mask[:int(h * 0.18)] = 1.0
        # Fade lin
        fade_rows = int(h * 0.05)
        for row in range(int(h * 0.13), int(h * 0.18)):
            mask[row] = max(0, 1.0 - (row - int(h * 0.13)) / fade_rows)
    elif subject_type == "animal":
        # Colturi sus (urechi)
        mask[:int(h * 0.22), :int(w * 0.30)] = 0.8
        mask[:int(h * 0.22), int(w * 0.70):] = 0.8
    elif subject_type in ("plant", "flower"):
        # Zona superioara 30%
        mask[:int(h * 0.30)] = 1.0
        fade_rows = int(h * 0.08)
        for row in range(int(h * 0.22), int(h * 0.30)):
            mask[row] = max(0, 1.0 - (row - int(h * 0.22)) / fade_rows)
    else:
        # Centru oval
        cy, cx = h * 0.5, w * 0.5
        ry, rx = h * 0.25, w * 0.25
        mask = np.clip(1.0 - ((xc - cx) / rx) ** 2 - ((yc - cy) / ry) ** 2, 0, 1)

    if gaussian_filter is not None:
        mask = gaussian_filter(mask, sigma=8)
    return np.clip(mask, 0, 1).astype(np.float32)


def _apply_cinemagraph_motion(
    arr: np.ndarray, subject_type: str, style_id: str,
    phase: float, h: int, w: int
) -> np.ndarray:
    """Aplică mișcarea animată pe toată imaginea (mascat ulterior)."""
    f = arr.copy()
    yc_mg, xc_mg = np.mgrid[0:h, 0:w].astype(np.float32)

    if subject_type == "face":
        # Brightness oscillation in zona ochilor
        brightness = 1.0 + 0.18 * math.sin(phase)
        f = f * brightness
    elif subject_type == "cup":
        # Shimmer horizontal sus
        shift = int(6 * math.sin(phase))
        f[:int(h * 0.18)] = np.roll(f[:int(h * 0.18)], shift, axis=1)
    elif subject_type == "animal":
        # Warp subtil ±3px
        dx = (3 * np.sin(phase + yc_mg * 0.05)).astype(int)
        src_x = np.clip(xc_mg.astype(int) + dx, 0, w - 1)
        src_y = yc_mg.astype(int)
        f = f[src_y, src_x].copy()
    elif subject_type in ("plant", "flower"):
        # Horizontal wave ±3px
        amplitude = 3.0 * (1 - yc_mg / h)
        dx = (amplitude * np.sin(phase + yc_mg * 0.04)).astype(int)
        src_x = np.clip(xc_mg.astype(int) + dx, 0, w - 1)
        src_y = yc_mg.astype(int)
        f = f[src_y, src_x].copy()
    else:
        # Contrast pulse
        contrast = 1.0 + 0.15 * math.sin(phase)
        f = (f - 128) * contrast + 128

    return f.astype(np.float32)
