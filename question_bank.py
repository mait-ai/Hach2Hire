"""
Question bank and lightweight resume / job-description analysis.

This module contains no external dependencies. It provides:
    - a tagged bank of technical, conceptual, behavioral, and scenario questions,
    - a skill taxonomy used to read a resume and a job description, and
    - helpers to select relevant topics and a likely role title.

The bank is intentionally easy to extend: add more Question entries and, if a
new skill is involved, add its trigger words to SKILL_TAXONOMY.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Question:
    qid: str
    topic: str          # for example: python, dsa, sql, oop, web, system_design, behavioral
    category: str       # technical, conceptual, behavioral, or scenario
    difficulty: str     # easy, medium, or hard
    text: str
    time_limit: int     # seconds allowed for the answer
    expected_keywords: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Skill taxonomy: maps a topic to the words that signal it in free text.
# ---------------------------------------------------------------------------

SKILL_TAXONOMY: dict[str, list[str]] = {
    "python": ["python", "pandas", "numpy", "flask", "django", "fastapi", "pytest"],
    "dsa": ["data structure", "algorithm", "leetcode", "complexity", "big o",
            "dynamic programming", "graph", "binary tree"],
    "sql": ["sql", "mysql", "postgres", "postgresql", "database", "rdbms",
            "query", "sqlite"],
    "oop": ["object oriented", "object-oriented", "oop", "design pattern",
            "inheritance", "encapsulation"],
    "web": ["rest", "api", "http", "backend", "frontend", "react", "node",
            "javascript", "express", "web"],
    "system_design": ["system design", "scalab", "architecture", "microservice",
                       "distributed", "load balanc", "caching", "kafka",
                       "docker", "kubernetes"],
}

ROLE_WORDS = ["engineer", "developer", "scientist", "analyst", "architect",
              "programmer", "sde", "swe"]


# ---------------------------------------------------------------------------
# The question bank.
# ---------------------------------------------------------------------------

QUESTIONS: list[Question] = [
    # python
    Question("py_e1", "python", "conceptual", "easy",
             "What is the difference between a list and a tuple in Python?",
             120, ["list", "tuple", "mutable", "immutable"]),
    Question("py_m1", "python", "conceptual", "medium",
             "Explain how Python manages memory, including reference counting and garbage collection.",
             180, ["reference counting", "garbage collection", "memory", "cyclic"]),
    Question("py_h1", "python", "technical", "hard",
             "How do generators work in Python, and when would you choose one over a list?",
             180, ["generator", "yield", "lazy", "memory", "iterator"]),

    # dsa
    Question("dsa_e1", "dsa", "technical", "easy",
             "What is the time complexity of binary search on a sorted array, and why?",
             90, ["binary search", "log n", "sorted", "divide"]),
    Question("dsa_m1", "dsa", "conceptual", "medium",
             "Explain how a hash table works and how it handles collisions.",
             180, ["hash", "collision", "bucket", "chaining", "load factor"]),
    Question("dsa_h1", "dsa", "technical", "hard",
             "Describe an approach to detect a cycle in a linked list and state its complexity.",
             180, ["cycle", "linked list", "slow", "fast", "pointer"]),

    # sql
    Question("sql_e1", "sql", "technical", "easy",
             "What is the difference between WHERE and HAVING in SQL?",
             120, ["where", "having", "group by", "aggregate", "filter"]),
    Question("sql_m1", "sql", "technical", "medium",
             "Explain the difference between an INNER JOIN and a LEFT JOIN.",
             150, ["inner join", "left join", "matching", "null", "rows"]),
    Question("sql_h1", "sql", "conceptual", "hard",
             "What is database indexing, and what are the trade-offs of adding an index?",
             180, ["index", "lookup", "write", "storage", "trade-off"]),

    # oop
    Question("oop_e1", "oop", "conceptual", "easy",
             "What are the four pillars of object-oriented programming?",
             120, ["encapsulation", "inheritance", "polymorphism", "abstraction"]),
    Question("oop_m1", "oop", "conceptual", "medium",
             "Explain the difference between composition and inheritance and when to prefer each.",
             180, ["composition", "inheritance", "has-a", "coupling", "reuse"]),
    Question("oop_h1", "oop", "conceptual", "hard",
             "What are the SOLID principles, and why does dependency inversion matter?",
             200, ["solid", "single responsibility", "open closed",
                   "dependency inversion", "abstraction"]),

    # web
    Question("web_e1", "web", "technical", "easy",
             "What is the difference between the HTTP GET and POST methods?",
             120, ["get", "post", "idempotent", "body", "query"]),
    Question("web_m1", "web", "conceptual", "medium",
             "Explain what a REST API is and the principles behind it.",
             180, ["rest", "stateless", "resource", "http", "endpoint"]),
    Question("web_h1", "web", "scenario", "hard",
             "How would you secure a REST API that handles user authentication?",
             200, ["token", "https", "hashing", "authentication",
                   "authorization", "rate limit"]),

    # system_design
    Question("sd_e1", "system_design", "scenario", "easy",
             "What is the purpose of a load balancer in a web system?",
             120, ["load balancer", "distribute", "traffic", "availability"]),
    Question("sd_m1", "system_design", "scenario", "medium",
             "How would you design a URL shortening service at a high level?",
             240, ["hash", "database", "redirect", "unique", "cache"]),
    Question("sd_h1", "system_design", "scenario", "hard",
             "How would you scale a read-heavy application to serve millions of users?",
             300, ["caching", "replication", "sharding", "load balancer",
                   "horizontal", "database"]),

    # behavioral (no expected keywords; accuracy falls back to relevance)
    Question("beh_e1", "behavioral", "behavioral", "easy",
             "Tell me about a project you are proud of and your specific role in it.",
             150, []),
    Question("beh_m1", "behavioral", "behavioral", "medium",
             "Describe a time you faced a conflict in a team and how you resolved it.",
             180, []),
    Question("beh_m2", "behavioral", "behavioral", "medium",
             "Tell me about a time you had to learn a new technology quickly.",
             180, []),
    Question("beh_h1", "behavioral", "behavioral", "hard",
             "Describe a significant technical challenge you faced and how you solved it.",
             200, []),
]


# ---------------------------------------------------------------------------
# Analysis helpers.
# ---------------------------------------------------------------------------

def extract_topics(resume_text: str, jd_text: str, max_topics: int = 5) -> list[str]:
    """Return the relevant topics, most-signalled first, always ending with behavioral."""
    combined = f"{resume_text}\n{jd_text}".lower()

    scored: list[tuple[str, int]] = []
    for topic, triggers in SKILL_TAXONOMY.items():
        hits = sum(combined.count(trigger) for trigger in triggers)
        if hits > 0:
            scored.append((topic, hits))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    topics = [topic for topic, _ in scored[:max_topics]]

    # Sensible default if nothing matched.
    if not topics:
        topics = ["python", "dsa", "oop"]

    if "behavioral" not in topics:
        topics.append("behavioral")
    return topics


def extract_role(jd_text: str) -> str:
    """Return a likely role title from the job description, or a neutral fallback."""
    skip = {"a", "an", "the", "for", "as", "we", "are", "is", "am", "hiring",
            "seeking", "looking", "to", "of", "and", "our", "this", "role",
            "position", "strong", "you", "your", "join", "team", "now",
            "candidate", "ideal", "with", "in", "on", "who"}
    tokens = re.findall(r"[a-z][a-z+#]*", jd_text.lower())
    for i, token in enumerate(tokens):
        if token in ROLE_WORDS:
            quals: list[str] = []
            j = i - 1
            while j >= 0 and len(quals) < 2:
                word = tokens[j]
                if word in skip or len(word) <= 1:
                    break
                quals.insert(0, word)
                j -= 1
            return " ".join(quals + [token]).title()
    return "the target role"


def questions_for_topics(topics: list[str]) -> list[Question]:
    """Return all bank questions whose topic is in the selected list."""
    chosen = set(topics)
    return [q for q in QUESTIONS if q.topic in chosen]
