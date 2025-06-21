import csv
from django.contrib.auth.models import User
from app.models import Subject, Topic, Question, AnswerOption

def import_questions_from_csv(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Fan va mavzu
            subject, _ = Subject.objects.get_or_create(name=row['subject'], slug=slugify(row['subject']))
            topic, _ = Topic.objects.get_or_create(subject=subject, name=row['topic'], slug=slugify(row['topic']))

            # Savol
            question, created = Question.objects.get_or_create(
                topic=topic,
                text=row['text'],
                defaults={"difficulty": row['difficulty']}
            )

            if created:
                # Variantlar
                options = [
                    {"label": "A", "text": row['option_a'], "is_correct": row['correct_option'] == "A"},
                    {"label": "B", "text": row['option_b'], "is_correct": row['correct_option'] == "B"},
                    {"label": "C", "text": row['option_c'], "is_correct": row['correct_option'] == "C"},
                    {"label": "D", "text": row['option_d'], "is_correct": row['correct_option'] == "D"},
                ]
                for opt in options:
                    AnswerOption.objects.create(
                        question=question,
                        label=opt['label'],
                        text=opt['text'],
                        is_correct=opt['is_correct']
                    )
                print(f"Savol qo‘shildi: {row['text']}")
            else:
                print(f"Savol allaqachon mavjud: {row['text']}")

if __name__ == "__main__":
    from django.utils.text import slugify
    import_questions_from_csv('questions.csv')