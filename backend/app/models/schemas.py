from pydantic import BaseModel
from enum import Enum


class StyleId(str, Enum):
    # Original 10
    warhol         = "warhol"
    hokusai        = "hokusai"
    klimt          = "klimt"
    ghibli         = "ghibli"
    banksy         = "banksy"
    dali           = "dali"
    vangogh        = "vangogh"
    baroque        = "baroque"
    mondrian       = "mondrian"
    mucha          = "mucha"
    # 20 new styles
    meiji_print    = "meiji_print"
    persian_mini   = "persian_mini"
    mughal_mini    = "mughal_mini"
    byzantine      = "byzantine"
    preraphaelite  = "preraphaelite"
    expressionism  = "expressionism"
    futurism       = "futurism"
    constructivism = "constructivism"
    swiss_poster   = "swiss_poster"
    pointillism    = "pointillism"
    risograph      = "risograph"
    woodcut        = "woodcut"
    ligne_claire   = "ligne_claire"
    daguerreotype  = "daguerreotype"
    infrared       = "infrared"
    lomography     = "lomography"
    cyberpunk      = "cyberpunk"
    brutalist      = "brutalist"
    wpa_poster     = "wpa_poster"
    zine_collage   = "zine_collage"


class QualityTier(str, Enum):
    free     = "free"      # Imagen 3 Fast Art + NumPy animation - $0
    standard = "standard"  # Veo 3 Fast, 4 sec - ~$0.60
    premium  = "premium"   # Veo 3 Full, 8 sec - ~$4.00


class AnimationMode(str, Enum):
    life       = "life"       # animatie naturala: clipit fata, shimmer cana, sway planta
    cinemagraph = "cinemagraph"  # o singura zona animata, restul static
    blink      = "blink"      # eye blink effect
    steam      = "steam"      # rising vapor wisps
    wind       = "wind"       # horizontal wind displacement
    glisten    = "glisten"    # sparkle points on bright areas
    sweep      = "sweep"      # diagonal light beam sweep


class GenerateRequest(BaseModel):
    style_id: StyleId
    quality: QualityTier
    session_id: str
    animation_mode: AnimationMode = AnimationMode.life


class RegenerateRequest(BaseModel):
    prompt: str
    style_id: str
    quality: str = "standard"
    session_id: str
    thumbnail_url: str = ""
    animation_mode: str = "life"
    frame_delay: int = 60  # ms per frame: 40=fast, 60=normal, 100=slow


class InspireRequest(BaseModel):
    prompt: str
    style_id: str


class StorycardRequest(BaseModel):
    result_url: str
    filter_label: str
    prompt_used: str


class GenerateResponse(BaseModel):
    creation_id: str
    video_url: str
    thumbnail_url: str
    prompt_used: str
    style_id: str
    quality: str
    share_code: str
    subject_type: str = "object"


class StatusResponse(BaseModel):
    status: str  # pending | processing | done | error
    progress: int  # 0-100
    result: GenerateResponse | None = None
    error: str | None = None
