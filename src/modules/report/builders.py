from collections import Counter
from typing import List, Optional

from src.enigines.evaluation import EvaluationResult
from src.modules.randomness.randomness_tests import RandomnessEvaluationResult
from src.modules.security.security_tests import SecurityEvaluationResult
from src.modules.transparency.transparency_tests import TransparencyEvaluationResult
from src.utils.types import RollRecord


def build_randomness_data(
    result: RandomnessEvaluationResult,
    rolls: List[RollRecord],
    n_faces: int,
) -> dict:
    outcomes = [r.outcome for r in rolls]
    face_labels = list(range(1, n_faces + 1))
    counts = Counter(min(n_faces, max(1, int(o))) for o in outcomes)
    observed = [counts.get(f, 0) for f in face_labels]
    expected = round(len(outcomes) / n_faces, 2) if n_faces > 0 else 0

    data: dict = {
        "stats": {"n_rolls": result.n_rolls, "n_bits": result.n_bits},
        "histogram": {
            "labels": face_labels,
            "observed": observed,
            "expected": expected,
        },
        "sanity_check": None,
        "distribution_tests": [],
        "server_seed_entropy": None,
        "nist_light": None,
        "nist_in_depth": None,
        "entropy_monitoring": None,
    }

    if result.light is not None:
        light = result.light

        data["sanity_check"] = {
            "passed": light.sanity_check.passed,
            "chi_square_stat": round(light.sanity_check.chi_square_stat, 4),
            "p_value": light.sanity_check.p_value,
            "message": light.sanity_check.message,
        }

        data["distribution_tests"] = [
            {
                "name": light.cramer_von_mises.test_name,
                "p_value": light.cramer_von_mises.p_value,
                "passed": light.cramer_von_mises.passed,
                "parameters": light.cramer_von_mises.parameters_used,
            },
            {
                "name": light.runs_independence.test_name,
                "p_value": light.runs_independence.p_value,
                "passed": light.runs_independence.passed,
                "parameters": light.runs_independence.parameters_used,
            },
        ]

        data["server_seed_entropy"] = {
            "passed": light.server_seed_min_entropy.passed,
            "message": light.server_seed_min_entropy.message,
            "details": light.server_seed_min_entropy.details,
        }

        if light.nist_light is not None:
            data["nist_light"] = [
                {"name": tr.test_name, "p_value": tr.p_value, "passed": tr.passed}
                for tr in light.nist_light.values()
            ]

    if result.in_depth is not None:
        in_depth = result.in_depth

        if in_depth.nist_in_depth is not None:
            data["nist_in_depth"] = [
                {"name": tr.test_name, "p_value": tr.p_value, "passed": tr.passed}
                for tr in in_depth.nist_in_depth.values()
            ]

        if in_depth.entropy_monitoring:
            em = in_depth.entropy_monitoring
            data["entropy_monitoring"] = {
                "repetition_count": {
                    "alarms_triggered": em["repetition_count"].alarms_triggered,
                    "passed": em["repetition_count"].passed,
                    "parameters": em["repetition_count"].parameters_used,
                },
                "adaptive_proportion": {
                    "alarms_triggered": em["adaptive_proportion"].alarms_triggered,
                    "passed": em["adaptive_proportion"].passed,
                    "parameters": em["adaptive_proportion"].parameters_used,
                },
            }

    return data


def build_security_data(result: SecurityEvaluationResult) -> dict:
    data: dict = {
        "stats": {"n_rolls": result.n_rolls},
        "light": None,
    }

    if result.light is not None:
        light = result.light
        data["light"] = {
            "seed_reuse": {
                "passed": light.seed_reuse.passed,
                "message": light.seed_reuse.message,
                "details": light.seed_reuse.details,
            },
            "nonce_presence": {
                "passed": light.nonce_presence.passed,
                "message": light.nonce_presence.message,
                "details": light.nonce_presence.details,
            },
            "nonce_uniqueness": {
                "passed": light.nonce_uniqueness.passed,
                "message": light.nonce_uniqueness.message,
                "details": light.nonce_uniqueness.details,
            },
            "nonce_min_entropy": round(light.nonce_min_entropy, 4),
        }

    return data


def build_transparency_data(result: TransparencyEvaluationResult) -> dict:
    data: dict = {
        "stats": {"n_rolls": result.n_rolls},
        "light": None,
    }

    if result.light is not None:
        light = result.light
        data["light"] = {
            "determinism": {
                "passed": light.determinism.passed,
                "message": light.determinism.message,
                "details": light.determinism.details,
            },
            "mapping_reproducibility": {
                "passed": light.mapping_reproducibility.passed,
                "message": light.mapping_reproducibility.message,
                "details": light.mapping_reproducibility.details,
            },
        }

    return data


def build_nper_data(nper: dict) -> dict:
    scores = nper.get("verificationTransparencyScores", {})

    chart_labels = [
        "Algorithm Disclosure",
        "Entropy Source Disclosure",
        "Historical Auditability",
        "Verification Tool (In-Platform)",
        "Verification Tool (Third-Party)",
        "Verification Friction (Expert)",
        "Verification Friction (Non-Expert)",
    ]

    def _score(key: str, sub: Optional[str] = None) -> float:
        block = scores.get(key, {})
        if sub:
            val = block.get(sub, 0.0)
        else:
            val = block.get("score", 0.0)
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    chart_scores = [
        _score("algorithmDisclosure"),
        _score("entropySourceDisclosure"),
        _score("historicalAuditabilityWindow"),
        _score("verificationToolAvailability", "inPlatformScore"),
        _score("verificationToolAvailability", "independentThirdPartyScore"),
        _score("verificationFriction", "expertPathScore"),
        _score("verificationFriction", "nonExpertPathScore"),
    ]

    def _justification(key: str) -> str:
        return scores.get(key, {}).get("justification", "")

    transparency_chart = {
        "labels": chart_labels,
        "scores": chart_scores,
        "justifications": {
            "algorithmDisclosure": _justification("algorithmDisclosure"),
            "entropySourceDisclosure": _justification("entropySourceDisclosure"),
            "historicalAuditabilityWindow": _justification("historicalAuditabilityWindow"),
            "verificationToolAvailability": _justification("verificationToolAvailability"),
            "verificationFriction": _justification("verificationFriction"),
        },
    }

    return {
        "mechanismId": nper.get("mechanismId", ""),
        "bareSHA256Check": nper.get("bareSHA256Check"),
        "csprngCompliance": nper.get("csprngCompliance"),
        "clientSeedGenerationSource": nper.get("clientSeedGenerationSource"),
        "commitmentTiming": nper.get("commitmentTiming"),
        "algorithmConformanceVsImplementationSecurity": nper.get(
            "algorithmConformanceVsImplementationSecurity"
        ),
        "attackVectorClassification": nper.get("attackVectorClassification"),
        "vrfQinpUniquenessEnforcement": nper.get("vrfQinpUniquenessEnforcement"),
        "drandFutureRoundCommitmentStrategy": nper.get("drandFutureRoundCommitmentStrategy"),
        "dkgPhaseIntegrity": nper.get("dkgPhaseIntegrity"),
        "predictionResistance": nper.get("predictionResistance"),
        "backwardsForwardStateInference": nper.get("backwardsForwardStateInference"),
        "nonceManagement": nper.get("nonceManagement"),
        "clientSeedRotationBehaviour": nper.get("clientSeedRotationBehaviour"),
        "vrfSecurityAssessment": nper.get("vrfSecurityAssessment"),
        "verificationTransparencyScores": scores,
        "transparency_chart_data": transparency_chart,
    }


def build_scorecard_data(per: EvaluationResult, nper: Optional[dict]) -> dict:
    rows = []

    # Randomness
    if per.randomness and per.randomness.light:
        light = per.randomness.light
        dist_passed = sum(
            1 for t in [light.cramer_von_mises, light.runs_independence] if t.passed
        )
        nist_total = len(light.nist_light) if light.nist_light else 0
        nist_passed = sum(1 for t in light.nist_light.values() if t.passed) if light.nist_light else 0

        if per.randomness.in_depth and per.randomness.in_depth.nist_in_depth:
            nist_total += len(per.randomness.in_depth.nist_in_depth)
            nist_passed += sum(
                1 for t in per.randomness.in_depth.nist_in_depth.values() if t.passed
            )

        rows.append({"domain": "Randomness", "metric": "Distribution tests", "value": f"{dist_passed} / 2", "passed": dist_passed == 2})
        if nist_total:
            rows.append({"domain": "Randomness", "metric": "NIST SP 800-22 tests", "value": f"{nist_passed} / {nist_total}", "passed": nist_passed == nist_total})
        rows.append({"domain": "Randomness", "metric": "Server seed entropy", "value": "PASS" if light.server_seed_min_entropy.passed else "FAIL", "passed": light.server_seed_min_entropy.passed})

    # Security
    if per.security and per.security.light:
        sl = per.security.light
        checks = [sl.seed_reuse.passed, sl.nonce_presence.passed, sl.nonce_uniqueness.passed]
        sec_passed = sum(checks)
        rows.append({"domain": "Security", "metric": "Binary checks", "value": f"{sec_passed} / 3", "passed": sec_passed == 3})

    # Transparency
    if per.transparency and per.transparency.light:
        tl = per.transparency.light
        tr_checks = [tl.determinism.passed, tl.mapping_reproducibility.passed]
        tr_passed = sum(tr_checks)
        rows.append({"domain": "Transparency", "metric": "Verification checks", "value": f"{tr_passed} / 2", "passed": tr_passed == 2})

    # NPER
    if nper:
        applicable_sections = [
            "bareSHA256Check",
            "csprngCompliance",
            "clientSeedGenerationSource",
            "commitmentTiming",
            "algorithmConformanceVsImplementationSecurity",
            "attackVectorClassification",
            "predictionResistance",
            "backwardsForwardStateInference",
            "nonceManagement",
            "clientSeedRotationBehaviour",
        ]
        conditional = [
            "vrfQinpUniquenessEnforcement",
            "drandFutureRoundCommitmentStrategy",
            "dkgPhaseIntegrity",
            "vrfSecurityAssessment",
        ]
        for key in conditional:
            block = nper.get(key, {})
            if isinstance(block, dict) and block.get("applicable", False):
                applicable_sections.append(key)

        total = len(applicable_sections)
        rows.append({"domain": "Non-Programmable", "metric": "Applicable checks present", "value": f"{total}", "passed": True})

    return {"rows": rows}
