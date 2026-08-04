"""古玉鉴真 — 模型架构"""

from .jade_model import JadeAuthModel
from .backbone import ConvNeXtV2Backbone
from .macro_stream import MacroStream
from .micro_stream import MicroStream
from .fusion import ViewCrossAttention
from .heads import EraHead, AuthHead

__all__ = [
    "JadeAuthModel",
    "ConvNeXtV2Backbone",
    "MacroStream",
    "MicroStream",
    "ViewCrossAttention",
    "EraHead",
    "AuthHead",
]
