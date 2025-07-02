import json
import os
from django.utils.text import slugify
from app.models import Subject, Topic, Question, AnswerOption

def yukla_testlar():
    # Fanlar va ularga mos JSON fayllar ro‘yxati
    fanlar = {
        # "Matematika": "tests/matematika_tests.json",
        # "Adabiyot": "tests/adabiyot.json",
        # "Biologiya": "tests/biologiya_tests.json",
        # "Fizika": "tests/fizika_tests.json",
        # "Geografiya": "tests/geografiya_tests.json",
        # "Ingliz tili": "tests/ingliz_tili_tests.json",
        # "Kimyo": "tests/kimyo_tests.json",
        # "Nemis tili": "tests/nemis_tili_tests.json",
        # "Fransuz tili": "tests/fransuz_tili_tests.json",
        # "Ona tili": "tests/ona_tili_tests.json",
        "Rus tili": "tests/rus_tili_tests.json",
        # "Tarix": "tests/tarix_tests.json",
    }

    for fan_nomi, fayl_yoli in fanlar.items():
        try:
            # Faylni ochish
            if not os.path.exists(fayl_yoli):
                print(f"⚠️ {fayl_yoli} fayli topilmadi.")
                continue

            with open(fayl_yoli, encoding="utf-8") as f:
                questions = json.load(f)

            # 1. Fan va Mavzuni olish yoki yaratish
            subject, created = Subject.objects.get_or_create(
                name=fan_nomi,
                defaults={"slug": slugify(fan_nomi)}
            )
            topic, created = Topic.objects.get_or_create(
                subject=subject,
                name=f"{fan_nomi} umumiy",
                defaults={"slug": slugify(f"{fan_nomi}-umumiy"), "description": f"{fan_nomi} asoslari"}
            )

            # 2. Savollarni bazaga qo‘shish
            for q in questions:
                question = Question.objects.create(
                    topic=topic,
                    text=q["text"],
                    difficulty=q["difficulty"],
                    explanation=q["explanation"]
                )
                for opt in q["options"]:
                    AnswerOption.objects.create(
                        question=question,
                        label=opt["label"],
                        text=opt["text"],
                        is_correct=opt["is_correct"]
                    )
            print(f"✅ {fan_nomi} bo‘yicha test savollar bazaga qo‘shildi.")

        except Exception as e:
            print(f"❌ {fan_nomi} testlarini yuklashda xatolik: {str(e)}")
            continue

    print("✅ Barcha test savollar va variantlar bazaga qo‘shildi.")