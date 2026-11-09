from flask import Flask, render_template, request, jsonify
import json
import os
import re
import pandas as pd
from difflib import SequenceMatcher

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(BASE_DIR, "dataset", "courses.json")
EXCEL_FILE = os.path.join(BASE_DIR, "ATI_Gampaha_Chatbot_QA.xlsx")


# ----------------------------------
# Load course details from JSON
# ----------------------------------
def load_courses():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            return data.get("courses", [])

        return []

    except FileNotFoundError:
        app.logger.error("JSON file not found: %s", DATA_FILE)
        return []

    except (json.JSONDecodeError, OSError) as error:
        app.logger.error("JSON loading error: %s", error)
        return []


# ----------------------------------
# Load questions and answers from Excel
# ----------------------------------
def load_excel_qa():
    try:
        df = pd.read_excel(EXCEL_FILE)

        df.columns = (
            df.columns.astype(str)
            .str.strip()
            .str.lower()
        )

        if "question" not in df.columns or "answer" not in df.columns:
            app.logger.error(
                "Excel must contain Question and Answer columns."
            )
            return [], []

        df = df.dropna(subset=["question", "answer"])

        questions = []
        answers = []

        for _, row in df.iterrows():
            question = str(row["question"]).strip()
            answer = str(row["answer"]).strip()

            if (
                question
                and answer
                and question.lower() != "nan"
                and answer.lower() != "nan"
            ):
                questions.append(question)
                answers.append(answer)

        app.logger.info("Excel questions loaded: %s", len(questions))
        return questions, answers

    except FileNotFoundError:
        app.logger.error("Excel file not found: %s", EXCEL_FILE)
        return [], []

    except Exception:
        app.logger.exception("Excel loading error")
        return [], []


# ----------------------------------
# Normalize text for matching
# ----------------------------------
def normalize_text(text):
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


# ----------------------------------
# Find the best answer from Excel
# ----------------------------------
def find_excel_answer(user_message, questions, answers):
    if not questions:
        return None

    user_text = normalize_text(user_message)

    normalized_questions = [
        normalize_text(question) for question in questions
    ]

    # Exact match
    for index, question in enumerate(normalized_questions):
        if user_text == question:
            return answers[index]

    # Full Excel question contained in the user's message
    for index, question in enumerate(normalized_questions):
        if len(question) >= 8 and question in user_text:
            return answers[index]

    ignored_words = {
        "a", "an", "the", "is", "are", "do", "does",
        "can", "could", "i", "my", "me", "to", "of",
        "for", "in", "on", "what", "how", "please",
        "tell", "about"
    }

    user_words = set(user_text.split()) - ignored_words

    best_index = -1
    best_score = 0.0

    for index, question in enumerate(normalized_questions):
        question_words = set(question.split()) - ignored_words

        if not user_words or not question_words:
            continue

        overlap = (
            len(user_words & question_words)
            / len(user_words | question_words)
        )

        similarity = SequenceMatcher(
            None, user_text, question
        ).ratio()

        score = max(overlap, similarity)

        if score > best_score:
            best_score = score
            best_index = index

    if best_index >= 0 and best_score >= 0.60:
        return answers[best_index]

    return None


# ----------------------------------
# Home page
# ----------------------------------
@app.route("/")
def home():
    return render_template("index.html")


# ----------------------------------
# Chatbot API
# ----------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        user_message = str(data.get("message", "")).strip()

        if not user_message:
            return jsonify({
                "reply": "Please enter a question."
            }), 400

        message = normalize_text(user_message)
        words = set(message.split())

        # Greetings
        if words & {"hello", "hi", "hey"}:
            return jsonify({
                "reply": (
                    "Hello! Welcome to ATI Gampaha. "
                    "You can ask me about courses, fees, duration, "
                    "schedules, registration, career opportunities, "
                    "and contact information."
                )
            })

        # Load data sources
        courses = load_courses()
        questions, answers = load_excel_qa()

        # Available course list
        course_list_phrases = [
            "available courses",
            "courses available",
            "what courses",
            "list courses",
            "all courses",
            "course list"
        ]

        if (
            message in {"course", "courses"}
            or any(phrase in message for phrase in course_list_phrases)
        ):
            names = [
                str(course.get("name", "")).strip()
                for course in courses
                if isinstance(course, dict) and course.get("name")
            ]

            if names:
                return jsonify({
                    "reply": "Our available courses are: "
                    + ", ".join(names) + "."
                })

            return jsonify({
                "reply": "Course details are currently unavailable."
            })

        # Search JSON course information only for specific
        # course-related questions
        course_question_words = {
            "fee", "fees", "price", "cost",
            "duration", "long", "weeks", "months",
            "schedule", "time", "weekday", "weekend",
            "category", "type"
        }

        for course in courses:
            if not isinstance(course, dict):
                continue

            name = str(course.get("name", "")).strip()
            name_lower = normalize_text(name)

            if not name_lower or name_lower not in message:
                continue

            # Do not override career, application, or other
            # general questions with course duration information.
            if words & {
                "career", "job", "jobs", "employment",
                "opportunity", "opportunities",
                "apply", "application", "register",
                "registration", "contact", "email", "phone"
            }:
                break

            if words & {"fee", "fees", "price", "cost"}:
                reply = (
                    f"The {name} course fee is "
                    f"{course.get('fee', 'Not available')}."
                )

            elif words & {"duration", "long", "weeks", "months"}:
                reply = (
                    f"The {name} course duration is "
                    f"{course.get('duration', 'Not available')}."
                )

            elif words & {"schedule", "time", "weekday", "weekend"}:
                reply = (
                    f"The {name} course schedule is "
                    f"{course.get('schedule', 'Not available')}."
                )

            elif words & {"category", "type"}:
                reply = (
                    f"The {name} course category is "
                    f"{course.get('category', 'Not available')}."
                )

            elif words & course_question_words:
                reply = (
                    f"Course: {name}\n"
                    f"Category: {course.get('category', 'Not available')}\n"
                    f"Duration: {course.get('duration', 'Not available')}\n"
                    f"Fee: {course.get('fee', 'Not available')}\n"
                    f"Schedule: {course.get('schedule', 'Not available')}\n"
                    f"Description: {course.get('description', 'Not available')}"
                )

            else:
                # Try Excel for other questions about this course
                break

            return jsonify({"reply": reply})

        # Excel answers for career, application, contact,
        # and other questions
        excel_answer = find_excel_answer(
            user_message, questions, answers
        )

        if excel_answer:
            return jsonify({"reply": excel_answer})

        return jsonify({
            "reply": (
                "Sorry, I could not find an answer. "
                "Please try asking in a different way, "
                "or contact ATI Gampaha."
            )
        })

    except Exception:
        app.logger.exception("Error while processing chatbot message")
        return jsonify({
            "reply": (
                "A server error occurred while processing your question. "
                "Please check the Flask terminal."
            )
        }), 500


# ----------------------------------
# Run Flask application
# ----------------------------------
if __name__ == "__main__":
    app.run(debug=True)