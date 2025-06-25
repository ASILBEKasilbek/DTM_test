import logging
import random
import secrets
import requests
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.db.models import Count
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .models import Subject, TestSession, UserAnswer, Result, UserProfile, Question, AnswerOption

logger = logging.getLogger(__name__)

# Konstantalar (settings.py da aniqlanishi kerak)
DEFAULT_QUESTION_COUNT = getattr(settings, 'DEFAULT_QUESTION_COUNT', 10)
OPTIONS_PER_QUESTION = getattr(settings, 'OPTIONS_PER_QUESTION', 4)

def home(request):
    subjects = Subject.objects.filter(is_deleted=False)
    return render(request, 'home.html', {'subjects': subjects})

def contact(request):
    return render(request, 'contact.html')

def about(request):
    return render(request, 'about.html')

def telegram_auth(request, telegram_id):
    try:
        # Telegram ID ni tasdiqlash (misol uchun, bot API orqali)
        response = requests.get(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getChat",
            params={'chat_id': telegram_id}
        )
        response.raise_for_status()
        if not response.json().get('ok'):
            logger.warning(f"Invalid Telegram ID: {telegram_id}")
            return render(request, 'home.html', {'error': "Noto‘g‘ri Telegram ID."})
    except requests.RequestException as e:
        logger.error(f"Telegram API error: {e}")
        return render(request, 'home.html', {'error': "Telegram autentifikatsiyasi xatosi."})

    try:
        user = User.objects.get(username=telegram_id)
    except User.DoesNotExist:
        user = User.objects.create_user(
            username=telegram_id,
            password=secrets.token_hex(8),
            email=f"{telegram_id}@example.com"
        )
        UserProfile.objects.create(user=user)
        logger.info(f"New user created: {telegram_id}")

    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return render(request,'base.html', {'user': user})
    # subject = Subject.objects.filter(is_deleted=False).first()
    # if not subject:
    #     logger.warning("No subjects available")
    #     return render(request, 'home.html', {'error': "Hech qanday fan mavjud emas."})

    # return redirect('app:start_test', subject_slug=subject.slug)

def start_test(request, subject_slug):
    if not request.user.is_authenticated:
        return redirect('app:telegram_auth', telegram_id='anonymous')

    try:
        subject = Subject.objects.get(slug=subject_slug, is_deleted=False)
    except Subject.DoesNotExist:
        logger.error(f"Subject not found: {subject_slug}")
        raise Http404("Fan topilmadi.")

    with transaction.atomic():
        session = TestSession.objects.create(
            user=request.user,
            subject=subject
        )
        question_ids = list(Question.objects.filter(
            topic__subject=subject,
            is_active=True,
            is_deleted=False
        ).annotate(
            option_count=Count('options')
        ).filter(option_count=OPTIONS_PER_QUESTION).values_list('id', flat=True))
        
        if len(question_ids) < DEFAULT_QUESTION_COUNT:
            logger.warning(f"Insufficient questions for subject {subject.name}")
            return render(request, 'home.html', {'error': 'Bu fanda yetarli savol mavjud emas.'})

        selected_ids = random.sample(question_ids, min(DEFAULT_QUESTION_COUNT, len(question_ids)))
        session.randomized_question_ids = selected_ids
        session.save()
        request.session[f'session_{session.id}_current_index'] = 0
        logger.info(f"Test session {session.id} started for user {request.user.username}")

    return redirect('app:test_session', session_id=session.id)

def test_session(request, session_id):
    try:
        session = TestSession.objects.prefetch_related('answers__question__options').get(
            id=session_id, user=request.user, is_deleted=False
        )
    except TestSession.DoesNotExist:
        logger.error(f"Test session {session_id} not found for user {request.user.username}")
        raise Http404("Test sessiyasi topilmadi.")

    if session.completed:
        return redirect('app:view_results', session_id=session.id)

    question_ids = session.randomized_question_ids
    if not question_ids:
        session.completed = True
        session.ended_at = timezone.now()
        session.save()
        calculate_result(session)
        send_telegram_result(request.user.username, session)
        return redirect('app:view_results', session_id=session.id)

    current_index = request.session.get(f'session_{session.id}_current_index', 0)
    if current_index >= len(question_ids):
        session.completed = True
        session.ended_at = timezone.now()
        session.score = session.calculate_score()
        session.save()
        calculate_result(session)
        send_telegram_result(request.user.username, session)
        return redirect('app:view_results', session_id=session.id)

    current_question = Question.objects.get(id=question_ids[current_index])
    options = current_question.get_shuffled_options()[:OPTIONS_PER_QUESTION]

    return render(request, 'test_session.html', {
        'session': session,
        'question': current_question,
        'options': options,
        'current_index': current_index + 1,
        'total_questions': len(question_ids)
    })

@require_POST
@ratelimit(key='user', rate='10/m')
def save_answer(request, session_id, question_id):
    try:
        with transaction.atomic():
            session = TestSession.objects.select_for_update().get(
                id=session_id, user=request.user, is_deleted=False
            )
            question = Question.objects.get(id=question_id, is_deleted=False)
            answer_id = request.POST.get('answer_id')
            if not answer_id:
                return JsonResponse({'status': 'error', 'message': 'Javob tanlanmadi.'})

            selected_option = question.options.get(id=answer_id, is_deleted=False)
            UserAnswer.objects.update_or_create(
                test_session=session,
                question=question,
                defaults={'selected_option': selected_option}
            )
            request.session[f'session_{session.id}_current_index'] += 1
            logger.info(f"Answer saved for question {question_id} in session {session_id} by user {request.user.username}")
            return JsonResponse({'status': 'success'})
    except TestSession.DoesNotExist:
        logger.error(f"Test session {session_id} not found")
        return JsonResponse({'status': 'error', 'message': 'Test sessiyasi topilmadi.'})
    except Question.DoesNotExist:
        logger.error(f"Question {question_id} not found")
        return JsonResponse({'status': 'error', 'message': 'Savol topilmadi.'})
    except AnswerOption.DoesNotExist:
        logger.error(f"Answer option {answer_id} not found")
        return JsonResponse({'status': 'error', 'message': 'Javob varianti topilmadi.'})
    except Exception as e:
        logger.error(f"Unexpected error in save_answer: {e}")
        return JsonResponse({'status': 'error', 'message': 'Xato yuz berdi.'})

def calculate_result(session):
    with transaction.atomic():
        session = TestSession.objects.select_for_update().get(id=session.id)
        correct_answers = UserAnswer.objects.filter(
            test_session=session,
            selected_option__is_correct=True
        ).count()
        total_questions = session.answers.count()
        percent = (correct_answers / total_questions) * 100 if total_questions else 0
        session.score = percent
        session.save()
        Result.objects.create(
            test_session=session,
            correct_answers=correct_answers,
            total_questions=total_questions,
            percent=percent
        )
        logger.info(f"Result calculated for session {session.id}: {percent}%")

def view_results(request, session_id):
    try:
        session = TestSession.objects.get(id=session_id, user=request.user, is_deleted=False)
        result = session.result
        answers = session.answers.all()
        return render(request, 'results.html', {'session': session, 'result': result, 'answers': answers})
    except TestSession.DoesNotExist:
        logger.error(f"Test session {session_id} not found for user {request.user.username}")
        raise Http404("Test sessiyasi topilmadi.")

def send_telegram_result(telegram_id, session):
    message = (
        f"\U0001F4CA Test natijasi:\n"
        f"Fan: {session.subject.name}\n"
    )
    if hasattr(session, 'result'):
        message += (
            f"To'g'ri javoblar: {session.result.correct_answers}/{session.result.total_questions}\n"
            f"Foiz: {session.result.percent}%\n"
        )
    else:
        message += "Natija hisoblanmadi."
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {'chat_id': telegram_id, 'text': message}
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        logger.info(f"Telegram message sent to {telegram_id}")
    except requests.RequestException as e:
        logger.error(f"Failed to send Telegram message to {telegram_id}: {e}")