from django.contrib.auth.models import User
from app.models import Subject, Topic, Question, AnswerOption

def import_questions():
    # Mavzu va fan yaratish
    subject, _ = Subject.objects.get_or_create(name="Matematika", slug="matematika")
    topic, _ = Topic.objects.get_or_create(subject=subject, name="Algebra", slug="algebra")

    # Namuna savollar ro‘yxati
    sample_questions = [
        {
            "text": "2 + 2 = ?",
            "difficulty": "easy",
            "options": [
                {"label": "A", "text": "4", "is_correct": True},
                {"label": "B", "text": "3", "is_correct": False},
                {"label": "C", "text": "5", "is_correct": False},
                {"label": "D", "text": "6", "is_correct": False},
            ]
        },
        {
            "text": "5 * 3 = ?",
            "difficulty": "medium",
            "options": [
                {"label": "A", "text": "12", "is_correct": False},
                {"label": "B", "text": "15", "is_correct": True},
                {"label": "C", "text": "18", "is_correct": False},
                {"label": "D", "text": "20", "is_correct": False},
            ]
        },
        # Yana savollar qo‘shishingiz mumkin
    ]

    for q_data in sample_questions:
        question, created = Question.objects.get_or_create(
            topic=topic,
            text=q_data["text"],
            defaults={"difficulty": q_data["difficulty"]}
        )
        if created:
            for opt_data in q_data["options"]:
                AnswerOption.objects.create(
                    question=question,
                    label=opt_data["label"],
                    text=opt_data["text"],
                    is_correct=opt_data["is_correct"]
                )
            print(f"Savol qo‘shildi: {q_data['text']}")
        else:
            print(f"Savol allaqachon mavjud: {q_data['text']}")

if __name__ == "__main__":
    import_questions()