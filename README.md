# AI-Powered Mock Interview Platform

A self-contained mock interview platform that reads a candidate resume and a job
description, runs a timed and adaptive interview, and produces an explainable
Interview Readiness Score. Built for the Hack2Hire hackathon.

Everything runs locally in Python with no external model or API key. The scoring
is fully deterministic and transparent, which is what makes the result
explainable and reproducible.

## Demo Video (required)

> Replace this line with a link to your screen recording of the live, working
> platform. The submission rules require this video to appear in the README.

For example: `Watch the demo: https://your-video-link`

## What it does

- Reads a resume and a job description and selects the relevant interview topics.
- Asks technical, conceptual, behavioral, and scenario questions.
- Adapts difficulty up after strong answers and down after weak ones.
- Enforces a time limit per question and penalizes over-time answers.
- Ends the interview early when performance falls below a threshold.
- Scores each answer on accuracy, clarity, depth, relevance, and time efficiency.
- Produces a final readiness score, a skill breakdown, strengths and weaknesses,
  actionable feedback, and a hiring readiness verdict for the role.

## How it works

The platform separates the interview logic from the screen, which keeps the
structure clean and testable.

- `engine.py` is the stateful brain. It tracks the running state, adapts the
  difficulty, applies the termination rules, and builds the final report.
- `evaluation.py` scores a single answer across the five dimensions and combines
  them into one quality value. This layer is deterministic and explainable, and
  it can be swapped for a model-based evaluator without changing anything else.
- `question_bank.py` holds the tagged question bank and the resume and
  job-description analysis (skill extraction and role detection).
- `app.py` is the Streamlit interface: setup, the timed interview loop, and the
  report.
- `test_core.py` simulates strong and weak candidates to verify the rules.

## Scoring rules (explainable)

These are the exact rules the engine applies. They live in `Config` inside
`engine.py` and in `DIMENSION_WEIGHTS` inside `evaluation.py`, so they are easy
to read and adjust.

- Difficulty levels and base points: easy is 10 points, medium is 20, hard is 30.
- Dimension weights: accuracy 0.35, relevance 0.20, depth 0.20, clarity 0.10,
  time efficiency 0.15. These sum to 1.0 and produce a quality value from 0 to 1.
- Points for an answer equal the base points for its difficulty multiplied by the
  quality value.
- Adaptive difficulty: a quality of 0.60 or higher is a good answer. After two
  good answers in a row the difficulty rises one level. After a weak answer it
  drops one level, or stabilizes if it is already at easy.
- Time handling: an answer within the limit scores well on time efficiency. An
  answer that exceeds the limit scores zero on time efficiency and is flagged as
  incomplete.
- Early termination, any of: ten questions answered, the running score below 40
  after at least three answers, three weak answers in a row, or the question pool
  exhausted.
- Final score: total points earned divided by total points possible, times 100.
- Readiness bands: 75 and above is Strong, 50 and above is Average, below 50 is
  Needs Improvement.
- Hiring readiness is mapped from the band and the detected role.

## Tech stack

- Python 3.
- Streamlit for the interface.
- The standard library only for the engine, the evaluator, and the question bank.
- No external model, API key, billing, or network access is required.

## Project structure

- `app.py` — Streamlit interface.
- `engine.py` — interview state machine, adaptation, termination, and report.
- `evaluation.py` — the five-dimension answer evaluator.
- `question_bank.py` — question bank and resume / job-description analysis.
- `test_core.py` — headless verification of the rules.
- `requirements.txt` — the single dependency.
- `sample_resume.txt`, `sample_jd.txt` — example inputs.

## Setup and run

1. Install the one dependency:
   - `pip install -r requirements.txt`
2. Start the platform:
   - `streamlit run app.py`
3. The app opens in your browser. Use the sample button or paste your own resume
   and job description, then start the interview.

To run the rule checks without the interface:

- `python test_core.py`

## Optional: deploy for an edge

The submission rules state that hosting is optional but adds an edge. Streamlit
Community Cloud deploys directly from a public GitHub repository at no cost.
Connect the repository and point it at `app.py`.

## Extending the platform

- Add questions: append `Question` entries in `question_bank.py`. If a new skill
  is involved, add its trigger words to `SKILL_TAXONOMY`.
- Plug in a model later: replace the body of `evaluate_answer` in `evaluation.py`
  so it returns the same shape. Nothing else needs to change.
