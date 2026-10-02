"""sikaguard: explainable detection of French-language SMS and Mobile Money scams.

>>> from sikaguard import analyze
>>> result = analyze("Compte bloqué, envoyez votre code secret")  # doctest: +SKIP
>>> result.verdict  # doctest: +SKIP
'arnaque'
"""

from sikaguard.analyzer import Analyzer, analyze
from sikaguard.model import ModelIntegrityError
from sikaguard.result import Reason, Result

__version__ = "0.1.0.dev2"

__all__ = ["Analyzer", "ModelIntegrityError", "Reason", "Result", "__version__", "analyze"]
