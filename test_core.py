"""Headless verification of the engine. Run: python test_core.py"""

import json

from engine import InterviewEngine
from question_bank import extract_topics, extract_role

RESUME = """Backend engineer with 3 years building Python services.
Experience with Flask REST APIs, PostgreSQL databases, and data structures.
Worked on system design for a high-traffic application."""

JD = """We are hiring a Backend Python Developer. The role requires strong SQL,
REST API design, object oriented programming, and system design skills."""


def strong_answer(question):
    """An answer that covers the expected concepts well, within the time limit."""
    if question.expected_keywords:
        body = ", ".join(question.expected_keywords)
        text = (f"In short, the key idea is {question.expected_keywords[0]}. "
                f"It involves {body}. A concrete example makes the trade-offs clear, "
                f"and choosing the right approach depends on the situation.")
    else:
        text = ("I led a project where I owned the backend service end to end. "
                "I broke the work into clear milestones and communicated progress. "
                "When a conflict arose, I listened, found common ground, and we shipped on time.")
    return text, question.time_limit * 0.6


def weak_answer(question):
    """A short, off-target answer delivered slowly."""
    return "I am not sure, maybe.", question.time_limit * 1.1


def run(label, answer_fn):
    print(f"\n==================== {label} ====================")
    topics = extract_topics(RESUME, JD)
    print("Topics selected:", topics)
    print("Role detected:", extract_role(JD))

    engine = InterviewEngine(topics, RESUME, JD)
    while not engine.is_finished():
        q = engine.current_question()
        if q is None:
            break
        answer, t = answer_fn(q)
        rec = engine.submit(q, answer, t)
        print(f"  [{rec.difficulty:<6}] {rec.topic:<14} "
              f"quality={rec.quality:.2f} points={rec.points:5.1f} "
              f"running={engine.running_score():5.1f}")

    report = engine.report()
    print("--- REPORT ---")
    print("Score:", report["interview_readiness_score"], "| Band:", report["readiness_band"])
    print("Hiring:", report["hiring_readiness"])
    print("Answered:", report["questions_answered"],
          "| Early stop:", report["terminated_early"],
          "| Reason:", report["termination_reason"])
    print("Skill breakdown:", report["skill_breakdown"])
    print("Dimension averages:", report["dimension_averages"])
    print("Strengths:", report["strengths"], "| Weaknesses:", report["weaknesses"])
    print("Feedback:")
    for tip in report["actionable_feedback"]:
        print("   -", tip)
    # Basic sanity checks.
    assert 0.0 <= report["interview_readiness_score"] <= 100.0
    assert report["questions_answered"] >= 1
    assert json.dumps(report)  # must be JSON serializable
    return report


if __name__ == "__main__":
    strong = run("STRONG CANDIDATE", strong_answer)
    weak = run("WEAK CANDIDATE", weak_answer)
    assert strong["interview_readiness_score"] > weak["interview_readiness_score"]
    print("\nAll checks passed.")
