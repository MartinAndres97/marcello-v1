import copy

import pytest

from app.survey_definition import QUESTIONS, survey_to_dict, validate_answers

GOOD = {"P1": [4], "P2": [4], "P3": [1, 2], "P4": [5], "P5": [1], "P6": [3], "P7": [1, 5], "P8": [4],
        "P9": [2], "P10": [5], "P11": [3], "P12": [4], "P13": [1, 2, 3], "P14": [1], "P15": [6]}


def test_fifteen_questions_with_expected_shape():
    assert [q.code for q in QUESTIONS] == [f"P{i}" for i in range(1, 16)]
    types = {q.code: q.qtype for q in QUESTIONS}
    assert [c for c, t in types.items() if t == "likert"] == ["P2", "P4", "P6", "P8", "P10", "P12"]
    assert [c for c, t in types.items() if t == "single"] == ["P1", "P15"]
    assert [c for c, t in types.items() if t == "multiple"] == ["P3", "P5", "P7", "P9", "P11", "P13", "P14"]
    assert len(QUESTIONS[0].options) == 10 and len(QUESTIONS[14].options) == 6
    assert all(len(q.options) == 5 for q in QUESTIONS if q.qtype in ("likert", "multiple"))
    assert len(survey_to_dict()["questions"]) == 15


def test_valid_answers_pass():
    clean, errors = validate_answers(copy.deepcopy(GOOD))
    assert errors == {} and len(clean) == 15


@pytest.mark.parametrize("mutate,code", [
    (lambda a: a.pop("P15"), "P15"),
    (lambda a: a.update(P2=[6]), "P2"),
    (lambda a: a.update(P2=[0]), "P2"),
    (lambda a: a.update(P2=[1, 2]), "P2"),
    (lambda a: a.update(P3=[]), "P3"),
    (lambda a: a.update(P3=[1, 1]), "P3"),
    (lambda a: a.update(P3=[9]), "P3"),
    (lambda a: a.update(P1=[11]), "P1"),
    (lambda a: a.update(P15=[1, 2]), "P15"),
    (lambda a: a.update(P2=[True]), "P2"),
    (lambda a: a.update(P2=[2.0]), "P2"),
    (lambda a: a.update(P99=[1]), "P99"),
])
def test_invalid_answers_rejected(mutate, code):
    answers = copy.deepcopy(GOOD)
    mutate(answers)
    _, errors = validate_answers(answers)
    assert code in errors
