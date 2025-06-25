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
import re
from .models import *
logger = logging.getLogger(__name__)

# Konstantalar
DEFAULT_QUESTION_COUNT = getattr(settings, 'DEFAULT_QUESTION_COUNT', 30)
OPTIONS_PER_QUESTION = getattr(settings, 'OPTIONS_PER_QUESTION', 4)
# views.py

from django.http import HttpResponse
from testlarni_yaratish import yukla_testlar
from app.models import Question
from django.contrib.admin.views.decorators import staff_member_required


@staff_member_required
def testlarni_yuklash_view(request):
    # Agar biron bir fan uchun savollar mavjud bo‘lsa, yuklashni to‘xtatamiz
    if Question.objects.exists():
        return HttpResponse("⚠️ Testlar allaqachon yuklangan.")
    try:
        yukla_testlar()
        return HttpResponse("✅ Barcha fanlar bo‘yicha testlar muvaffaqiyatli yuklandi.")
    except Exception as e:
        return HttpResponse(f"❌ Xatolik yuz berdi: {str(e)}")
    
def home(request):
    subjects = Subject.objects.filter(is_deleted=False)
    return render(request, 'home.html', {'subjects': subjects})

@ratelimit(key='user_or_ip', rate='5/m')
def contact(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            message = request.POST.get('message', '').strip()

            # Validatsiya
            if not name or len(name) < 2:
                return JsonResponse({'status': 'error', 'message': 'Ism kamida 2 harfdan iborat bo‘lishi kerak.'})
            if not re.match(r'^\+998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}$', phone):
                return JsonResponse({'status': 'error', 'message': 'Telefon raqami +998 XX XXX XX XX formatida bo‘lishi kerak.'})
            if not message or len(message) < 10:
                return JsonResponse({'status': 'error', 'message': 'Xabar kamida 10 harfdan iborat bo‘lishi kerak.'})

            # Feedback modeliga saqlash
            with transaction.atomic():
                feedback = Feedback.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    subject=f"Aloqa formasi: {name}",
                    message=f"Ism: {name}\nTelefon: {phone}\nXabar: {message}",
                    status='pending'
                )

            # Telegramga xabar yuborish
            telegram_message = (
                f"📬 Yangi xabar:\n"
                f"Ism: {name}\n"
                f"Telefon: {phone}\n"
                f"Xabar: {message}\n"
                f"Vaqt: {timezone.now().strftime('%Y-%m-%d %H:%M')}"
            )
            telegram_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
            telegram_data = {
                'chat_id': settings.ADMIN_TELEGRAM_ID,
                'text': telegram_message
            }
            try:
                response = requests.post(telegram_url, data=telegram_data)
                response.raise_for_status()
                logger.info(f"Telegram message sent for feedback from {phone}")
            except requests.RequestException as e:
                logger.error(f"Failed to send Telegram message for feedback: {e}")
                return JsonResponse({'status': 'error', 'message': 'Xabar Telegramga yuborilmadi, lekin saqlandi.'})

            return JsonResponse({'status': 'success', 'message': 'Xabar muvaffaqiyatli yuborildi!'})

        except Exception as e:
            logger.error(f"Error processing contact form: {e}")
            return JsonResponse({'status': 'error', 'message': 'Xabar yuborishda xato yuz berdi.'})
    else:
        return render(request, 'contact.html')
def about(request):
    return render(request, 'about.html')

def telegram_auth(request, telegram_id):
    try:
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
    subjects = Subject.objects.filter(is_deleted=False)
    return render(request, 'home.html', {'subjects': subjects})

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
        request.session['selected_answers'] = {}
        logger.info(f"Test session {session.id} started for user {request.user.username}")

    return redirect('app:test_session', session_id=session.id)

def test_session(request, session_id):
    try:
        session = TestSession.objects.prefetch_related('answers__question__options').get(
            id=session_id, user=request.user, is_deleted=False
        )
    except TestSession.DoesNotExist:
        logger.error(f"Test session {session_id} not found for user喧_0x1Ffor user {request.user.username}")
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

    questions = Question.objects.filter(id__in=question_ids).prefetch_related('options')
    answered_count = UserAnswer.objects.filter(test_session=session).count()

    # Sessiya va ma'lumotlar bazasidagi javoblarni sinxronlashtirish
    selected_answers = request.session.get("selected_answers", {}).get(str(session_id), {})
    # Ma'lumotlar bazasidagi javoblarni qo'shish
    user_answers = UserAnswer.objects.filter(test_session=session).select_related('selected_option')
    for answer in user_answers:
        selected_answers[str(answer.question.id)] = str(answer.selected_option.id)
    request.session['selected_answers'][str(session_id)] = selected_answers
    request.session.modified = True

    return render(request, 'test_session.html', {
        'session': session,
        'questions': questions,
        'answered_count': answered_count,
        'questions_count': questions.count(),
        'selected_answers': selected_answers,
    })


@require_POST
def save_answer_session(request, session_id, question_id):
    answer_id = request.POST.get("answer_id")
    if not answer_id:
        return JsonResponse({"status": "error", "message": "answer_id topilmadi"})

    try:
        with transaction.atomic():
            session = TestSession.objects.get(id=session_id, user=request.user, is_deleted=False)
            question = Question.objects.get(id=question_id, is_deleted=False)
            selected_option = AnswerOption.objects.get(id=answer_id, is_deleted=False)
            user_answer, created = UserAnswer.objects.update_or_create(
                test_session=session,
                question=question,
                defaults={'selected_option': selected_option, 'is_correct': selected_option.is_correct}
            )
            logger.info(f"Answer saved for question {question_id} in session {session_id} by user {request.user.username}")
    except Exception as e:
        logger.error(f"Error saving answer to DB: {e}")
        return JsonResponse({"status": "error", "message": "Javobni saqlashda xato yuz berdi."})

    selected_answers = request.session.get("selected_answers", {})
    session_key = str(session_id)
    if session_key not in selected_answers:
        selected_answers[session_key] = {}
    selected_answers[session_key][str(question_id)] = answer_id
    request.session["selected_answers"] = selected_answers
    request.session.modified = True

    return JsonResponse({"status": "success"})

@require_POST
@ratelimit(key='user', rate='10/m')
def save_answer_db(request, session_id, question_id):
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
            user_answer, created = UserAnswer.objects.update_or_create(
                test_session=session,
                question=question,
                defaults={'selected_option': selected_option, 'is_correct': selected_option.is_correct}
            )
            if 'selected_answers' not in request.session:
                request.session['selected_answers'] = {}
            request.session['selected_answers'][str(question_id)] = str(selected_option.id)
            request.session.modified = True
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

@require_POST
@ratelimit(key='user', rate='5/m')
def submit_test(request, session_id):
    try:
        with transaction.atomic():
            session = TestSession.objects.select_for_update().get(
                id=session_id, user=request.user, is_deleted=False
            )

            if session.completed:
                logger.info(f"Test session {session_id} already completed")
                return JsonResponse({
                    'status': 'success',
                    'redirect_url': reverse('app:view_results', kwargs={'session_id': session.id})
                })

            # Sessiyadagi vaqtincha javoblarni saqlash
            selected_answers = request.session.get('selected_answers', {}).get(str(session_id), {})
            for question_id, answer_id in selected_answers.items():
                try:
                    question = Question.objects.get(id=question_id, is_deleted=False)
                    selected_option = question.options.get(id=answer_id, is_deleted=False)
                    UserAnswer.objects.update_or_create(
                        test_session=session,
                        question=question,
                        defaults={'selected_option': selected_option}
                    )
                except Exception as e:
                    logger.warning(f"Error saving answer for question {question_id}: {e}")
                    continue

            # Sessiyani yakunlash
            odi = TestSession.objects.get(id=session.id)
            session.completed = True
            session.ended_at = timezone.now()
            session.score = odi.calculate_score() if hasattr(odi, 'calculate_score') else 0
            session.save()

            # Natijalarni hisoblash va xabar yuborish
            calculate_result(session)
            send_telegram_result(request.user.username, session)

            logger.info(f"Test session {session_id} completed for user {request.user.username}")

            return JsonResponse({
                'status': 'success',
                'redirect_url': reverse('app:view_results', kwargs={'session_id': session.id})
            })

    except TestSession.DoesNotExist:
        logger.error(f"Test session {session_id} not found")
        return JsonResponse({'status': 'error', 'message': 'Test sessiyasi topilmadi.'})
    except Exception as e:
        logger.error(f"Unexpected error in submit_test: {e}")
        return JsonResponse({'status': 'error', 'message': f'Xato yuz berdi: {str(e)}'})

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