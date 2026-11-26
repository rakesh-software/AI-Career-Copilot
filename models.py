from db import db
from datetime import datetime


class User(db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )

    resumes = db.relationship(
        "Resume",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )

    reports = db.relationship(
        "CareerReport",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )


class Resume(db.Model):

    __tablename__ = "resumes"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    filename = db.Column(
        db.String(255),
        nullable=False
    )

    resume_text = db.Column(
        db.Text,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    reports = db.relationship(
        "CareerReport",
        backref="resume",
        lazy=True
    )


class CareerReport(db.Model):

    __tablename__ = "reports"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    resume_id = db.Column(
        db.Integer,
        db.ForeignKey("resumes.id"),
        nullable=True
    )

    skills = db.Column(
        db.Text
    )

    skill_gaps = db.Column(
        db.Text
    )

    recommendations = db.Column(
        db.Text
    )

    interview_questions = db.Column(
        db.Text
    )

    roadmap = db.Column(
        db.Text
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )