"""Tests: Every style must have complete definitions across all services.

Run: cd backend && python -m pytest tests/ -v
"""
import pytest
from app.models.schemas import StyleId
from app.services.gemini_service import STYLE_INSTRUCTIONS, STYLE_MOTION_SUFFIX
from app.services.hf_service import STYLE_GRADIENTS, STYLE_ANTI_PATTERNS


ALL_STYLES = list(StyleId)


class TestStyleCompleteness:
    """Every StyleId must be defined in all required dictionaries."""

    @pytest.mark.parametrize("style", ALL_STYLES)
    def test_style_has_instruction(self, style):
        assert style in STYLE_INSTRUCTIONS, f"{style.value} missing from STYLE_INSTRUCTIONS"

    @pytest.mark.parametrize("style", ALL_STYLES)
    def test_style_has_motion_suffix(self, style):
        assert style in STYLE_MOTION_SUFFIX, f"{style.value} missing from STYLE_MOTION_SUFFIX"

    @pytest.mark.parametrize("style", ALL_STYLES)
    def test_style_has_colors(self, style):
        assert style.value in STYLE_GRADIENTS, f"{style.value} missing from STYLE_GRADIENTS"

    @pytest.mark.parametrize("style", ALL_STYLES)
    def test_instruction_not_empty(self, style):
        inst = STYLE_INSTRUCTIONS[style]
        assert len(inst) > 50, f"{style.value} instruction too short ({len(inst)} chars)"

    @pytest.mark.parametrize("style", ALL_STYLES)
    def test_motion_suffix_not_empty(self, style):
        sfx = STYLE_MOTION_SUFFIX[style]
        assert len(sfx) > 20, f"{style.value} motion suffix too short ({len(sfx)} chars)"


class TestAntiPatterns:
    """Critical styles must have anti-patterns defined."""

    CRITICAL_STYLES = [
        StyleId.warhol, StyleId.dali, StyleId.vangogh, StyleId.klimt,
        StyleId.hokusai, StyleId.banksy, StyleId.ghibli, StyleId.futurism,
        StyleId.expressionism, StyleId.mondrian, StyleId.baroque,
    ]

    @pytest.mark.parametrize("style", CRITICAL_STYLES)
    def test_critical_style_has_anti_pattern(self, style):
        assert style in STYLE_ANTI_PATTERNS, f"{style.value} missing anti-pattern"

    @pytest.mark.parametrize("style", CRITICAL_STYLES)
    def test_anti_pattern_has_do_not(self, style):
        ap = STYLE_ANTI_PATTERNS.get(style, "")
        assert "DO NOT" in ap, f"{style.value} anti-pattern must contain 'DO NOT' rules"


class TestStyleInstructionQuality:
    """Style instructions must follow quality rules."""

    @pytest.mark.parametrize("style", ALL_STYLES)
    def test_no_generic_terms(self, style):
        inst = STYLE_INSTRUCTIONS[style].lower()
        forbidden = ["beautiful", "stunning", "amazing", "gorgeous"]
        for word in forbidden:
            assert word not in inst, f"{style.value} instruction contains forbidden generic term '{word}'"

    @pytest.mark.parametrize("style", ALL_STYLES)
    def test_instruction_has_technique_details(self, style):
        inst = STYLE_INSTRUCTIONS[style].lower()
        # Every instruction should mention at least one concrete technique word
        technique_words = [
            "brush", "color", "stroke", "ink", "paint", "line", "surface",
            "texture", "shadow", "light", "tone", "contrast", "flat", "gradient",
            "print", "grain", "pigment", "canvas", "stencil", "spray", "gold",
            "mosaic", "concrete", "halftone", "neon", "silver", "film",
        ]
        has_technique = any(w in inst for w in technique_words)
        assert has_technique, f"{style.value} instruction lacks concrete technique details"


class TestAntiPatternConsistency:
    """Anti-patterns must be consistent with style instructions."""

    def test_futurism_not_surrealist(self):
        """Futurism anti-pattern must explicitly distinguish from Dalí."""
        ap = STYLE_ANTI_PATTERNS.get(StyleId.futurism, "")
        assert "dalí" in ap.lower() or "dali" in ap.lower(), \
            "Futurism anti-pattern must mention Dalí to prevent confusion"

    def test_dali_not_portrait(self):
        """Dalí anti-pattern must prevent generating artist portrait."""
        ap = STYLE_ANTI_PATTERNS.get(StyleId.dali, "")
        assert "portrait" in ap.lower() or "mustache" in ap.lower(), \
            "Dalí anti-pattern must prevent generating artist portrait"

    def test_klimt_face_realistic(self):
        """Klimt anti-pattern must specify face stays realistic."""
        ap = STYLE_ANTI_PATTERNS.get(StyleId.klimt, "")
        assert "face" in ap.lower() and "realistic" in ap.lower(), \
            "Klimt anti-pattern must specify face remains realistic"

    def test_warhol_not_lichtenstein(self):
        """Warhol must not be confused with Lichtenstein."""
        ap = STYLE_ANTI_PATTERNS.get(StyleId.warhol, "")
        inst = STYLE_INSTRUCTIONS.get(StyleId.warhol, "")
        # At least one of them should mention the distinction
        combined = (ap + inst).lower()
        assert "silkscreen" in combined or "screen" in combined, \
            "Warhol must reference silkscreen technique"
