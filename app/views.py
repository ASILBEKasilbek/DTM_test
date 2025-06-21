import requests
import random
import secrets

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.db.models import Count
from django.views.decorators.csrf import csrf_exempt

from .models import Subject, TestSession, UserAnswer, Result, UserProfile, Question, AnswerOption

def home(request):
    subjects = Subject.objects.all()
    return render(request, 'home.html', {'subjects': subjects})

def contact(request):
    return render(request, 'contact.html')

def about(request):
    return render(request, 'about.html')

def telegram_auth(request, telegram_id):
    try:
        user = User.objects.get(username=telegram_id)
    except User.DoesNotExist:
        user = User.objects.create_user(
            username=telegram_id,
            password=secrets.token_hex(8),
            email=f"{telegram_id}@telegram.com"
        )
        UserProfile.objects.create(user=user)

    login(request, user, backend='django.contrib.auth.backends.ModelBackend')

    subject = Subject.objects.first()
    if not subject:
        return render(request, 'home.html', {'error': "Hech qanday fan mavjud emas."})

    return redirect('app:start_test', subject_slug=subject.slug)

def start_test(request, subject_slug):
    if not request.user.is_authenticated:
        return redirect('app:telegram_auth', telegram_id='anonymous')

    subject = Subject.objects.get(slug=subject_slug)
    session = TestSession.objects.create(
        user=request.user,
        subject=subject
    )

    # Tasodifiy 10 ta savol tanlab, session bilan bog'lab qo'yamiz
    questions = Question.objects.filter(
        topic__subject=subject,
        is_active=True,
        options__isnull=False
    ).distinct().annotate(
        option_count=Count('options')
    ).filter(option_count=4).order_by('?')[:10]

    session.questions.set(questions)  # ManyToManyField orqali saqlanadi (modelda bo'lishi kerak)
    request.session['current_question_index'] = 0
    return redirect('app:test_session', session_id=session.id)

def test_session(request, session_id):
    session = TestSession.objects.get(id=session_id, user=request.user)
    if session.completed:
        return redirect('app:view_results', session_id=session.id)

    questions = session.questions.all().order_by('id')  # Avval tanlanganlar
    current_question_index = request.session.get('current_question_index', 0)
    if current_question_index >= len(questions):
        session.completed = True
        session.ended_at = timezone.now()
        session.save()
        calculate_result(session)
        send_telegram_result(request.user.username, session)
        return redirect('app:view_results', session_id=session.id)

    current_question = questions[current_question_index]
    options = current_question.options.order_by('label')[:4]  # 4 ta variant

    return render(request, 'test_session.html', {
        'session': session,
        'question': current_question,
        'options': options,
        'current_index': current_question_index + 1,
        'total_questions': len(questions)
    })
@csrf_exempt
def save_answer(request, session_id, question_id):
    if request.method == 'POST':
        try:
            session = TestSession.objects.get(id=session_id, user=request.user)
            question = Question.objects.get(id=question_id)
            answer_id = request.POST.get('answer_id')

            if not answer_id:
                return JsonResponse({'status': 'error', 'message': 'Javob tanlanmadi.'})

            selected_option = question.options.get(id=answer_id)
            UserAnswer.objects.update_or_create(
                test_session=session,
                question=question,
                defaults={'selected_option': selected_option}
            )

            current_index = request.session.get('current_question_index', 0)
            request.session['current_question_index'] = current_index + 1

            return JsonResponse({'status': 'success'})

        except (TestSession.DoesNotExist, Question.DoesNotExist, AnswerOption.DoesNotExist):
            return JsonResponse({'status': 'error', 'message': 'Noto\'g\'ri so\'rov.'})

    return JsonResponse({'status': 'error', 'message': 'Faqat POST so\'rovlari qabul qilinadi.'})

def calculate_result(session):
    with transaction.atomic():
        correct_answers = UserAnswer.objects.filter(
            test_session=session,
            selected_option__is_correct=True
        ).count()
        total_questions = session.answers.count()
        score = (correct_answers / total_questions) * 100 if total_questions else 0

        session.score = score
        session.save()

        Result.objects.create(
            test_session=session,
            correct_answers=correct_answers,
            total_questions=total_questions,
            score=score,
            percent=score
        )

def view_results(request, session_id):
    session = TestSession.objects.get(id=session_id, user=request.user)
    result = session.result
    answers = session.answers.all()
    return render(request, 'results.html', {'session': session, 'result': result, 'answers': answers})

def send_telegram_result(telegram_id, session):
    message = (
        f"\U0001F4CA Test natijasi:\n"
        f"Fan: {session.subject.name}\n"
        f"To'g'ri javoblar: {session.result.correct_answers}/{session.result.total_questions}\n"
        f"Foiz: {session.result.percent}%\n"
        f"Ball: {session.result.score}"
    )
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': telegram_id,
        'text': message
    }
    requests.post(url, data=data)