import google.generativeai as genai
from app.config import settings
from app.models.schemas import StyleId

STYLE_INSTRUCTIONS = {
    # ── ORIGINAL 10 — technique-focused, no iconic motif references ──────────
    StyleId.warhol: (
        "Transform using Andy Warhol's Factory silkscreen print technique. "
        "Posterize the subject into exactly four flat CMYK color separations printed as "
        "discrete layers. Ben-Day halftone dots visible at edges. Apply stark high-contrast "
        "graphic reduction: every shadow becomes a solid flat shape, every highlight becomes "
        "pure white. Arrange as a 2×2 or 1×4 repeat grid, each quadrant with a different "
        "off-register color shift — hot pink, acid yellow, electric cyan, lime green. "
        "Zero photographic gradients. Thin black contour outlines only at form boundaries. "
        "Commercial silkscreen ink texture on the surface."
    ),
    StyleId.hokusai: (
        "Transform using Edo-period ukiyo-e woodblock print technique. Apply confident, "
        "variable-width ink outlines — thicker on outer contours, hairline on interior detail. "
        "Fill enclosed shapes with flat, unmodulated color using the traditional palette: "
        "bero Prussian blue, vermilion, pale yellow, ivory. No photographic gradients: replace "
        "tonal transitions with fine parallel hatching lines or flat color steps. Apply bokashi "
        "wet-bleed gradation only at sky or water zones. Treat negative space as active "
        "composition element. Subtle rice-paper grain texture beneath the ink."
    ),
    StyleId.klimt: (
        "Transform using Gustav Klimt's Vienna Secession mosaic technique. Render the subject's "
        "face and visible hands with naturalistic oil paint precision — these zones remain "
        "photorealistic. Every other surface — garments, background, furniture, floor — becomes "
        "an intricate flat mosaic of geometric micro-patterns: spirals, eyes, triangles, "
        "Byzantine tesserae. Gold leaf dominates all decorative zones. Color palette: "
        "burnished gold, deep ochre, cobalt, ivory, black. The tension between the naturalistic "
        "face and the ornamental abstraction of everything else is the defining technique."
    ),
    StyleId.ghibli: (
        "Transform using Studio Ghibli hand-drawn cel animation technique. Apply soft watercolor "
        "wet washes as the base layer — colors bleed softly at edges rather than staying sharp. "
        "Add precise ink-pen outline over the wash in a single consistent weight. Light is "
        "warm ambient, sourced from windows or sky, casting gentle diffuse shadows. Backgrounds "
        "feature botanical detail: leaf veins, bark texture, cloud wisps. Character forms are "
        "slightly simplified and rounded. The overall feeling is tactile, hand-made, "
        "alive with small environmental movements."
    ),
    StyleId.banksy: (
        "Transform using Banksy's urban stencil spray-paint technique. Reduce the subject to "
        "a high-contrast black stencil with deliberate bridge cuts between isolated shapes. "
        "Spray feathering and spatter visible at stencil edges — the paint bleeds beyond the "
        "mask. Background is raw concrete or brick texture, neutral grey. Add one single accent "
        "color element as a separate stencil layer (red heart, yellow crown, blue balloon). "
        "The subject must read clearly in under one second. Maximum brutally simple graphic "
        "reduction — remove all detail that does not serve the silhouette read."
    ),
    StyleId.dali: (
        "Transform using Salvador Dalí's paranoid-critical hyperrealist technique. Render every "
        "surface with photographic precision and academic oil-paint finish — no impressionistic "
        "looseness. The physical laws of the scene are subtly violated: rigid objects acquire "
        "soft draping weight, solid surfaces develop impossible permeability, scale relationships "
        "between objects are slightly wrong. Cast shadows fall in directions inconsistent with "
        "the light source. All violations must feel inevitable and calm rather than chaotic. "
        "Sky is infinite pale yellow-ochre, shadows deep ultramarine. The uncanny emerges "
        "from technical perfection applied to impossible premises."
    ),
    StyleId.vangogh: (
        "Transform using Vincent van Gogh's impasto post-impressionist technique. Every surface "
        "is covered by thick directional brushstrokes — short stabbing dashes on foliage, "
        "long sweeping curves on open fields, tight concentric loops around spherical forms. "
        "The physical paint ridge is visible as raised relief, casting micro-shadows. Color is "
        "heightened: pure ultramarine adjacent to raw sienna, viridian against cadmium orange. "
        "No smooth blending — color transitions occur through side-by-side stroke juxtaposition. "
        "Mark density and direction describe form. Energy comes from the texture of making, "
        "not from subject matter references."
    ),
    StyleId.baroque: (
        "Transform using Dutch Golden Age chiaroscuro oil painting technique. A single strong "
        "directional light source — implied candle or window — illuminates the subject from "
        "one side only. The unlit side fades into near-total warm darkness (umber, raw sienna, "
        "deep brown). The lit zone uses cool ivory highlights with sfumato soft-edge transitions. "
        "Surface texture simulates aged oil on canvas: fine craquelure, subtle impasto on "
        "brightest highlights. Color palette is restricted: earth tones, lead white, vermilion "
        "accents. Volume is entirely constructed through tonal gradient, not outline."
    ),
    StyleId.mondrian: (
        "Transform using Piet Mondrian's strict De Stijl neoplastic composition. Decompose the "
        "subject into a flat orthogonal grid of rectangles separated by bold black lines of "
        "consistent weight — no diagonal lines, no curves. Fill rectangles with either pure "
        "primary hues (cadmium red, ultramarine blue, lemon yellow) or neutral non-colors "
        "(white, black, light grey). No secondary or tertiary colors permitted. No texture, "
        "no gradients, no shadows. The subject is fully abstracted into rectangular planes. "
        "Proportions of the grid should feel visually balanced but asymmetric. "
        "The image must work as pure geometry."
    ),
    StyleId.mucha: (
        "Transform using Alphonse Mucha's Art Nouveau poster technique. Draw the subject with "
        "sinuous, fluid ink line — curves predominate, no harsh angles. The background features "
        "a symmetrical botanical halo or lunette frame composed of stylized flowers, stems, "
        "and leaves rendered in flat outlined shapes. Color palette: aged cream ground, soft "
        "muted pastels (rose, sage, gold, lilac), subtle sepia wash. Add ornamental border "
        "panels at top or bottom with geometric-botanical hybrid patterns. All elements — "
        "figure, halo, border — sit on the same flat plane with no atmospheric depth. "
        "Printed on aged cream stock with visible grain."
    ),

    # ── 20 NEW STYLES ─────────────────────────────────────────────────────────
    StyleId.meiji_print: (
        "Transform using Meiji-era shin-hanga woodblock print technique. Apply delicate bokashi "
        "gradation — wet pigment bleed creating smooth tonal transitions from deep indigo to pale "
        "sky at edges. Contour lines are confident single-weight ink, slightly less bold than Edo "
        "period. Color palette: muted indigo, rose, moss green, ivory, soft gold. Fine washi "
        "paper texture with visible fibres beneath the ink. Western perspective influence subtly "
        "present — slight depth recession, atmospheric haze in backgrounds. Katagami stencil "
        "patterns appear in fabric and textile surfaces."
    ),
    StyleId.persian_mini: (
        "Transform using Safavid Persian miniature painting technique. Reject all Western "
        "perspective and chiaroscuro — every element is presented frontally at its most "
        "recognizable angle. No cast shadows anywhere in the composition. Space is compressed "
        "into stacked horizontal registers. Color is pure, flat, jewel-saturated: lapis lazuli "
        "blue, vermilion, malachite green, gold leaf ground. Figures and objects are outlined "
        "in fine ink, filled with opaque gouache pigments ground from precious stones. "
        "Decorative borders of arabesque interlace. Every surface is filled with intricate "
        "pattern — no empty negative space."
    ),
    StyleId.mughal_mini: (
        "Transform using Mughal imperial miniature painting technique — a hybrid of Safavid "
        "Persian flatness and European Renaissance volume. Figures have subtle modelling through "
        "fine parallel hatching rather than flat fill. Atmospheric sky gradation from deep "
        "lapis to pale gold at the horizon. Fine naturalistic botanical detail in margins: "
        "individually observed flowers and insects. Cotton-polished paper surface gives the "
        "pigment an enamel-smooth finish. Color: muted warm earths, deep red, teal, ivory, "
        "burnished gold. The marriage of Persian ornament with observed natural detail."
    ),
    StyleId.byzantine: (
        "Transform using Byzantine mosaic technique. Decompose the entire image into individual "
        "tessera units — small square tiles of gold smalti, colored glass, and stone. Skin tones "
        "built from warm tan and terracotta tiles with deliberate visible gaps. Background is "
        "pure gold tessera ground, tesserae set at slightly varying angles to catch light. "
        "Figures are rendered with hieratic frontality — facing directly forward, symmetrical "
        "stiff posture, elongated proportions. Outlining in dark lead-line between color zones. "
        "No atmospheric perspective. Color palette: gold, deep cobalt, vermilion, ivory, "
        "dark umber, turquoise smalti."
    ),
    StyleId.preraphaelite: (
        "Transform using Pre-Raphaelite Brotherhood wet white ground oil technique. Paint onto "
        "a wet white ground to achieve jewel-saturated, luminous color — every hue at maximum "
        "chromatic intensity without muddying. Botanical detail rendered with scientific "
        "precision: individual leaves, petals, and bark described with obsessive specificity. "
        "Figures have a slightly glassy, over-precise quality. Fabric folds are studied from "
        "life and rendered with archaeological accuracy. Light is even and cool, no dramatic "
        "chiaroscuro. Color palette: jewel emerald, deep rose madder, cobalt, ivory, gold. "
        "Every element in sharp focus simultaneously — no shallow depth of field."
    ),
    StyleId.expressionism: (
        "Transform using German Expressionist Die Brücke woodcut and oil technique. Distort "
        "anatomy and space to externalize psychological tension — elongate figures, tilt floors, "
        "skew architectural lines. Color is anti-naturalistic and psychologically motivated: "
        "harsh acid green, cadmium orange, alizarin crimson applied in unmixed slabs. Thick "
        "visible brushwork with knife-like edges. Outlines are jagged, angular, anxious. "
        "No pretty surfaces — the image should feel urgent and abraded. Compressed space creates "
        "claustrophobia. Emotional truth over optical accuracy."
    ),
    StyleId.futurism: (
        "Transform using Italian Futurist simultaneity technique. Decompose any movement in "
        "the scene into multiple overlapping stroboscopic ghost images — three to six positions "
        "of a single action shown simultaneously in the same frame. Lines of force radiate "
        "outward from dynamic centers. Speed lines (linee di forza) emanate from moving elements "
        "in aggressive diagonal bundles. Color palette: electric blue, orange-red, acid yellow "
        "on near-black ground. The composition must feel like it is vibrating at high frequency. "
        "Static objects barely exist — only motion has visual weight."
    ),
    StyleId.constructivism: (
        "Transform using Soviet Constructivist design by Rodchenko and Lissitzky. Reduce the "
        "image to a strict geometric composition using only three colors: cadmium red, black, "
        "and white. Diagonal axes dominate — 45-degree angles create dynamic tension. All "
        "typography elements (if present) use sans-serif geometric letterforms integrated as "
        "visual shapes. Circles, rectangles, and triangles interlock with machined precision. "
        "No organic curves, no hand-drawn quality. The aesthetic of industrial production: "
        "technical drawing precision, flat ink, zero decoration. Every element serves "
        "compositional function."
    ),
    StyleId.swiss_poster: (
        "Transform using Swiss International Typographic Style poster design. Apply a strict "
        "modular grid — all elements snap to invisible underlying columns and rows. Halftone "
        "photography (60-line screen) anchors the composition. Color palette: maximum two "
        "spot colors plus black and white. Helvetica or Akzidenz-Grotesk letterforms (if text "
        "present) set in precise size hierarchies. Generous white space as active element. "
        "The design must communicate its hierarchy in under two seconds. Asymmetric balance, "
        "rational organization, absolute clarity. Print registration marks deliberately visible "
        "at corners."
    ),
    StyleId.pointillism: (
        "Transform using Georges Seurat's chromoluminarist divisionist technique. Apply pure "
        "unmixed pigment dots of consistent small size across the entire canvas surface — "
        "no dot is blended with its neighbor. Colors mix optically at viewing distance. "
        "Shadow zones use complementary dots: orange shadows receive blue dots, green shadows "
        "receive red dots. The dot matrix reveals the subject only when the eye integrates "
        "from distance. Edge definition is soft — contours emerge from density shifts, not "
        "from outlines. Palette: pure spectrum primaries and their complements, white ground "
        "showing through dot gaps."
    ),
    StyleId.risograph: (
        "Transform using Risograph duplicator printing aesthetic. Decompose the image into "
        "exactly two or three flat-color spot channels printed separately and imperfectly "
        "registered. Characteristic Riso ink colors: fluorescent pink, school-bus yellow, "
        "teal, and black. Where channels overlap, they create secondary mixed tones through "
        "transparent ink layering. Mis-registration between channels offset 2-4px. Paper "
        "grain highly visible beneath the ink. Halftone screening uses coarse angled dot "
        "patterns. Ink density varies slightly across the print, leaving faint banding. "
        "Like a 1980s photocopied fanzine elevated to fine art."
    ),
    StyleId.woodcut: (
        "Transform using hand-carved woodcut relief printing technique. The image exists only "
        "in binary: areas where the knife has carved away (white, ink-free) and areas where "
        "wood remains (black, ink-bearing). No greyscale — every tonal zone must be resolved "
        "into pure black or pure white. Visible gouge-mark texture in the white areas — "
        "the direction of carving strokes describes the surface. Knife-cut edges have a "
        "slightly irregular quality: not perfectly smooth, showing the grain of the wood. "
        "Form is described through pattern of black marks alone. Maximum graphic reduction "
        "— only the essential silhouette and structural lines survive."
    ),
    StyleId.ligne_claire: (
        "Transform using Hergé's ligne claire bande dessinée technique. Apply a uniform, "
        "unwavering ink line of identical weight everywhere in the image — foreground and "
        "background receive exactly the same line weight. No variation in stroke width, no "
        "calligraphic taper. Fill all enclosed zones with flat, unmodulated color — no "
        "gradients, no texture within any colored area. Apply equal rendering detail to "
        "every element: a background building has the same precision as the foreground subject. "
        "Color palette: clean primaries and secondaries, saturated but not garish. "
        "Shadows are indicated by a single flat tone, not by gradient."
    ),
    StyleId.daguerreotype: (
        "Transform using 1840s daguerreotype photographic technique. Silver-grey tonal palette "
        "only — no warm sepia, no color. Highlights have a distinctive metallic specular bloom "
        "(halation). The silver plate surface shows subtle reflective variation — lighter at "
        "the center, darker at extreme edges. Exposure latitude is compressed: shadows block "
        "up quickly to dense black, highlights blowout to pure silver-white. Fine grain texture "
        "visible at midtones. Slightly long exposure motion blur on any moving element. "
        "Vignetting at corners. The image has the quality of something preserved impossibly "
        "from another century."
    ),
    StyleId.infrared: (
        "Transform using Kodak Aerochrome false-color infrared film technique. Foliage "
        "containing chlorophyll becomes brilliant white or pale gold (infrared reflection). "
        "Clear sky renders deep black or near-black. Shadows on foliage are rendered in "
        "vivid magenta-pink. Skin tones shift toward pale ivory with faint magenta cast. "
        "Water and concrete remain in normal tonal range but with heightened contrast. "
        "Overall color palette: white foliage, dark sky, magenta shadows, ivory skin, "
        "teal-shifted distant atmosphere. The world is botanically luminous and atmospherically "
        "dramatic simultaneously."
    ),
    StyleId.lomography: (
        "Transform using LC-A Lomo camera analogue photography aesthetic. Heavy vignetting — "
        "corners darken significantly toward black. Cross-processed film chemistry shifts "
        "colors unpredictably: greens shift toward cyan, reds toward orange-pink, shadows "
        "take on blue-green cast. Slight soft focus at image edges from cheap plastic lens. "
        "Occasional light leak streaks — horizontal bands of warm orange or pale pink crossing "
        "the frame. Film grain visible, slightly chunky. Saturation boosted beyond natural. "
        "The image looks like it was found in a shoebox, shot impulsively, accidentally perfect."
    ),
    StyleId.cyberpunk: (
        "Transform using cyberpunk neon-noir visual language influenced by Syd Mead and "
        "1980s retrofuturism. Ground the scene in near-total darkness — deep indigo-black "
        "environment. Illuminate only with neon practical sources: electric magenta, cyan, "
        "acid green, amber. Apply lens effects: neon bloom and wet-surface reflections "
        "doubling every light source. Overlay subtle HUD scan-line pattern across the image. "
        "Occasional glitch artifact — horizontal pixel-shift bands or RGB channel separation. "
        "Visible rain streaks catching the neon. Surfaces: wet concrete, chrome, glass, "
        "black vinyl. The subject feels like the most human thing in a machine world."
    ),
    StyleId.brutalist: (
        "Transform using Brutalist architecture and graphic design aesthetic. Dominant material "
        "is raw board-formed concrete — form-liner texture visible in every surface. Typography "
        "is blunt, oversized, unornamented — occupying space aggressively. Color palette: raw "
        "concrete grey, black, white, occasional single accent in industrial yellow or red. "
        "Composition is asymmetric and confrontational rather than harmonious. No decorative "
        "elements — every visual choice is structural. Shadows are deep and architectural. "
        "The aesthetic rejects beauty as ornamentation and finds it instead in honest "
        "material weight and geometric mass."
    ),
    StyleId.wpa_poster: (
        "Transform using American WPA federal silkscreen poster technique from the 1930s-40s. "
        "Maximum six flat colors with no gradients — each a distinct spot ink. Figures and "
        "forms reduced to bold heroic silhouettes with deliberate simplification. Staging is "
        "monumental: low camera angle looking up, figures larger than life. Color palette: "
        "earthy terracotta, deep forest green, sky blue, cream, black. Hard edge between all "
        "color zones — no soft blending at boundaries. Strong diagonal composition. "
        "Print registration visible. The image should feel like public art made to inspire "
        "collective action."
    ),
    StyleId.zine_collage: (
        "Transform using DIY punk zine photocopier collage aesthetic. The image is assembled "
        "from torn and cut paper fragments with ragged edges — glue or tape marks visible at "
        "joins. Multiple generations of photocopying have degraded image quality: halftone "
        "breaking down, contrast crushing to high-key black and white. Handwritten annotation "
        "scrawled in marker at margins. Misaligned elements, accidental overlaps, ink bleed. "
        "Small areas of color from cut magazine fragments. Texture of the paper grain and "
        "toner uneven distribution. The image looks assembled at 2am with scissors and rage, "
        "photocopied fifty times."
    ),
}

STYLE_MOTION_SUFFIX = {
    # Original 10 — intrinsic medium physics, no subject-matter references
    StyleId.warhol:        "color grid panels cycling through sequential CMYK registration shifts, "
                           "Ben-Day dot screens rotating in a pulsing seamless loop",
    StyleId.hokusai:       "ink contour lines redrawing themselves in slow deliberate strokes, "
                           "flat color planes bleeding in layer by layer as woodblock registers settle",
    StyleId.klimt:         "gold tessera tiles shimmering with micro-rotation, mosaic patterns "
                           "slowly morphing between geometric configurations in a hypnotic loop",
    StyleId.ghibli:        "watercolor washes slowly spreading at edges, cel outlines gently breathing "
                           "with wind-movement, soft ambient light shifting in a warm seamless loop",
    StyleId.banksy:        "spray paint mist drifting across the stencil edges, grain noise "
                           "pulsing, the single accent color flickering in an urban loop",
    StyleId.dali:          "solid surfaces acquiring soft drape weight in slow motion, "
                           "cast shadows rotating against the light source in a dreamlike loop",
    StyleId.vangogh:       "impasto brushstroke marks lengthening and curving in the direction "
                           "of their application, paint ridges casting shifting micro-shadows",
    StyleId.baroque:       "single candlelight source flickering, chiaroscuro boundary "
                           "gently pulsing between illuminated and shadow zones in a seamless loop",
    StyleId.mondrian:      "primary color blocks pulsing in rhythmic sequence, black grid lines "
                           "briefly dissolving and re-forming in a geometric seamless loop",
    StyleId.mucha:         "botanical halo elements slowly rotating outward, aged cream ground "
                           "warming and cooling as soft light rakes across the print surface",
    # 20 new — intrinsic medium motion
    StyleId.meiji_print:   "bokashi gradation bleeding and retracting at paper edges, "
                           "washi fibre texture shimmering under raking light in a gentle loop",
    StyleId.persian_mini:  "gold leaf ground glinting as the viewing angle subtly shifts, "
                           "jewel-pigment surfaces slowly intensifying and releasing saturation",
    StyleId.mughal_mini:   "fine hatching strokes breathing slightly as if freshly applied, "
                           "botanical margin details individually blooming in sequence",
    StyleId.byzantine:     "gold tessera tiles rotating fractionally to catch shifting light, "
                           "smalti mosaic surface shimmering with incandescent depth",
    StyleId.preraphaelite: "botanical elements individually illuminating in sequence as the "
                           "wet white ground light source pulses through jewel-saturated pigment",
    StyleId.expressionism: "gestural knife-stroke marks vibrating with psychological urgency, "
                           "distorted space briefly compressing further then releasing",
    StyleId.futurism:      "stroboscopic ghost-images cycling forward through their motion sequence, "
                           "lines of force radiating outward in pulsing diagonal bursts",
    StyleId.constructivism:"geometric elements briefly rotating on their 45-degree axes, "
                           "red planes advancing and receding against the black ground",
    StyleId.swiss_poster:  "halftone dot screen rotating through its screen angle, "
                           "grid columns briefly shifting phase and snapping back to registration",
    StyleId.pointillism:   "pure pigment dots individually brightening and dimming, "
                           "optical color mixing shifting as the dot pattern subtly breathes",
    StyleId.risograph:     "color separation channels drifting in their mis-registration offsets, "
                           "halftone screen angles rotating through the ink layers",
    StyleId.woodcut:       "gouge-mark texture briefly animating in the direction of carving, "
                           "ink spreading fractionally from the relief surface in a loop",
    StyleId.ligne_claire:  "uniform ink line briefly thickening and returning to weight, "
                           "flat color fills cycling through clean hue shifts",
    StyleId.daguerreotype: "silver plate halation bloom expanding and contracting, "
                           "metallic reflectivity shifting across the tonal surface",
    StyleId.infrared:      "chlorophyll-white foliage pulsing brighter as if reacting to light, "
                           "dark sky deepening and recovering in a slow breathing loop",
    StyleId.lomography:    "vignette corners breathing in and out, light leak streak "
                           "drifting slowly across the frame in warm analogue loop",
    StyleId.cyberpunk:     "neon light sources flickering with electrical instability, "
                           "HUD scan-lines scrolling and glitch artifacts briefly fracturing the image",
    StyleId.brutalist:     "concrete form-liner shadows shifting as light angle slowly changes, "
                           "mass feeling heavier then lighter in a geological slow loop",
    StyleId.wpa_poster:    "flat color planes briefly separating at print registration seams, "
                           "heroic staging light source warming and cooling in a slow loop",
    StyleId.zine_collage:  "photocopier toner degrading and regenerating across image zones, "
                           "torn paper edges lifting fractionally as if in an analogue loop",
}


async def generate_prompt_variations(prompt: str, style_id: StyleId) -> list:
    """Genereaza 3 variante creative ale promptului dat, in acelasi stil artistic."""
    art_dir = STYLE_INSTRUCTIONS.get(style_id, STYLE_INSTRUCTIONS[StyleId.dali])
    motion_sfx = STYLE_MOTION_SUFFIX.get(style_id, "animated in a seamless loop")

    variation_prompt = f"""You are a creative art director. You have this AI art generation prompt:

"{prompt}"

Generate exactly 3 alternative creative versions of this prompt. Each version must:
- Keep the SAME main subject from the original
- Use this artistic style: {art_dir}
- End with: {motion_sfx}
- Be 40-60 words long
- Be DIFFERENT from each other (different mood, perspective, technique, or atmosphere)

Return ONLY a JSON array of 3 strings, like: ["version 1", "version 2", "version 3"]
No explanation, no markdown, just the JSON array."""

    # Vertex AI first
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
        from app.config import settings

        vertexai.init(project=settings.google_cloud_project, location=settings.google_cloud_location)
        model = GenerativeModel("gemini-2.0-flash-001")
        response = model.generate_content(variation_prompt)
        text = response.text.strip()
        # Parse JSON
        import json
        # Remove possible markdown fences
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        variations = json.loads(text)
        if isinstance(variations, list) and len(variations) >= 3:
            return variations[:3]
        return variations
    except Exception as e1:
        print(f"generate_prompt_variations Vertex failed: {e1}")
        # Fallback: genai
        try:
            import json
            genai.configure(api_key=settings.google_api_key or None)
            model2 = genai.GenerativeModel(settings.gemini_model)
            response2 = model2.generate_content(variation_prompt)
            text2 = response2.text.strip()
            if text2.startswith("```"):
                text2 = text2.split("```")[1]
                if text2.startswith("json"):
                    text2 = text2[4:]
            return json.loads(text2)[:3]
        except Exception as e2:
            print(f"generate_prompt_variations genai also failed: {e2}")
            # Hardcoded fallback - 3 simple variations
            return [
                prompt + ", dramatic chiaroscuro lighting, deep shadows",
                prompt + ", ethereal soft glow, pastel dream atmosphere",
                prompt + ", bold neon accents, cyberpunk energy",
            ]


async def generate_creative_prompt(image_bytes: bytes, style_id: StyleId) -> str:
    genai.configure(api_key=settings.google_api_key or None)
    model = genai.GenerativeModel(settings.gemini_model)

    image_part = {"mime_type": "image/jpeg", "data": image_bytes}

    instruction = STYLE_INSTRUCTIONS.get(style_id, STYLE_INSTRUCTIONS[StyleId.dali])
    motion_suffix = STYLE_MOTION_SUFFIX.get(style_id, "animated in a seamless cinematic loop")

    prompt_text = f"""Analyze this image and identify the main subject/object.
Then write a single vivid, cinematic video generation prompt (max 120 words) that:
1. Describes the subject clearly with precise visual details
2. {instruction}
3. Ends with: {motion_suffix}

Return ONLY the prompt text, nothing else."""

    response = model.generate_content([prompt_text, image_part])
    return response.text.strip()
