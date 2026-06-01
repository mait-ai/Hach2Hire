"""
The interview engine: the stateful brain of the platform.

It is driven one turn at a time, which suits an interactive interface. For each
answer it scores the response, updates the running state, adapts the difficulty,
and checks the termination rules. At the end it produces an explainable report.

All rules live in Config so they can be read and adjusted in one place. They are
restated in the README so the scoring is fully transparent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from question_bank import Question, questions_for_topics, extract_role
from evaluation import evaluate_answer, _content_words


class Config:
    DIFFICULTY_LADDER = ["easy", "medium", "hard"]
    START_DIFFICULTY = "easy"
    BASE_POINTS = {"easy": 10.0, "medium": 20.0, "hard": 30.0}

    GOOD_ANSWER_QUALITY = 0.60       # quality at or above this counts as a good answer
    PROMOTE_AFTER_GOOD = 2           # consecutive good answers needed to raise difficulty
    DEMOTE_AFTER_POOR = 1            # poor answers needed to lower difficulty, else stabilize

    MAX_QUESTIONS = 10
    MIN_QUESTIONS_BEFORE_CUT = 3     # do not terminate on score before this many answers
    SCORE_FLOOR = 40.0               # end early if the running score falls below this
    MAX_CONSECUTIVE_POOR = 3         # end early after this many weak answers in a row

    # Final readiness bands, matching the categories named in the problem statement.
    BANDS = [(75.0, "Strong"), (50.0, "Average"), (0.0, "Needs Improvement")]


@dataclass
class TurnRecord:
    qid: str
    topic: str
    category: str
    difficulty: str
    question: str
    answer: str
    time_taken: float
    time_limit: int
    dimensions: dict
    quality: float
    points: float
    points_possible: float
    incomplete: bool
    rationale: str


@dataclass
class InterviewState:
    total_points: float = 0.0
    max_points: float = 0.0
    answered: int = 0
    current_difficulty: str = Config.START_DIFFICULTY
    time_used: float = 0.0
    consecutive_good: int = 0
    consecutive_poor: int = 0
    finished: bool = False
    termination_reason: Optional[str] = None
    asked_ids: set = field(default_factory=set)
    turns: list = field(default_factory=list)
    topic_totals: dict = field(default_factory=dict)   # topic -> [earned, possible]


class InterviewEngine:
    def __init__(self, topics: list[str], resume_text: str = "", jd_text: str = ""):
        if not topics:
            raise ValueError("At least one topic is required to start an interview.")
        self.topics = topics
        self.role = extract_role(jd_text)
        self.jd_terms = _content_words(jd_text)
        self._pool = questions_for_topics(topics)
        if not self._pool:
            raise ValueError("No questions are available for the selected topics.")
        self.state = InterviewState()

    # -- normalized running score (0 to 100) --
    def running_score(self) -> float:
        if self.state.max_points <= 0:
            return 0.0
        return round(self.state.total_points / self.state.max_points * 100.0, 2)

    # -- choose the next question --
    def current_question(self) -> Optional[Question]:
        if self.state.finished:
            return None
        unused = [q for q in self._pool if q.qid not in self.state.asked_ids]
        if not unused:
            return None

        ladder = Config.DIFFICULTY_LADDER
        target = self.state.current_difficulty
        # Prefer the current difficulty, then the nearest available difficulty.
        order = sorted(
            ladder,
            key=lambda d: abs(ladder.index(d) - ladder.index(target)),
        )
        for difficulty in order:
            candidates = [q for q in unused if q.difficulty == difficulty]
            if candidates:
                # Rotate topics for variety: prefer the least-asked topic.
                asked_per_topic = {t: 0 for t in self.topics}
                for turn in self.state.turns:
                    asked_per_topic[turn.topic] = asked_per_topic.get(turn.topic, 0) + 1
                candidates.sort(key=lambda q: asked_per_topic.get(q.topic, 0))
                return candidates[0]
        return unused[0]

    # -- submit an answer and advance the state --
    def submit(self, question: Question, answer_text: str, time_taken: float) -> TurnRecord:
        if self.state.finished:
            raise RuntimeError("The interview has already finished.")

        result = evaluate_answer(question, answer_text, time_taken, self.jd_terms)
        quality = result["quality"]
        base = Config.BASE_POINTS.get(question.difficulty, 10.0)
        points = round(base * quality, 2)

        # Update totals.
        self.state.total_points += points
        self.state.max_points += base
        self.state.time_used += time_taken
        self.state.answered += 1
        self.state.asked_ids.add(question.qid)

        topic_total = self.state.topic_totals.setdefault(question.topic, [0.0, 0.0])
        topic_total[0] += points
        topic_total[1] += base

        # Update good / poor streaks.
        if quality >= Config.GOOD_ANSWER_QUALITY and not result["incomplete"]:
            self.state.consecutive_good += 1
            self.state.consecutive_poor = 0
        else:
            self.state.consecutive_poor += 1
            self.state.consecutive_good = 0

        record = TurnRecord(
            qid=question.qid, topic=question.topic, category=question.category,
            difficulty=question.difficulty, question=question.text,
            answer=answer_text.strip(), time_taken=round(time_taken, 1),
            time_limit=question.time_limit, dimensions=result["dimensions"],
            quality=quality, points=points, points_possible=base,
            incomplete=result["incomplete"], rationale=result["rationale"],
        )
        self.state.turns.append(record)

        # Check termination, then adapt difficulty for the next question.
        self._check_termination()
        if not self.state.finished:
            self._adapt_difficulty()
        return record

    def _adapt_difficulty(self) -> None:
        ladder = Config.DIFFICULTY_LADDER
        pos = ladder.index(self.state.current_difficulty)
        if self.state.consecutive_good >= Config.PROMOTE_AFTER_GOOD and pos < len(ladder) - 1:
            self.state.current_difficulty = ladder[pos + 1]
            self.state.consecutive_good = 0
        elif self.state.consecutive_poor >= Config.DEMOTE_AFTER_POOR and pos > 0:
            self.state.current_difficulty = ladder[pos - 1]
            self.state.consecutive_poor = 0
        # Otherwise the difficulty stabilizes.

    def _check_termination(self) -> None:
        s = self.state
        if s.answered >= Config.MAX_QUESTIONS:
            s.finished, s.termination_reason = True, "Reached the maximum number of questions."
            return
        if s.consecutive_poor >= Config.MAX_CONSECUTIVE_POOR:
            s.finished, s.termination_reason = True, "Several weak answers in a row."
            return
        if s.answered >= Config.MIN_QUESTIONS_BEFORE_CUT and self.running_score() < Config.SCORE_FLOOR:
            s.finished, s.termination_reason = True, "Performance fell below the readiness threshold."
            return
        if all(q.qid in s.asked_ids for q in self._pool):
            s.finished, s.termination_reason = True, "All available questions were answered."

    def is_finished(self) -> bool:
        if not self.state.finished:
            self._check_termination()
        return self.state.finished

    # -- final, explainable report --
    def report(self) -> dict:
        s = self.state
        score = self.running_score()
        band = next(label for floor, label in Config.BANDS if score >= floor)

        skill_breakdown = {
            topic: round(earned / possible * 100.0, 1) if possible else 0.0
            for topic, (earned, possible) in s.topic_totals.items()
        }
        strengths = sorted((t for t, v in skill_breakdown.items() if v >= 70.0),
                           key=lambda t: skill_breakdown[t], reverse=True)
        weaknesses = sorted((t for t, v in skill_breakdown.items() if v < 50.0),
                            key=lambda t: skill_breakdown[t])

        dimension_avg = self._dimension_averages()
        early = s.finished and s.answered < Config.MAX_QUESTIONS and \
            s.termination_reason not in (None, "All available questions were answered.")

        return {
            "interview_readiness_score": score,
            "readiness_band": band,
            "hiring_readiness": self._hiring_verdict(band),
            "questions_answered": s.answered,
            "time_used_seconds": round(s.time_used, 1),
            "terminated_early": early,
            "termination_reason": s.termination_reason,
            "skill_breakdown": skill_breakdown,
            "dimension_averages": dimension_avg,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "actionable_feedback": self._feedback(weaknesses, dimension_avg, skill_breakdown),
            "transcript": [self._turn_summary(t) for t in s.turns],
        }

    def _dimension_averages(self) -> dict:
        if not self.state.turns:
            return {}
        names = ["accuracy", "relevance", "depth", "clarity", "time_efficiency"]
        totals = {n: 0.0 for n in names}
        for turn in self.state.turns:
            for n in names:
                totals[n] += turn.dimensions[n]
        count = len(self.state.turns)
        return {n: round(totals[n] / count * 100.0, 1) for n in names}

    def _hiring_verdict(self, band: str) -> str:
        if band == "Strong":
            return f"Recommended for {self.role}."
        if band == "Average":
            return f"Borderline: promising, but needs more polish for {self.role}."
        return f"Not yet ready for {self.role}; focused practice is advised."

    def _feedback(self, weaknesses: list[str], dimension_avg: dict,
                  skill_breakdown: dict) -> list[str]:
        tips = []
        advice = {
            "accuracy": "Tighten technical accuracy by naming the core concepts each question targets.",
            "relevance": "Stay on point: answer the exact question before adding extra detail.",
            "depth": "Add depth with concrete examples, trade-offs, and the reasoning behind choices.",
            "clarity": "Improve clarity by leading with a one-line summary, then the supporting detail.",
            "time_efficiency": "Manage time better: outline the answer first so you finish within the limit.",
        }
        # Address the two weakest dimensions.
        for name, _ in sorted(dimension_avg.items(), key=lambda kv: kv[1])[:2]:
            if dimension_avg.get(name, 100) < 70:
                tips.append(advice[name])
        # Name the weakest topics.
        for topic in weaknesses[:2]:
            tips.append(f"Strengthen {topic.replace('_', ' ')} fundamentals before the next interview.")
        if not tips:
            tips.append("Strong all-round performance; keep practising harder questions to stay sharp.")
        return tips

    @staticmethod
    def _turn_summary(turn: TurnRecord) -> dict:
        return {
            "qid": turn.qid, "topic": turn.topic, "difficulty": turn.difficulty,
            "quality": turn.quality, "points": turn.points,
            "points_possible": turn.points_possible, "time_taken": turn.time_taken,
            "time_limit": turn.time_limit, "incomplete": turn.incomplete,
            "dimensions": turn.dimensions, "rationale": turn.rationale,
        }
