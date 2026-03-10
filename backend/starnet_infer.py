"""StarNet-based language classification inference for C3F.

Provides:
  list_weights()      → list of {filename, display} dicts
  classify_image()    → {lang_code, confidence, all_langs, class_name}

Models are loaded lazily and cached in memory by weight path.
"""

import os
import json
import logging

import torch
import torch.nn as nn
from torchvision import transforms
from PIL import Image

from timm.layers import DropPath, trunc_normal_

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────
# Directory that contains the built-in class-index JSON files shipped with
# the Starnet source code.
_STARNET_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'Starnet'))

# ── Model cache ────────────────────────────────────────────────────────────
# weight_path → (model, class_map)   where class_map is {int: str}
_model_cache: dict = {}


# ── StarNet-S3 model (from starnet_original.py) ────────────────────────────

class _ConvBN(torch.nn.Sequential):
    def __init__(self, in_planes, out_planes, kernel_size=1, stride=1,
                 padding=0, dilation=1, groups=1, with_bn=True):
        super().__init__()
        self.add_module('conv', torch.nn.Conv2d(
            in_planes, out_planes, kernel_size, stride,
            padding, dilation, groups))
        if with_bn:
            self.add_module('bn', torch.nn.BatchNorm2d(out_planes))
            torch.nn.init.constant_(self.bn.weight, 1)
            torch.nn.init.constant_(self.bn.bias, 0)


class _Block(nn.Module):
    def __init__(self, dim, mlp_ratio=3, drop_path=0.):
        super().__init__()
        self.dwconv  = _ConvBN(dim, dim, 7, 1, (7-1)//2, groups=dim, with_bn=True)
        self.f1      = _ConvBN(dim, mlp_ratio * dim, 1, with_bn=False)
        self.f2      = _ConvBN(dim, mlp_ratio * dim, 1, with_bn=False)
        self.g       = _ConvBN(mlp_ratio * dim, dim, 1, with_bn=True)
        self.dwconv2 = _ConvBN(dim, dim, 7, 1, (7-1)//2, groups=dim, with_bn=False)
        self.act     = nn.ReLU6()
        self.drop_path = DropPath(drop_path) if drop_path > 0. else nn.Identity()

    def forward(self, x):
        inp = x
        x   = self.dwconv(x)
        x1, x2 = self.f1(x), self.f2(x)
        x   = self.act(x1) * x2
        x   = self.dwconv2(self.g(x))
        return inp + self.drop_path(x)


class _StarNet(nn.Module):
    """StarNet-S3 classification head (base_dim=32, depths=[2,2,8,4])."""

    def __init__(self, num_classes: int,
                 base_dim: int = 32, depths=(2, 2, 8, 4),
                 mlp_ratio: int = 4, drop_path_rate: float = 0.0):
        super().__init__()
        self.in_channel = 32
        self.stem = nn.Sequential(
            _ConvBN(3, self.in_channel, kernel_size=3, stride=2, padding=1),
            nn.ReLU6())
        dpr = [x.item() for x in torch.linspace(0, drop_path_rate, sum(depths))]
        self.stages = nn.ModuleList()
        cur = 0
        for i, d in enumerate(depths):
            embed_dim = base_dim * (2 ** i)
            down      = _ConvBN(self.in_channel, embed_dim, 3, 2, 1)
            self.in_channel = embed_dim
            blocks    = [_Block(self.in_channel, mlp_ratio, dpr[cur + j])
                         for j in range(d)]
            cur += d
            self.stages.append(nn.Sequential(down, *blocks))
        self.norm    = nn.BatchNorm2d(self.in_channel)
        self.avgpool = nn.AdaptiveAvgPool2d(1)
        self.head    = nn.Linear(self.in_channel, num_classes)
        self.apply(self._init_weights)

    def _init_weights(self, m):
        if isinstance(m, (nn.Linear, nn.Conv2d)):
            trunc_normal_(m.weight, std=.02)
            if isinstance(m, nn.Linear) and m.bias is not None:
                nn.init.constant_(m.bias, 0)
        elif isinstance(m, (nn.LayerNorm, nn.BatchNorm2d)):
            if m.bias is not None:
                nn.init.constant_(m.bias, 0)
            if m.weight is not None:
                nn.init.constant_(m.weight, 1.0)

    def forward(self, x):
        x = self.stem(x)
        for stage in self.stages:
            x = stage(x)
        return self.head(torch.flatten(self.avgpool(self.norm(x)), 1))


# ── Image pre-processing ────────────────────────────────────────────────────
_TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
])

# ── Class name → ISO 639-1 language code ───────────────────────────────────
_CLASS_TO_LANG: dict[str, str] = {
    'arabic':    'ar',
    'bangla':    'bn',
    'bengali':   'bn',
    'chinese':   'zh',
    'english':   'en',
    'japanese':  'ja',
    'korean':    'ko',
    'latin':     'la',
    'symbols':   'symbols',
    'hindi':     'hi',
    'gujrathi':  'gu',
    'gujarati':  'gu',
    'kannada':   'kn',
    'oriya':     'or',
    'punjabi':   'pa',
    'tamil':     'ta',
    'telegu':    'te',
    'telugu':    'te',
    'cambodian': 'km',
    'greek':     'el',
    'hebrew':    'he',
    'mongolian': 'mn',
    'russian':   'ru',
    'thai':      'th',
    'tibetan':   'bo',
}


# ── Class-index JSON resolution ─────────────────────────────────────────────

def _resolve_class_json(weight_path: str) -> str | None:
    """Return the path to the class-index JSON for *weight_path*, or None."""
    stem       = os.path.splitext(os.path.basename(weight_path))[0]
    weight_dir = os.path.dirname(weight_path)

    # 1. Same-stem JSON in the same directory as the weight file
    candidate = os.path.join(weight_dir, stem + '.json')
    if os.path.exists(candidate):
        return candidate

    # 2. Pattern-match against known dataset names → built-in JSON
    name_lower = stem.lower()
    if 'cvsi' in name_lower:
        suffix = 'classCVSI-2015_indices.json'
    elif 'icdar2017' in name_lower:
        suffix = 'classICDAR2017_indices.json'
    elif 'siw' in name_lower:
        suffix = 'classSIW-13_indices.json'
    elif 'mle2e' in name_lower:
        suffix = 'classMLe2e_indices.json'
    else:
        suffix = 'class_indices.json'

    candidate = os.path.join(_STARNET_DIR, suffix)
    if os.path.exists(candidate):
        return candidate

    return None


def _load_class_map(json_path: str) -> dict[int, str]:
    """Load {int_index: class_name} from a class-index JSON file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    return {int(k): v for k, v in raw.items()}


# ── Model loading ───────────────────────────────────────────────────────────

def load_model(weight_path: str) -> tuple:
    """Load and cache a StarNet model for *weight_path*.

    Returns (model, class_map) where class_map is {int: str}.
    Raises RuntimeError if the class-index JSON cannot be found.
    """
    if weight_path in _model_cache:
        return _model_cache[weight_path]

    json_path = _resolve_class_json(weight_path)
    if json_path is None:
        raise RuntimeError(
            f'No class-index JSON found for weight {weight_path!r}. '
            'Place a matching .json file (same stem) next to the .pth file, '
            'or use a filename that contains a known dataset name '
            '(cvsi / icdar2017 / siw / mle2e).')

    class_map   = _load_class_map(json_path)
    num_classes = len(class_map)
    logger.info('StarNet: loading %s  (%d classes, json=%s)',
                weight_path, num_classes, json_path)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model  = _StarNet(num_classes=num_classes).to(device)

    # torch.load with weights_only was added in PyTorch 2.x;
    # fall back gracefully for older versions.
    try:
        state = torch.load(weight_path, map_location=device, weights_only=False)
    except TypeError:
        state = torch.load(weight_path, map_location=device)

    # Some checkpoints wrap weights under a sub-key.
    if isinstance(state, dict):
        for sub in ('state_dict', 'model', 'net'):
            if sub in state:
                state = state[sub]
                break

    # Try strict load first; fall back to non-strict for fine-tuned heads.
    try:
        model.load_state_dict(state, strict=True)
    except RuntimeError as e:
        logger.warning('StarNet strict load failed (%s), retrying with strict=False', e)
        model.load_state_dict(state, strict=False)

    model.eval()
    _model_cache[weight_path] = (model, class_map)
    logger.info('StarNet loaded successfully: %s', weight_path)
    return model, class_map


# ── Inference ───────────────────────────────────────────────────────────────

def classify_image(image_path: str, weight_path: str) -> dict:
    """Run StarNet inference on *image_path* using *weight_path*.

    Returns a dict with keys:
      lang_code   – ISO 639-1 code (or class name if no mapping)
      confidence  – top-1 probability as a percentage (0–100)
      all_langs   – list of top-5 dicts with lang/name_zh/name_en/prob
      class_name  – raw class name from the model's class map
    """
    model, class_map = load_model(weight_path)
    device = next(model.parameters()).device

    img    = Image.open(image_path).convert('RGB')
    tensor = _TRANSFORM(img).unsqueeze(0).to(device)

    with torch.no_grad():
        logits = model(tensor)                       # (1, num_classes)
        probs  = torch.softmax(logits, dim=1)[0]     # (num_classes,)

    top_idx   = int(probs.argmax().item())
    top_prob  = float(probs[top_idx].item())
    class_name = class_map.get(top_idx, 'unknown')
    lang_code  = _CLASS_TO_LANG.get(class_name.lower(), class_name.lower())
    confidence = round(top_prob * 100, 2)

    # Build top-5 probability list
    k = min(5, len(class_map))
    topk_vals, topk_idxs = torch.topk(probs, k)
    all_langs = []
    for v, i in zip(topk_vals.tolist(), topk_idxs.tolist()):
        cname = class_map.get(int(i), 'unknown')
        lcode = _CLASS_TO_LANG.get(cname.lower(), cname.lower())
        all_langs.append({
            'lang':    lcode,
            'name_zh': cname,   # app.py will overwrite with LANGUAGE_NAMES
            'name_en': cname,
            'prob':    round(v * 100, 1),
        })

    return {
        'lang_code':  lang_code,
        'confidence': confidence,
        'all_langs':  all_langs,
        'class_name': class_name,
    }
