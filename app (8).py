"""
Streamlit interface for the AI-Powered Mock Interview Platform.

Run locally:
    pip install streamlit
    streamlit run app.py

The interface has three phases: setup (paste a resume and job description),
interview (timed, adaptive questions), and report (the explainable result).
All interview logic lives in engine.py; this file only handles the screen.
"""

import json
import time

import streamlit as st
import streamlit.components.v1 as components

from engine import InterviewEngine, Config
from question_bank import extract_topics, extract_role

st.set_page_config(page_title="AI Mock Interview Platform", layout="centered")

BAND_COLORS = {"Strong": "#1e8e3e", "Average": "#e8710a", "Needs Improvement": "#c5221f"}

DEFAULT_RESUME = (
    "Backend engineer with three years of experience building Python services. "
    "Worked with Flask REST APIs, PostgreSQL databases, and core data structures. "
    "Contributed to the system design of a high-traffic web application and "
    "applied object oriented programming throughout."
)
DEFAULT_JD = (
    "We are hiring a Backend Python Developer. The role requires strong SQL, "
    "REST API design, object oriented programming, and system design skills. "
    "Familiarity with data structures and algorithms is expected."
)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def init_state():
    ss = st.session_state
    ss.setdefault("phase", "setup")
    ss.setdefault("engine", None)
    ss.setdefault("current_q", None)
    ss.setdefault("q_start", None)


def start_interview(resume_text: str, jd_text: str):
    ss = st.session_state
    topics = extract_topics(resume_text, jd_text)
    ss.engine = InterviewEngine(topics, resume_text, jd_text)
    ss.current_q = ss.engine.current_question()
    ss.q_start = time.time()
    ss.phase = "interview"


def submit_answer(answer_text: str):
    ss = st.session_state
    elapsed = time.time() - ss.q_start
    ss.engine.submit(ss.current_q, answer_text, elapsed)
    if ss.engine.is_finished():
        ss.phase = "report"
        return
    ss.current_q = ss.engine.current_question()
    if ss.current_q is None:
        ss.phase = "report"
    else:
        ss.q_start = time.time()


def restart():
    ss = st.session_state
    ss.phase = "setup"
    ss.engine = None
    ss.current_q = None
    ss.q_start = None


# ---------------------------------------------------------------------------
# Small UI helpers
# ---------------------------------------------------------------------------

def countdown_timer(seconds: float):
    """A client-side ticking countdown. The authoritative timing is server-side."""
    seconds = int(max(0, seconds))
    html = """
    <div id="cd" style="font-family: sans-serif; font-size: 1.25rem;
         font-weight: 600; padding: 6px 0;"></div>
    <script>
    var total = %d;
    var el = document.getElementById('cd');
    function render(s) {
        var m = Math.floor(s / 60), r = s %% 60;
        if (s <= 0) {
            el.textContent = 'Time is up. Submit now; over-time is penalized.';
            el.style.color = '#c5221f';
            return;
        }
        el.textContent = 'Time remaining: ' + m + ':' + (r < 10 ? '0' : '') + r;
        el.style.color = s <= 10 ? '#c5221f' : (s <= 30 ? '#e8710a' : '#1e8e3e');
    }
    render(total);
    var iv = setInterval(function () {
        total -= 1;
        if (total < 0) { clearInterval(iv); render(0); return; }
        render(total);
    }, 1000);
    </script>
    """ % seconds
    components.html(html, height=44)


def labelled_bar(label: str, value: float):
    st.markdown(f"**{label.replace('_', ' ').title()}** — {value:.0f} percent")
    st.progress(min(1.0, max(0.0, value / 100.0)))


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------

def render_setup():
    st.title("AI-Powered Mock Interview Platform")
    st.write(
        "Paste a resume and a job description. The platform reads both, selects "
        "relevant topics, and runs a timed, adaptive interview that adjusts to "
        "your performance and produces an explainable readiness score."
    )

    if st.button("Load a sample resume and job description"):
        st.session_state["resume_input"] = DEFAULT_RESUME
        st.session_state["jd_input"] = DEFAULT_JD
        st.rerun()

    resume = st.text_area("Candidate resume", key="resume_input", height=170,
                          placeholder="Paste the candidate resume here ...")
    jd = st.text_area("Job description", key="jd_input", height=140,
                      placeholder="Paste the job description here ...")

    if st.button("Start interview", type="primary"):
        if not resume.strip() or not jd.strip():
            st.warning("Please provide both a resume and a job description.")
        else:
            with st.spinner("Analyzing the resume and the job description ..."):
                topics = extract_topics(resume, jd)
                role = extract_role(jd)
            st.success(f"Detected role: {role}. Topics: {', '.join(topics)}.")
            start_interview(resume, jd)
            st.rerun()


def render_interview():
    ss = st.session_state
    engine = ss.engine
    q = ss.current_q
    if q is None:
        ss.phase = "report"
        st.rerun()

    st.title("Interview in progress")
    st.caption(f"Role: {engine.role}  |  Focus topics: {', '.join(engine.topics)}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Question", f"{engine.state.answered + 1} / {Config.MAX_QUESTIONS}")
    col2.metric("Difficulty", engine.state.current_difficulty.title())
    col3.metric("Running score", f"{engine.running_score():.0f}")

    st.divider()
    st.markdown(f"**Topic:** {q.topic.replace('_', ' ').title()}  |  "
                f"**Type:** {q.category.title()}  |  "
                f"**Time limit:** {q.time_limit} seconds")
    st.subheader(q.text)

    elapsed = time.time() - ss.q_start
    countdown_timer(q.time_limit - elapsed)

    answer = st.text_area("Your answer", key=f"answer_{engine.state.answered}",
                          height=200, placeholder="Type your answer here ...")

    left, right = st.columns([1, 1])
    if left.button("Submit answer", type="primary"):
        submit_answer(answer)
        st.rerun()
    if right.button("End interview early"):
        engine.state.finished = True
        engine.state.termination_reason = "Ended by the candidate."
        ss.phase = "report"
        st.rerun()


def render_report():
    engine = st.session_state.engine
    report = engine.report()
    score = report["interview_readiness_score"]
    band = report["readiness_band"]
    color = BAND_COLORS.get(band, "#444")

    st.title("Interview Readiness Report")

    st.markdown(
        f"""
        <div style="border: 2px solid {color}; border-radius: 14px;
             padding: 18px 22px; text-align: center;">
          <div style="font-size: 3rem; font-weight: 800; color: {color};">{score:.1f}</div>
          <div style="font-size: 1.1rem; color: #555;">Interview Readiness Score (out of 100)</div>
          <div style="font-size: 1.4rem; font-weight: 700; margin-top: 6px; color: {color};">{band}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    st.info(f"Hiring readiness: {report['hiring_readiness']}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Questions answered", report["questions_answered"])
    c2.metric("Time used (seconds)", f"{report['time_used_seconds']:.0f}")
    c3.metric("Ended early", "Yes" if report["terminated_early"] else "No")
    if report["termination_reason"]:
        st.caption(f"Reason the interview ended: {report['termination_reason']}")

    st.divider()
    st.subheader("Performance by skill area")
    if report["skill_breakdown"]:
        for topic, value in report["skill_breakdown"].items():
            labelled_bar(topic, value)
    else:
        st.write("No skill data was recorded.")

    st.subheader("Performance by evaluation dimension")
    for name, value in report["dimension_averages"].items():
        labelled_bar(name, value)

    st.divider()
    left, right = st.columns(2)
    with left:
        st.subheader("Strengths")
        if report["strengths"]:
            for t in report["strengths"]:
                st.write(f"- {t.replace('_', ' ').title()}")
        else:
            st.write("- None identified yet.")
    with right:
        st.subheader("Areas to improve")
        if report["weaknesses"]:
            for t in report["weaknesses"]:
                st.write(f"- {t.replace('_', ' ').title()}")
        else:
            st.write("- None identified.")

    st.subheader("Actionable feedback")
    for tip in report["actionable_feedback"]:
        st.write(f"- {tip}")

    with st.expander("Full transcript and per-answer scoring"):
        for i, turn in enumerate(report["transcript"], start=1):
            st.markdown(f"**Q{i} ({turn['difficulty']}, {turn['topic']})** "
                        f"— quality {turn['quality']:.2f}, "
                        f"{turn['points']:.1f} of {turn['points_possible']:.0f} points")
            st.caption(turn["rationale"])
            st.write(turn["dimensions"])

    st.divider()
    st.download_button(
        "Download report as JSON",
        data=json.dumps(report, indent=2),
        file_name="interview_readiness_report.json",
        mime="application/json",
    )
    if st.button("Start a new interview"):
        restart()
        st.rerun()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

init_state()
phase = st.session_state.phase
if phase == "setup":
    render_setup()
elif phase == "interview":
    render_interview()
else:
    render_report()
