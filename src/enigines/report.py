import os
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader

from src.enigines.evaluation import EvaluationResult
from src.logger.base_logger import BaseLogger
from src.modules.report.builders import (
    build_nper_data,
    build_randomness_data,
    build_scorecard_data,
    build_security_data,
    build_transparency_data,
)
from src.utils.types import RollRecord


class ReportEngine:
    def __init__(self, output_path: str, n_faces: int = 6) -> None:
        self._output_path = output_path
        self._n_faces = n_faces
        self._logger = BaseLogger(__name__)

        template_dir = Path(__file__).parent.parent / "modules" / "report"
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True,
        )

    def generate(
        self,
        programmable: EvaluationResult,
        rolls: List[RollRecord],
        tier: str = "LIGHT",
        non_programmable: Optional[dict] = None,
    ) -> str:
        """Render index.html from evaluation results and return its absolute path."""
        self._logger.info("Building report data...")

        randomness_data = (
            build_randomness_data(programmable.randomness, rolls, self._n_faces)
            if programmable.randomness is not None
            else None
        )
        security_data = (
            build_security_data(programmable.security)
            if programmable.security is not None
            else None
        )
        transparency_data = (
            build_transparency_data(programmable.transparency)
            if programmable.transparency is not None
            else None
        )
        nper_data = build_nper_data(non_programmable) if non_programmable else None
        scorecard_data = build_scorecard_data(programmable, non_programmable)

        template = self._env.get_template("template.html")
        html = template.render(
            mechanism=programmable.mechanism,
            generated_at=programmable.saved_at,
            tier=tier,
            randomness=randomness_data,
            security=security_data,
            transparency=transparency_data,
            nper=nper_data,
            scorecard=scorecard_data,
            significance_level=0.01,
        )

        abs_path = os.path.abspath(self._output_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(html)

        self._logger.info(f"Report written to {abs_path}")
        return abs_path
